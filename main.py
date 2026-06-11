import sys
import argparse
import datetime
from pathlib import Path
import cv2
import numpy as np

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QGridLayout, QHBoxLayout,
    QVBoxLayout, QLabel, QLineEdit, QPushButton, QListWidget,
    QFrame, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtGui import QImage, QPixmap, QFont

from utils.inference import PCDetectionBackend, BPUDetectionBackend
from utils.camera_worker import FrameBuffer, CameraGrabber, InferenceWorker
from utils.db_manager import DBManager
from utils.gui_theme import get_qss_theme, get_no_signal_pixmap


def ndarray_to_qpixmap(img, width=640, height=480) -> QPixmap:
    """将 OpenCV BGR 图像转为 PyQt QPixmap 并自适应大小"""
    h, w, c = img.shape
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    bytes_per_line = c * w
    qimg = QImage(img_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
    pixmap = QPixmap.fromImage(qimg)
    return pixmap.scaled(width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation)


class GarageLocatorWindow(QMainWindow):
    """地库车辆定位系统主监控窗口"""
    def __init__(self, detector, db, input_sources):
        super().__init__()
        self.detector = detector
        self.db = db
        self.input_sources = input_sources
        
        self.grabbers = []
        self.inference_worker = None
        self.frame_buffer = FrameBuffer()

        self.setWindowTitle("地库车辆定位系统")
        self.showFullScreen()  # 默认全屏展示
        self.setStyleSheet(get_qss_theme())

        self.init_ui()
        self.start_threads()

    def init_ui(self):
        # 1. 主窗口中央部件
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # 2. 左侧监控大屏 (2x2 网格布局)
        left_widget = QWidget(self)
        grid_layout = QGridLayout(left_widget)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(10)
        
        self.camera_views = {}
        for i in range(4):
            view_label = QLabel(self)
            view_label.setObjectName("camera_view")
            view_label.setAlignment(Qt.AlignCenter)
            view_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            
            # 默认展示“信号丢失”占位图
            offline_img = get_no_signal_pixmap(name=f"Camera {i+1}")
            view_label.setPixmap(ndarray_to_qpixmap(offline_img, 640, 480))
            
            row = i // 2
            col = i % 2
            grid_layout.addWidget(view_label, row, col)
            self.camera_views[i] = view_label

        main_layout.addWidget(left_widget, stretch=3)

        # 3. 右侧控制台与查询日志侧边栏
        right_panel = QFrame(self)
        right_panel.setObjectName("panel_frame")
        right_panel.setFixedWidth(400)
        panel_layout = QVBoxLayout(right_panel)
        panel_layout.setContentsMargins(15, 15, 15, 15)
        panel_layout.setSpacing(15)

        # 系统标题
        title_label = QLabel("地库车辆定位系统", self)
        title_label.setFont(QFont("Microsoft YaHei", 18, QFont.Bold))
        title_label.setStyleSheet("color: #1F8EF1;")
        title_label.setAlignment(Qt.AlignCenter)
        panel_layout.addWidget(title_label)

        # 车辆检索部分
        search_title = QLabel("车辆末次位置查询", self)
        search_title.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        panel_layout.addWidget(search_title)

        search_bar_layout = QHBoxLayout()
        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("请输入要检索的车牌号...")
        self.search_input.returnPressed.connect(self.search_vehicle)
        search_bar_layout.addWidget(self.search_input)

        search_btn = QPushButton("查询", self)
        search_btn.clicked.connect(self.search_vehicle)
        search_bar_layout.addWidget(search_btn)
        panel_layout.addLayout(search_bar_layout)

        # 查询结果显示区
        self.result_frame = QFrame(self)
        self.result_frame.setStyleSheet("""
            QFrame {
                background-color: #1B2436; 
                border-radius: 6px; 
                padding: 10px;
                border: 1px solid #2D3D5A;
            }
        """)
        self.result_frame.setVisible(False)
        result_layout = QVBoxLayout(self.result_frame)
        self.result_text_label = QLabel(self)
        self.result_text_label.setWordWrap(True)
        self.result_text_label.setFont(QFont("Microsoft YaHei", 11))
        self.result_crop_label = QLabel(self)
        self.result_crop_label.setAlignment(Qt.AlignCenter)
        self.result_crop_label.setFixedSize(200, 80)
        self.result_crop_label.setStyleSheet("background-color: #0A0D14; border: 1px solid #2D3D5A;")
        
        result_layout.addWidget(self.result_text_label)
        result_layout.addWidget(self.result_crop_label, alignment=Qt.AlignCenter)
        panel_layout.addWidget(self.result_frame)

        # 实时日志部分
        log_title = QLabel("实时通行日志", self)
        log_title.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        panel_layout.addWidget(log_title)

        self.log_list = QListWidget(self)
        panel_layout.addWidget(self.log_list)

        # 快捷提示信息
        tips_label = QLabel("提示: 按 Esc 键退出系统全屏", self)
        tips_label.setFont(QFont("Microsoft YaHei", 10))
        tips_label.setStyleSheet("color: #718096;")
        tips_label.setAlignment(Qt.AlignCenter)
        panel_layout.addWidget(tips_label)

        main_layout.addWidget(right_panel, stretch=1)

    def start_threads(self):
        # 1. 启动推理线程
        self.inference_worker = InferenceWorker(self.frame_buffer, self.detector)
        self.inference_worker.frame_processed.connect(self.on_frame_processed)
        self.inference_worker.start()

        # 2. 启动指定通道的摄像头线程
        for i in range(4):
            if i < len(self.input_sources) and self.input_sources[i] is not None:
                source = self.input_sources[i]
                grabber = CameraGrabber(camera_id=i, source=source, frame_buffer=self.frame_buffer)
                grabber.start()
                self.grabbers.append(grabber)

    @pyqtSlot(int, QImage, list, float)
    def on_frame_processed(self, camera_id: int, frame: QImage, results: list, latency: float):
        """处理推理线程发回的图像和车牌数据"""
        # 更新监控画面
        if camera_id in self.camera_views:
            pixmap = QPixmap.fromImage(frame).scaled(
                self.camera_views[camera_id].width(),
                self.camera_views[camera_id].height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.camera_views[camera_id].setPixmap(pixmap)

        # 登记车牌事件并写入日志
        for res in results:
            if not res.text:
                continue
            
            # 过滤非必要干扰（比如识别出少于 4 个字符的脏文本）
            if len(res.text) < 4:
                continue

            # 插入本地轨迹数据库
            self.db.record_occurrence(res.text, camera_id + 1, res.crop)

            # 打印日志通知 UI
            time_str = datetime.datetime.now().strftime("%H:%M:%S")
            log_msg = f"[{time_str}] #{camera_id + 1}号摄像头 -> 识别到: {res.text} (耗时: {latency:.1f}ms)"
            
            # 防止日志无限堆积，只留最新 100 条
            if self.log_list.count() > 100:
                self.log_list.takeItem(0)
            self.log_list.addItem(log_msg)
            self.log_list.scrollToBottom()

    def search_vehicle(self):
        """末次位置轨迹搜索"""
        query_text = self.search_input.text().strip().upper()
        if not query_text:
            self.result_frame.setVisible(False)
            return

        # 查询数据库
        res = self.db.query_last_location(query_text)
        if res:
            self.result_frame.setVisible(True)
            self.result_text_label.setText(
                f"查询车牌: <b>{query_text}</b><br/>"
                f"末次位置: <b>{res['camera_id']} 号摄像头</b><br/>"
                f"通行时间: <font color='#A0AEC0'>{res['timestamp']}</font>"
            )
            
            # 显示截取到的车牌图像
            crop_img = res.get("crop_image")
            if crop_img is not None and crop_img.size > 0:
                # 转换色彩通道以在 QLabel 中显示
                h, w, c = crop_img.shape
                bytes_per_line = c * w
                rgb_crop = cv2.cvtColor(crop_img, cv2.COLOR_BGR2RGB)
                qimg = QImage(rgb_crop.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
                pixmap = QPixmap.fromImage(qimg).scaled(200, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.result_crop_label.setPixmap(pixmap)
                self.result_crop_label.setVisible(True)
            else:
                self.result_crop_label.clear()
                self.result_crop_label.setVisible(False)
        else:
            # 模糊联想搜索提示
            fuzzy_list = self.db.query_fuzzy(query_text)
            self.result_frame.setVisible(True)
            self.result_crop_label.setVisible(False)
            if fuzzy_list:
                plates_str = ", ".join([item["plate_number"] for item in fuzzy_list[:3]])
                self.result_text_label.setText(
                    f"未找到精确匹配。相关联想车牌:<br/><b>{plates_str}</b>"
                )
            else:
                self.result_text_label.setText(
                    f"<font color='#FD5D93'>未找到车牌 <b>{query_text}</b> 的任何通行记录。</font>"
                )

    def keyPressEvent(self, event):
        """按 Esc 键退出全屏/程序"""
        if event.key() == Qt.Key_Escape:
            self.close()

    def closeEvent(self, event):
        """窗口关闭时安全终止所有后台线程"""
        print("Closing application, terminating threads...")
        for grabber in self.grabbers:
            grabber.stop()
        if self.inference_worker:
            self.inference_worker.stop()
        event.accept()


def main():
    parser = argparse.ArgumentParser(description="地库车辆定位系统监控大屏控制台")
    parser.add_argument(
        "--backend", choices=("pc", "bpu"), default="pc",
        help="指定推理后端，'pc' 用于电脑测试，'bpu' 用于实机部署"
    )
    parser.add_argument(
        "--inputs", nargs="+", default=[],
        help="指定摄像头输入源列表，空格分隔（例如 0 1 video.mp4 对应通道 1、2、3），最多 4 路"
    )
    parser.add_argument(
        "--yolo-model", default="models/yolo11m-pose-carplate.pt",
        help="PC 端的 PyTorch YOLO pose 权重路径"
    )
    parser.add_argument(
        "--yolo-bin", default="models/yolo11m-pose-carplate_bayese_640x640_nv12.bin",
        help="BPU 端的 YOLOv11 bin 模型文件路径"
    )
    parser.add_argument(
        "--lpr-bin", default="models/lpr.bin",
        help="BPU 端的 LPRNet bin 字符识别模型文件路径"
    )
    args = parser.parse_args()

    # 1. 整理 4 路输入源
    sources = [None] * 4
    for idx, inp in enumerate(args.inputs[:4]):
        sources[idx] = inp

    # 2. 初始化数据库
    db = DBManager()

    # 3. 实例化推理后端
    if args.backend == "bpu":
        detector = BPUDetectionBackend(args.yolo_bin, args.lpr_bin)
    else:
        # PC 推理模式
        detector = PCDetectionBackend(args.yolo_model)

    # 4. 启动 PyQt 应用
    app = QApplication(sys.argv)
    window = GarageLocatorWindow(detector, db, sources)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

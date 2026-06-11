import sys
import argparse
import time
from PyQt5.QtCore import QCoreApplication, pyqtSlot, QObject
from PyQt5.QtGui import QImage
from inference import BPUDetectionBackend, PCDetectionBackend
from camera_worker import FrameBuffer, CameraGrabber, InferenceWorker
from db_manager import DBManager

class HeadlessTester(QObject):
    """Headless 模式下验证多线程拉流与 BPU 推理的核心逻辑"""
    def __init__(self, detector, db, sources):
        super().__init__()
        self.detector = detector
        self.db = db
        self.frame_buffer = FrameBuffer()
        self.grabbers = []
        
        # 1. 实例化推理工作线程 (QThread 在 QCoreApplication 事件循环下正常运作)
        self.inference_worker = InferenceWorker(self.frame_buffer, self.detector)
        self.inference_worker.frame_processed.connect(self.on_frame_processed)
        self.inference_worker.start()

        # 2. 启动采集线程
        for i, src in enumerate(sources):
            if src is not None:
                grabber = CameraGrabber(camera_id=i, source=src, frame_buffer=self.frame_buffer)
                grabber.start()
                self.grabbers.append(grabber)
                
        print(f"Headless Tester started with {len(self.grabbers)} grabbers.")
        print("Running for 20 seconds to log detections, then exit...")

    @pyqtSlot(int, QImage, list, float)
    def on_frame_processed(self, camera_id: int, frame: QImage, results: list, latency: float):
        print(f"\n[Headless Log] 通道 #{camera_id + 1} 推理耗时: {latency:.1f}ms")
        for res in results:
            if not res.text or len(res.text) < 4:
                continue
            # 记录到 SQLite 轨迹库
            self.db.record_occurrence(res.text, camera_id + 1, res.crop)
            print(f"  >>> 【车牌捕获成功】: {res.text} (置信度: {res.confidence:.2f})")
            
            # 同时查一下这辆车在数据库中的最后位置，验证查询机制
            last_pos = self.db.query_last_location(res.text)
            if last_pos:
                print(f"  >>> 【轨迹自检】 车牌 {res.text} 末次出现在 {last_pos['camera_id']} 号摄像头 (时间: {last_pos['timestamp']})")

    def stop(self):
        print("Stopping headless threads...")
        for grabber in self.grabbers:
            grabber.stop()
        if self.inference_worker:
            self.inference_worker.stop()


def main():
    parser = argparse.ArgumentParser(description="地库车辆定位系统 - 无界面测试工具")
    parser.add_argument(
        "--backend", choices=("pc", "bpu"), default="bpu",
        help="指定推理后端，BPU 板端运行请设为 'bpu'"
    )
    parser.add_argument(
        "--inputs", nargs="+", default=[],
        help="指定输入视频流或测试图片，多个用空格分隔，最多4个"
    )
    parser.add_argument(
        "--yolo-bin", default="models/yolo11m-pose-carplate_bayese_640x640_nv12.bin",
        help="BPU 端的 YOLO bin 模型路径"
    )
    parser.add_argument(
        "--lpr-bin", default="models/lpr.bin",
        help="BPU 端的 LPRNet bin 模型路径"
    )
    args = parser.parse_args()

    # 1. 整理 4 路输入源
    sources = [None] * 4
    for idx, inp in enumerate(args.inputs[:4]):
        sources[idx] = inp

    if not any(sources):
        print("Error: 请使用 --inputs 参数传入至少一个视频流或测试图像！")
        return 1

    # 2. 初始化非图形的核心 Application 事件循环
    app = QCoreApplication(sys.argv)

    # 3. 初始化数据库与推理后端
    db = DBManager("headless_test.db")
    if args.backend == "bpu":
        detector = BPUDetectionBackend(args.yolo_bin, args.lpr_bin)
    else:
        # PC 测试模式（如果本地有环境）
        from inference import PCDetectionBackend
        detector = PCDetectionBackend("models/yolo11m-pose-carplate.pt")

    # 4. 运行测试
    tester = HeadlessTester(detector, db, sources)

    # 5. 定时器 20 秒后关闭退出
    from PyQt5.QtCore import QTimer
    QTimer.singleShot(20000, lambda: (
        tester.stop(),
        app.quit(),
        print("\nHeadless test finished successfully!")
    ))

    return app.exec_()

if __name__ == "__main__":
    sys.exit(main())

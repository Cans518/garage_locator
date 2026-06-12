import time
import threading
from pathlib import Path
import cv2
import numpy as np

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QImage

from .inference import DetectionResult, VehiclePlateDetector
from .plate_utils import draw_text


def draw_annotations(img, results: list[DetectionResult]):
    """美观标注车牌和关键点"""
    for res in results:
        # 1. 绘制包围框
        cv2.polylines(img, [res.box], True, (255, 120, 0), 2)
        # 2. 绘制 4 个红色的关键点
        for pt in res.pts:
            cv2.circle(img, (int(pt[0]), int(pt[1])), 4, (0, 0, 255), -1)
        # 3. 绘制识别文字
        text = f"{res.text} ({res.confidence:.2f})"
        text_x = int(np.min(res.box[:, 0]))
        text_y = max(10, int(np.min(res.box[:, 1])) - 30)
        img = draw_text(img, text, (text_x, text_y), (0, 0, 255), 24)
    return img


class FrameBuffer:
    """槽位式高并发线程安全图像缓冲区"""
    def __init__(self):
        self.lock = threading.Lock()
        self.frames = {}          # {camera_id: frame}
        self.has_new_frame = threading.Event()

    def put(self, camera_id: int, frame: np.ndarray):
        with self.lock:
            self.frames[camera_id] = frame
        self.has_new_frame.set()

    def get_all(self) -> dict[int, np.ndarray]:
        with self.lock:
            res = dict(self.frames)
            self.frames.clear()
        self.has_new_frame.clear()
        return res


class CameraGrabber(QThread):
    """轻量摄像头采集线程，不占用 BPU，带断线自动恢复"""
    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

    def __init__(self, camera_id: int, source, frame_buffer: FrameBuffer):
        super().__init__()
        self.camera_id = camera_id
        self.source = source
        self.frame_buffer = frame_buffer
        self.running = True

    def run(self):
        print(f"CameraGrabber {self.camera_id} started for source {self.source}")
        
        # 尝试转换整数 ID (例如 "0" -> 0)
        source_val = self.source
        if isinstance(self.source, str) and self.source.isdigit():
            source_val = int(self.source)

        if isinstance(self.source, str):
            source_path = Path(self.source)
            if source_path.suffix.lower() in self.IMAGE_EXTENSIONS and source_path.exists():
                frame = cv2.imread(str(source_path))
                if frame is None:
                    print(f"Camera {self.camera_id} could not read image source: {self.source}")
                    return

                while self.running:
                    self.frame_buffer.put(self.camera_id, frame.copy())
                    self.msleep(1000)

                print(f"CameraGrabber {self.camera_id} stopped.")
                return

        cap = cv2.VideoCapture(source_val)
        while self.running:
            if not cap.isOpened():
                time.sleep(2.0)
                cap = cv2.VideoCapture(source_val)
                continue

            ok, frame = cap.read()
            if not ok:
                # 视频文件循环播放
                if isinstance(self.source, str) and Path(self.source).exists():
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    time.sleep(0.1)
                    continue
                else:
                    print(f"Camera {self.camera_id} disconnected, retrying...")
                    cap.release()
                    time.sleep(2.0)
                    continue

            # 将新图像帧放入对应的槽位
            self.frame_buffer.put(self.camera_id, frame)
            # 约控制在 30fps
            self.msleep(30)

        cap.release()
        print(f"CameraGrabber {self.camera_id} stopped.")

    def stop(self):
        self.running = False
        self.wait()


class InferenceWorker(QThread):
    """独立推理后台线程，串行消费多路画面槽位，保护 BPU 免受多线程冲突"""
    # 信号发送: (camera_id, 绘制好的帧, 检测结果列表, 单帧检测延迟ms)
    frame_processed = pyqtSignal(int, QImage, list, float)

    def __init__(self, frame_buffer: FrameBuffer, detector: VehiclePlateDetector):
        super().__init__()
        self.frame_buffer = frame_buffer
        self.detector = detector
        self.running = True

    def run(self):
        print("InferenceWorker Thread started.")
        while self.running:
            # 阻塞等待至少一路通道更新画面
            if not self.frame_buffer.has_new_frame.wait(timeout=0.2):
                continue

            # 取出所有通道的最鲜活跃图像
            tasks = self.frame_buffer.get_all()
            for camera_id, frame in tasks.items():
                if not self.running:
                    break

                try:
                    t0 = time.time()
                    results = self.detector.detect(frame)
                    latency = (time.time() - t0) * 1000
                except Exception as exc:
                    print(f"Inference error on camera {camera_id}: {exc}")
                    results = []
                    latency = 0.0

                # 绘制车牌与四角坐标
                try:
                    annotated_frame = draw_annotations(frame.copy(), results)
                except Exception:
                    annotated_frame = frame

                # 将最终画面和推理出的车牌数据安全投递回 GUI 主线程
                try:
                    rgb_img = cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB)
                    h, w, c = rgb_img.shape
                    qimg = QImage(rgb_img.data, w, h, c * w, QImage.Format_RGB888).copy()
                except Exception:
                    qimg = QImage()

                self.frame_processed.emit(camera_id, qimg, results, latency)

        print("InferenceWorker Thread stopped.")

    def stop(self):
        self.running = False
        self.wait()

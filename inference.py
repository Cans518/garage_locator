import sys
import os
import time
from pathlib import Path
from dataclasses import dataclass
import cv2
import numpy as np

# 将当前项目目录加入 sys.path 确保模块可直接加载
project_dir = Path(__file__).resolve().parent
if str(project_dir) not in sys.path:
    sys.path.insert(0, str(project_dir))

@dataclass
class DetectionResult:
    box: np.ndarray       # 车牌包围框 (4, 2)
    pts: np.ndarray       # 关键点 (4, 2)
    text: str             # 识别出的车牌文本
    confidence: float     # OCR 置信度
    crop: np.ndarray      # 车牌裁切图

# --- 车牌剪裁核心透视变换逻辑 (CPU 共享) ---

def order_points(pts):
    pts = np.asarray(pts, dtype="float32")
    if pts.shape[0] < 4:
        raise ValueError(f"Expected at least 4 points, got {pts.shape[0]}")
    pts = pts[:4]
    rect = np.zeros((4, 2), dtype="float32")
    sums = pts.sum(axis=1)
    rect[0] = pts[np.argmin(sums)]
    rect[2] = pts[np.argmax(sums)]
    diffs = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diffs)]
    rect[3] = pts[np.argmax(diffs)]
    return rect

def expand_points(pts, scale=1.06):
    pts = np.asarray(pts, dtype="float32")
    center = pts.mean(axis=0)
    return center + (pts - center) * float(scale)

def four_point_transform(image, pts, padding=8):
    rect = order_points(pts)
    tl, tr, br, bl = rect
    width_a = np.linalg.norm(br - bl)
    width_b = np.linalg.norm(tr - tl)
    max_width = max(1, int(max(width_a, width_b)))
    height_a = np.linalg.norm(tr - br)
    height_b = np.linalg.norm(tl - bl)
    max_height = max(1, int(max(height_a, height_b)))
    padding = max(0, int(padding))
    dst = np.array([
        [padding, padding],
        [max_width - 1 + padding, padding],
        [max_width - 1 + padding, max_height - 1 + padding],
        [padding, max_height - 1 + padding]
    ], dtype="float32")
    matrix = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(
        image,
        matrix,
        (max_width + 2 * padding, max_height + 2 * padding),
        borderMode=cv2.BORDER_REPLICATE
    )

def crop_plate(image, pts, crop_scale=1.0, crop_padding=0, min_crop_width=300):
    expanded = expand_points(pts, scale=crop_scale)
    crop = four_point_transform(image, expanded, padding=crop_padding)
    height, width = crop.shape[:2]
    if width > 0 and width < min_crop_width:
        scale = float(min_crop_width) / float(width)
        crop = cv2.resize(
            crop,
            (int(width * scale), int(height * scale)),
            interpolation=cv2.INTER_CUBIC
        )
    return crop


class VehiclePlateDetector:
    """推理后端抽象基类"""
    def detect(self, frame: np.ndarray) -> list[DetectionResult]:
        raise NotImplementedError


# --- PC 端推理后端 (YOLO + PaddleOCR) ---

class PCDetectionBackend(VehiclePlateDetector):
    def __init__(self, yolo_model_path: str):
        print("Initializing PC Inference Backend...")
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError("ultralytics is required for PC backend. Install with: pip install ultralytics") from exc
        
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise RuntimeError("paddleocr is required for PC backend. Install with: pip install paddlepaddle paddleocr") from exc

        self.yolo = YOLO(yolo_model_path)
        self.ocr = PaddleOCR(lang="ch", show_log=False)
        print("PC Inference Backend initialized successfully.")

    def detect(self, frame: np.ndarray) -> list[DetectionResult]:
        results = self.yolo(frame, verbose=False)
        output = []
        if not results:
            return output

        result = results[0]
        if result.keypoints is None:
            return output

        keypoints_array = result.keypoints.xy.cpu().numpy()
        boxes_array = result.boxes.xyxy.cpu().numpy()
        
        for idx, keypoints in enumerate(keypoints_array):
            if len(keypoints) < 4:
                continue
            pts = keypoints[:4]
            # 提取车牌包围矩形框
            box_xyxy = boxes_array[idx]
            box = np.array([
                [box_xyxy[0], box_xyxy[1]],
                [box_xyxy[2], box_xyxy[1]],
                [box_xyxy[2], box_xyxy[3]],
                [box_xyxy[0], box_xyxy[3]]
            ], dtype=np.int32)

            # 透视变换裁切车牌
            try:
                plate_img = crop_plate(frame, pts)
            except Exception:
                continue

            # 调用 PaddleOCR 进行识别
            try:
                ocr_res = self.ocr.ocr(plate_img, det=False, cls=False)
                if ocr_res and ocr_res[0]:
                    text, score = ocr_res[0][0]
                    score = float(score)
                else:
                    text, score = "", 0.0
            except Exception:
                text, score = "", 0.0

            # 清理非车牌字符
            import re
            cleaned_text = "".join(re.findall(r"[\u4e00-\u9fa5A-Z0-9]", text))

            output.append(DetectionResult(
                box=box,
                pts=pts.astype(np.int32),
                text=cleaned_text,
                confidence=score,
                crop=plate_img
            ))
        return output


# --- BPU 开发板端推理后端 (YOLO.bin + LPRNet.bin) ---

class BPUDetectionBackend(VehiclePlateDetector):
    def __init__(self, yolo_bin_path: str, lpr_bin_path: str):
        print("Initializing BPU Inference Backend...")
        try:
            import hbm_runtime
        except ImportError as exc:
            raise RuntimeError("hbm_runtime not found. Make sure you run on RDK development board.") from exc

        # 1. 初始化 BPU YOLO-pose 模型
        from ultralytics_yolo_pose import UltralyticsYOLOPose, UltralyticsYOLOPoseConfig
        cfg = UltralyticsYOLOPoseConfig(
            model_path=str(yolo_bin_path),
            nkpt=4,
            score_thres=0.25,
            nms_thres=0.70
        )
        self.yolo = UltralyticsYOLOPose(cfg)

        # 2. 初始化 BPU LPRNet 识别模型
        from detect_plate_rdk import LPRNetRecognizer
        self.lpr = LPRNetRecognizer(
            lpr_bin_path,
            input_color="rgb",
            input_mean=127.5,
            input_scale=0.007843137
        )
        print("BPU Inference Backend initialized successfully.")

    def detect(self, frame: np.ndarray) -> list[DetectionResult]:
        # YOLO 关键点与包围框 BPU 推理
        boxes, scores, kpts = self.yolo.predict(frame)
        output = []
        if len(kpts) == 0:
            return output

        for idx, pts_with_conf in enumerate(kpts):
            if len(pts_with_conf) < 4:
                continue
            pts = pts_with_conf[:, :2] # 提取关键点 x,y

            # 对应车牌的 bounding box
            b = boxes[idx]
            box = np.array([
                [b[0], b[1]],
                [b[2], b[1]],
                [b[2], b[3]],
                [b[0], b[3]]
            ], dtype=np.int32)

            # 透视变换裁切车牌
            try:
                plate_img = crop_plate(frame, pts)
            except Exception:
                continue

            # 调用 BPU LPRNet 进行识别
            try:
                text, score = self.lpr.recognize(plate_img)
            except Exception:
                text, score = "", 0.0

            # 过滤非车牌字符
            import re
            cleaned_text = "".join(re.findall(r"[\u4e00-\u9fa5A-Z0-9]", text))

            output.append(DetectionResult(
                box=box,
                pts=pts.astype(np.int32),
                text=cleaned_text,
                confidence=score,
                crop=plate_img
            ))
        return output

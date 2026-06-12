import sys
from pathlib import Path
from dataclasses import dataclass
import numpy as np

# 将当前项目目录加入 sys.path 确保模块可直接加载
project_dir = Path(__file__).resolve().parents[1]
if str(project_dir) not in sys.path:
    sys.path.insert(0, str(project_dir))

from .plate_utils import (  # noqa: E402
    clean_plate_number,
    crop_plate,
    expand_points,
    four_point_transform,
    order_points,
)

@dataclass
class DetectionResult:
    box: np.ndarray       # 车牌包围框 (4, 2)
    pts: np.ndarray       # 关键点 (4, 2)
    text: str             # 识别出的车牌文本
    confidence: float     # OCR 置信度
    crop: np.ndarray      # 车牌裁切图

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
        self.ocr = self._create_paddle_ocr(PaddleOCR)
        print("PC Inference Backend initialized successfully.")

    def _create_paddle_ocr(self, paddle_ocr_cls):
        """创建兼容 PaddleOCR 2.x/3.x 的中文 OCR 实例"""
        common_kwargs = {"lang": "ch"}

        # PaddleOCR 3.x 默认会启用文档方向和矫正模型；车牌裁切图不需要这些步骤。
        v3_lightweight_kwargs = {
            **common_kwargs,
            "use_doc_orientation_classify": False,
            "use_doc_unwarping": False,
            "use_textline_orientation": False,
        }
        try:
            return paddle_ocr_cls(**v3_lightweight_kwargs)
        except ValueError as exc:
            unknown_v3_arg = any(name in str(exc) for name in v3_lightweight_kwargs if name != "lang")
            if not unknown_v3_arg:
                raise

        try:
            return paddle_ocr_cls(lang="ch", show_log=False)
        except ValueError as exc:
            if "show_log" not in str(exc):
                raise
            return paddle_ocr_cls(**common_kwargs)

    def _recognize_plate_text(self, plate_img: np.ndarray) -> tuple[str, float]:
        """兼容 PaddleOCR 2.x 和 3.x 的返回格式"""
        try:
            if hasattr(self.ocr, "predict"):
                ocr_res = self.ocr.predict(plate_img)
            else:
                ocr_res = self.ocr.ocr(plate_img, det=False, cls=False)
        except Exception as exc:
            print(f"PaddleOCR recognize failed: {exc}")
            return "", 0.0

        if not ocr_res:
            return "", 0.0

        first_res = ocr_res[0]

        # PaddleOCR 3.x: OCRResult.res 通常包含 rec_texts / rec_scores。
        res_dict = getattr(first_res, "res", None)
        if isinstance(res_dict, dict):
            texts = res_dict.get("rec_texts") or []
            scores = res_dict.get("rec_scores") or []
            if texts:
                score = float(scores[0]) if scores else 0.0
                return str(texts[0]), score

        if isinstance(first_res, dict):
            texts = first_res.get("rec_texts") or []
            scores = first_res.get("rec_scores") or []
            if texts:
                score = float(scores[0]) if scores else 0.0
                return str(texts[0]), score

        # PaddleOCR 2.x det=False: [[("TEXT", score)]] 或相近嵌套结构。
        try:
            candidate = first_res[0]
            if isinstance(candidate, (list, tuple)) and len(candidate) >= 2:
                return str(candidate[0]), float(candidate[1])
        except Exception:
            pass

        print(f"Unexpected PaddleOCR result format: {type(first_res)}")
        return "", 0.0

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
            text, score = self._recognize_plate_text(plate_img)

            cleaned_text = clean_plate_number(text)

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
        from .ultralytics_yolo_pose import UltralyticsYOLOPose, UltralyticsYOLOPoseConfig
        cfg = UltralyticsYOLOPoseConfig(
            model_path=str(yolo_bin_path),
            nkpt=4,
            score_thres=0.25,
            nms_thres=0.70
        )
        self.yolo = UltralyticsYOLOPose(cfg)

        # 2. 初始化 BPU LPRNet 识别模型
        from .detect_plate_rdk import LPRNetRecognizer
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

            cleaned_text = clean_plate_number(text)

            output.append(DetectionResult(
                box=box,
                pts=pts.astype(np.int32),
                text=cleaned_text,
                confidence=score,
                crop=plate_img
            ))
        return output

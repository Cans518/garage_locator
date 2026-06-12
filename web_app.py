import argparse
import base64
import datetime
import json
import mimetypes
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import cv2
import numpy as np

from utils.db_manager import DBManager
from utils.inference import BPUDetectionBackend, PCDetectionBackend
from utils.plate_utils import draw_text


ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "web"
ASSETS_ROOT = ROOT / "assets"
DB_PATH = ROOT / "vehicle_locator.db"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
WEB_RUNTIME = None


def build_default_sources(limit=4):
    if not ASSETS_ROOT.exists():
        return []
    return [
        str(path)
        for path in sorted(ASSETS_ROOT.iterdir())
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    ][:limit]


def json_response(handler: BaseHTTPRequestHandler, payload, status=200):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def asset_images():
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    if not ASSETS_ROOT.exists():
        return []
    return [
        f"/assets/{path.name}"
        for path in sorted(ASSETS_ROOT.iterdir())
        if path.is_file() and path.suffix.lower() in exts
    ]


def encode_image_data_url(frame: np.ndarray, quality=82):
    if frame is None or frame.size == 0:
        return None
    ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        return None
    payload = base64.b64encode(encoded.tobytes()).decode("ascii")
    return f"data:image/jpeg;base64,{payload}"


def draw_annotations(frame: np.ndarray, results):
    annotated = frame.copy()
    for result in results:
        try:
            cv2.polylines(annotated, [result.box], True, (6, 182, 212), 2)
            for point in result.pts:
                cv2.circle(annotated, (int(point[0]), int(point[1])), 4, (16, 185, 129), -1)
            label = f"{result.text} {result.confidence:.2f}"
            x = int(np.min(result.box[:, 0]))
            y = max(12, int(np.min(result.box[:, 1])) - 30)
            annotated = draw_text(annotated, label, (x, y), (0, 90, 180), 24)
        except Exception:
            continue
    return annotated


class LatestFrameBuffer:
    def __init__(self):
        self.lock = threading.Lock()
        self.frames = {}
        self.has_new_frame = threading.Event()

    def put(self, camera_id: int, frame: np.ndarray):
        with self.lock:
            self.frames[camera_id] = frame
        self.has_new_frame.set()

    def get_all(self):
        with self.lock:
            frames = dict(self.frames)
            self.frames.clear()
        self.has_new_frame.clear()
        return frames


class CameraCaptureThread(threading.Thread):
    def __init__(self, camera_id: int, source, frame_buffer: LatestFrameBuffer, stop_event: threading.Event):
        super().__init__(daemon=True)
        self.camera_id = camera_id
        self.source = source
        self.frame_buffer = frame_buffer
        self.stop_event = stop_event

    def run(self):
        source_value = self.source
        if isinstance(source_value, str) and source_value.isdigit():
            source_value = int(source_value)

        if isinstance(self.source, str):
            source_path = Path(self.source)
            if source_path.suffix.lower() in IMAGE_EXTENSIONS and source_path.exists():
                frame = cv2.imread(str(source_path))
                if frame is None:
                    return
                while not self.stop_event.is_set():
                    self.frame_buffer.put(self.camera_id, frame.copy())
                    time.sleep(1.0)
                return

        cap = cv2.VideoCapture(source_value)
        while not self.stop_event.is_set():
            if not cap.isOpened():
                time.sleep(2.0)
                cap = cv2.VideoCapture(source_value)
                continue

            ok, frame = cap.read()
            if not ok:
                if isinstance(self.source, str) and Path(self.source).exists():
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    time.sleep(0.1)
                    continue
                cap.release()
                time.sleep(2.0)
                cap = cv2.VideoCapture(source_value)
                continue

            self.frame_buffer.put(self.camera_id, frame)
            time.sleep(0.03)

        cap.release()


class WebInferenceRuntime:
    def __init__(self, detector, db: DBManager, sources):
        self.detector = detector
        self.db = db
        self.sources = sources
        self.frame_buffer = LatestFrameBuffer()
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.camera_frames = {}
        self.events = []
        self.latency_by_camera = {}
        self.errors = []
        self.capture_threads = []
        self.inference_thread = None

    def start(self):
        for camera_id, source in enumerate(self.sources):
            if source is None:
                continue
            thread = CameraCaptureThread(camera_id, source, self.frame_buffer, self.stop_event)
            thread.start()
            self.capture_threads.append(thread)

        self.inference_thread = threading.Thread(target=self._run_inference, daemon=True)
        self.inference_thread.start()

    def stop(self):
        self.stop_event.set()
        self.frame_buffer.has_new_frame.set()

    def _run_inference(self):
        while not self.stop_event.is_set():
            if not self.frame_buffer.has_new_frame.wait(timeout=0.2):
                continue

            tasks = self.frame_buffer.get_all()
            for camera_id, frame in tasks.items():
                if self.stop_event.is_set():
                    break

                try:
                    started = time.time()
                    results = self.detector.detect(frame)
                    latency = (time.time() - started) * 1000
                except Exception as exc:
                    results = []
                    latency = 0.0
                    with self.lock:
                        self.errors.append(str(exc))
                        self.errors = self.errors[-20:]

                annotated = draw_annotations(frame, results)
                frame_url = encode_image_data_url(annotated)

                with self.lock:
                    self.camera_frames[camera_id + 1] = frame_url
                    self.latency_by_camera[camera_id + 1] = latency

                for result in results:
                    if not result.text or len(result.text) < 4:
                        continue

                    self.db.record_occurrence(result.text, camera_id + 1, result.crop)
                    event = {
                        "plateNumber": result.text,
                        "cameraId": camera_id + 1,
                        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "latency": round(latency, 1),
                        "confidence": round(float(result.confidence or 0.0), 3),
                    }
                    with self.lock:
                        self.events.insert(0, event)
                        self.events = self.events[:100]

    def snapshot(self):
        with self.lock:
            frames = dict(self.camera_frames)
            events = list(self.events)
            latency = dict(self.latency_by_camera)
            errors = list(self.errors)

        return {
            "cameraImages": [
                frames.get(camera_id)
                for camera_id in range(1, 5)
                if frames.get(camera_id)
            ],
            "events": events,
            "latency": latency,
            "errors": errors,
            "running": not self.stop_event.is_set(),
        }


def query_last_location(plate_number: str):
    if not DB_PATH.exists() or not plate_number:
        return None

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT camera_id, timestamp, crop_image
            FROM vehicle_history
            WHERE plate_number = ?
            ORDER BY timestamp DESC, id DESC
            LIMIT 1
            """,
            (plate_number,),
        )
        row = cursor.fetchone()

    if not row:
        return None

    camera_id, timestamp, crop_blob = row
    crop_data_url = None
    if crop_blob:
        encoded = base64.b64encode(crop_blob).decode("ascii")
        crop_data_url = f"data:image/jpeg;base64,{encoded}"

    return {
        "plateNumber": plate_number,
        "cameraId": camera_id,
        "timestamp": timestamp,
        "cropImage": crop_data_url,
    }


def query_fuzzy(plate_number: str):
    if not DB_PATH.exists() or not plate_number:
        return []

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT vh.plate_number, vh.camera_id, vh.timestamp
            FROM vehicle_history vh
            INNER JOIN (
                SELECT plate_number, MAX(id) AS latest_id
                FROM vehicle_history
                WHERE plate_number LIKE ?
                GROUP BY plate_number
            ) latest
                ON vh.plate_number = latest.plate_number
                AND vh.id = latest.latest_id
            ORDER BY vh.timestamp DESC, vh.id DESC
            LIMIT 6
            """,
            (f"%{plate_number}%",),
        )
        rows = cursor.fetchall()

    return [
        {"plateNumber": row[0], "cameraId": row[1], "timestamp": row[2]}
        for row in rows
    ]


def recent_events(limit=12):
    if not DB_PATH.exists():
        return []

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT plate_number, camera_id, timestamp
            FROM vehicle_history
            ORDER BY timestamp DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cursor.fetchall()

    return [
        {"plateNumber": row[0], "cameraId": row[1], "timestamp": row[2]}
        for row in rows
    ]


class GarageWebHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            self.serve_file(WEB_ROOT / "index.html")
            return

        if path == "/api/search":
            params = parse_qs(parsed.query)
            plate = params.get("plate", [""])[0].strip().upper()
            result = query_last_location(plate)
            json_response(
                self,
                {
                    "ok": bool(result),
                    "query": plate,
                    "result": result,
                    "suggestions": [] if result else query_fuzzy(plate),
                },
            )
            return

        if path == "/api/events":
            runtime_snapshot = WEB_RUNTIME.snapshot() if WEB_RUNTIME else None
            runtime_events = runtime_snapshot["events"] if runtime_snapshot else []
            runtime_images = runtime_snapshot["cameraImages"] if runtime_snapshot else []
            json_response(
                self,
                {
                    "events": runtime_events or recent_events(),
                    "cameraImages": runtime_images or asset_images()[:4],
                    "stats": {
                        "channels": 4,
                        "records": len(runtime_events) if runtime_events else len(recent_events(100)),
                        "status": "online" if runtime_snapshot and runtime_snapshot["running"] else "database",
                    },
                    "latency": runtime_snapshot["latency"] if runtime_snapshot else {},
                    "errors": runtime_snapshot["errors"] if runtime_snapshot else [],
                },
            )
            return

        if path.startswith("/assets/"):
            self.serve_file(ASSETS_ROOT / path.removeprefix("/assets/"))
            return

        if path.startswith("/web/"):
            self.serve_file(WEB_ROOT / path.removeprefix("/web/"))
            return

        self.send_error(404)

    def serve_file(self, file_path: Path):
        try:
            resolved = file_path.resolve()
        except FileNotFoundError:
            self.send_error(404)
            return

        allowed_roots = (WEB_ROOT.resolve(), ASSETS_ROOT.resolve())
        if not any(str(resolved).startswith(str(root)) for root in allowed_roots):
            self.send_error(403)
            return

        if not resolved.exists() or not resolved.is_file():
            self.send_error(404)
            return

        content_type, _ = mimetypes.guess_type(str(resolved))
        body = resolved.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def add_inference_arguments(parser: argparse.ArgumentParser):
    parser.add_argument(
        "--backend", choices=("pc", "bpu", "none"), default="pc",
        help="推理后端；none 只启动 Web 查询和数据库展示"
    )
    parser.add_argument(
        "--inputs", nargs="+", default=[],
        help="指定摄像头/视频/图片输入源，最多 4 路；为空时默认读取 assets 中的测试图片"
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


def start_web_runtime(args):
    global WEB_RUNTIME

    if args.backend == "none":
        WEB_RUNTIME = None
        return None

    input_list = args.inputs if args.inputs else build_default_sources(limit=4)
    sources = [None] * 4
    for index, source in enumerate(input_list[:4]):
        sources[index] = source

    if args.backend == "bpu":
        detector = BPUDetectionBackend(args.yolo_bin, args.lpr_bin)
    else:
        detector = PCDetectionBackend(args.yolo_model)

    WEB_RUNTIME = WebInferenceRuntime(detector, DBManager(str(DB_PATH)), sources)
    WEB_RUNTIME.start()
    print("Web inference runtime started.")
    return WEB_RUNTIME


def main():
    parser = argparse.ArgumentParser(description="地库车辆定位系统 Web 控制台")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8080, type=int)
    add_inference_arguments(parser)
    args = parser.parse_args()

    runtime = start_web_runtime(args)

    server = ThreadingHTTPServer((args.host, args.port), GarageWebHandler)
    print(f"Garage Locator Web is running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    finally:
        if runtime:
            runtime.stop()


if __name__ == "__main__":
    main()

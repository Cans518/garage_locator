import os
import re
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp"}
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}
DEFAULT_YOLO_MODEL = "models/yolo11m-pose-carplate.pt"
DEFAULT_RDK_REC_MODEL = "models/lpr.bin"


def load_yolo_model(model_path):
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError("Ultralytics is not installed. Install it with: pip install ultralytics") from exc
    return YOLO(str(model_path))


def order_points(pts):
    """Return points ordered as top-left, top-right, bottom-right, bottom-left."""
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
    """Expand points outwards from their center to keep plate edges in the crop."""
    pts = np.asarray(pts, dtype="float32")
    center = pts.mean(axis=0)
    return center + (pts - center) * float(scale)


def four_point_transform(image, pts, padding=8):
    """Warp a quadrilateral plate region to a front-facing crop."""
    rect = order_points(pts)
    tl, tr, br, bl = rect

    width_a = np.linalg.norm(br - bl)
    width_b = np.linalg.norm(tr - tl)
    max_width = max(1, int(max(width_a, width_b)))

    height_a = np.linalg.norm(tr - br)
    height_b = np.linalg.norm(tl - bl)
    max_height = max(1, int(max(height_a, height_b)))

    padding = max(0, int(padding))
    dst = np.array(
        [
            [padding, padding],
            [max_width - 1 + padding, padding],
            [max_width - 1 + padding, max_height - 1 + padding],
            [padding, max_height - 1 + padding],
        ],
        dtype="float32",
    )

    matrix = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(
        image,
        matrix,
        (max_width + 2 * padding, max_height + 2 * padding),
        borderMode=cv2.BORDER_REPLICATE,
    )


def crop_plate(image, pts, crop_scale=1.0, crop_padding=0, min_crop_width=300):
    """Expand, warp, and optionally upscale a detected plate region."""
    expanded = expand_points(pts, scale=crop_scale)
    crop = four_point_transform(image, expanded, padding=crop_padding)

    height, width = crop.shape[:2]
    if width > 0 and width < min_crop_width:
        scale = float(min_crop_width) / float(width)
        crop = cv2.resize(
            crop,
            (int(width * scale), int(height * scale)),
            interpolation=cv2.INTER_CUBIC,
        )
    return crop


@lru_cache(maxsize=8)
def _load_font(text_size):
    font_paths = [
        "simhei.ttf",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/msyh.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc",
    ]

    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, int(text_size), encoding="utf-8")
            except OSError:
                continue
    return ImageFont.load_default()


def draw_text(img, text, position, text_color=(255, 0, 0), text_size=30):
    """Draw UTF-8 text on an OpenCV BGR image."""
    if isinstance(img, np.ndarray):
        img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    else:
        img_pil = img

    draw = ImageDraw.Draw(img_pil)
    draw.text(position, str(text), fill=text_color, font=_load_font(text_size))
    return cv2.cvtColor(np.asarray(img_pil), cv2.COLOR_RGB2BGR)


def clean_plate_number(text):
    """Keep Chinese characters, capital letters, and numbers from OCR output."""
    if text is None:
        return ""
    text = re.sub(r"[\s\-\+\*\.\\_·]", "", str(text)).upper()
    return "".join(re.findall(r"[\u4e00-\u9fa5A-Z0-9]", text))


def iter_plate_keypoints(results):
    """Yield the first 4 pose keypoints for each YOLO result."""
    for result in results:
        if result.keypoints is None:
            continue
        keypoints_array = result.keypoints.xy.cpu().numpy()
        for keypoints in keypoints_array:
            if len(keypoints) >= 4:
                yield keypoints[:4]


def draw_plate_annotation(img, pts, label):
    for x, y in pts:
        cv2.circle(img, (int(x), int(y)), 3, (0, 0, 255), -1)

    pts_int = np.asarray(pts, dtype=np.int32).reshape((-1, 1, 2))
    cv2.polylines(img, [pts_int], True, (255, 0, 0), 2)

    text_x = int(np.min(pts[:, 0]))
    text_y = max(10, int(np.min(pts[:, 1])) - 35)
    return draw_text(img, label, (text_x, text_y), (255, 0, 0), 32)


def should_show_window(no_show):
    return not no_show and (os.name == "nt" or bool(os.environ.get("DISPLAY")))


def ensure_dir(path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def iter_image_files(directory):
    directory = Path(directory)
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def default_output_dir_for(source):
    source = Path(str(source))
    if source.is_dir():
        return source / "output_results"
    return Path(".")


def prefixed_output_path(input_path, output_dir, prefix="output_"):
    input_path = Path(input_path)
    return ensure_dir(output_dir) / f"{prefix}{input_path.name}"


def read_image(path, flags=cv2.IMREAD_COLOR):
    path = Path(path)
    try:
        data = np.fromfile(str(path), dtype=np.uint8)
    except OSError:
        return None
    if data.size == 0:
        return None
    return cv2.imdecode(data, flags)


def save_image(path, image):
    path = Path(path)
    ensure_dir(path.parent)
    extension = path.suffix or ".jpg"
    ok, encoded = cv2.imencode(extension, image)
    if not ok:
        raise RuntimeError(f"Failed to write image: {path}")
    encoded.tofile(str(path))
    return path


def save_plate_crop(crop, crop_dir, source_name, plate_index, frame_index=None):
    crop_dir = ensure_dir(crop_dir)
    stem = Path(str(source_name)).stem or "frame"
    frame_part = f"_f{frame_index:06d}" if frame_index is not None else ""
    crop_path = crop_dir / f"{stem}{frame_part}_plate{plate_index}.jpg"
    save_image(crop_path, crop)
    return crop_path


def resolve_repo_path(path):
    path = Path(path)
    if path.is_absolute() or path.exists():
        return path

    repo_path = Path(__file__).resolve().parent / path
    if repo_path.exists():
        return repo_path
    return path


def parse_source(source):
    if isinstance(source, int):
        return source, True
    source_text = str(source)
    if source_text.isdigit():
        return int(source_text), True
    return source_text, False

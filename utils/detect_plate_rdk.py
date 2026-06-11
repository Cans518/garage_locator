import sys
import os
from pathlib import Path

import cv2
import numpy as np

# 将 rdk_model_zoo 根目录和 pose python 运行时目录加入 sys.path
repo_dir = Path(__file__).resolve().parents[1]
sys.path.append(str(repo_dir))
sys.path.append(str(repo_dir / "samples" / "vision" / "ultralytics_yolo" / "runtime" / "python"))

import argparse

from utils.plate_utils import (
    DEFAULT_RDK_REC_MODEL,
    DEFAULT_YOLO_MODEL,
    VIDEO_EXTENSIONS,
    clean_plate_number,
    crop_plate,
    default_output_dir_for,
    draw_plate_annotation,
    iter_image_files,
    iter_plate_keypoints,
    load_yolo_model,
    parse_source,
    prefixed_output_path,
    read_image,
    resolve_repo_path,
    save_image,
    save_plate_crop,
    should_show_window,
)



LPRNET_INPUT_SHAPE = (1, 3, 24, 94)
LPRNET_NUM_CLASSES = 68

CHARS = [
    "京",
    "沪",
    "津",
    "渝",
    "冀",
    "晋",
    "蒙",
    "辽",
    "吉",
    "黑",
    "苏",
    "浙",
    "皖",
    "闽",
    "赣",
    "鲁",
    "豫",
    "鄂",
    "湘",
    "粤",
    "桂",
    "琼",
    "川",
    "贵",
    "云",
    "藏",
    "陕",
    "甘",
    "青",
    "宁",
    "新",
    "0",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "A",
    "B",
    "C",
    "D",
    "E",
    "F",
    "G",
    "H",
    "J",
    "K",
    "L",
    "M",
    "N",
    "P",
    "Q",
    "R",
    "S",
    "T",
    "U",
    "V",
    "W",
    "X",
    "Y",
    "Z",
    "I",
    "O",
    "-",
]


def _tensor_shape(metadata, model_name, tensor_name, fallback):
    if metadata is None:
        return fallback

    model_metadata = metadata.get(model_name, metadata) if isinstance(metadata, dict) else metadata
    if isinstance(model_metadata, dict):
        shape = model_metadata.get(tensor_name, fallback)
    elif isinstance(model_metadata, (list, tuple)) and model_metadata:
        first = model_metadata[0]
        shape = model_metadata if isinstance(first, (int, np.integer)) else first
    else:
        shape = fallback

    try:
        return tuple(int(value) for value in shape)
    except TypeError:
        return fallback


def _resolve_input_layout(input_shape):
    if len(input_shape) != 4:
        raise ValueError(f"LPRNet expects a 4D input tensor, got shape {input_shape}")

    if input_shape[1] in (1, 3):
        return "nchw", input_shape[1], input_shape[2], input_shape[3]
    if input_shape[3] in (1, 3):
        return "nhwc", input_shape[3], input_shape[1], input_shape[2]

    raise ValueError(f"Could not infer image layout from LPRNet input shape {input_shape}")


def _prepare_plate_image(plate_crop, target_width, target_height, channels, input_color):
    if plate_crop is None or plate_crop.size == 0:
        raise ValueError("Empty plate crop")

    image = plate_crop
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    elif image.shape[2] == 4:
        image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)

    image = cv2.resize(image, (target_width, target_height), interpolation=cv2.INTER_LINEAR)

    if channels == 1:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)[:, :, None]

    if input_color == "rgb":
        return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    return image


def preprocess_lprnet_input(
    plate_crop,
    input_shape=LPRNET_INPUT_SHAPE,
    input_color="rgb",
    input_mean=0.0,
    input_scale=1.0,
):
    layout, channels, target_height, target_width = _resolve_input_layout(input_shape)
    image = _prepare_plate_image(plate_crop, target_width, target_height, channels, input_color)

    tensor = image.astype(np.float32)
    if input_mean:
        tensor -= float(input_mean)
    if input_scale != 1.0:
        tensor *= float(input_scale)

    if layout == "nchw":
        tensor = tensor.transpose(2, 0, 1)[None, ...]
    else:
        tensor = tensor[None, ...]

    return np.ascontiguousarray(tensor, dtype=np.float32)


def _class_time_logits(logits):
    data = np.asarray(logits, dtype=np.float32).squeeze()
    if data.ndim != 2:
        raise ValueError(f"LPRNet output should squeeze to 2D, got shape {data.shape}")

    if data.shape[0] == LPRNET_NUM_CLASSES:
        return data
    if data.shape[1] == LPRNET_NUM_CLASSES:
        return data.T

    raise ValueError(f"LPRNet output must contain {LPRNET_NUM_CLASSES} classes, got {data.shape}")


def _softmax(values, axis=0):
    shifted = values - np.max(values, axis=axis, keepdims=True)
    exp_values = np.exp(shifted)
    return exp_values / np.sum(exp_values, axis=axis, keepdims=True)


def decode_lprnet(logits):
    class_time = _class_time_logits(logits)
    pred_labels = np.argmax(class_time, axis=0)
    if pred_labels.size == 0:
        return "", 0.0

    blank_index = len(CHARS) - 1
    decoded_indexes = []
    decoded_steps = []
    previous = None

    for step, current in enumerate(pred_labels):
        current = int(current)
        if current == blank_index:
            previous = current
            continue
        if current == previous:
            continue

        decoded_indexes.append(current)
        decoded_steps.append(step)
        previous = current

    text = "".join(CHARS[index] for index in decoded_indexes)
    if not decoded_steps:
        return text, 0.0

    probs = _softmax(class_time, axis=0)
    confidence = float(np.mean([probs[index, step] for index, step in zip(decoded_indexes, decoded_steps)]))
    return text, confidence


class LPRNetRecognizer:
    def __init__(
        self,
        model_path,
        priority=5,
        bpu_cores=None,
        input_color="rgb",
        input_mean=0.0,
        input_scale=1.0,
    ):
        try:
            import hbm_runtime
        except ImportError as exc:
            raise RuntimeError(
                "hbm_runtime is not available. Run this script on RDK OS >= 3.5.0 "
                "or install the D-Robotics runtime package on the board."
            ) from exc

        self.runtime = hbm_runtime.HB_HBMRuntime(str(model_path))
        self.model_name = self.runtime.model_names[0]
        self.input_name = self.runtime.input_names[self.model_name][0]
        self.output_name = self.runtime.output_names[self.model_name][0]
        self.input_shape = _tensor_shape(
            getattr(self.runtime, "input_shapes", None),
            self.model_name,
            self.input_name,
            LPRNET_INPUT_SHAPE,
        )
        self.input_color = input_color
        self.input_mean = input_mean
        self.input_scale = input_scale

        self.set_scheduling_params(priority=priority, bpu_cores=bpu_cores)

    def set_scheduling_params(self, priority=None, bpu_cores=None):
        kwargs = {}
        if priority is not None:
            kwargs["priority"] = {self.model_name: int(priority)}
        if bpu_cores is not None:
            kwargs["bpu_cores"] = {self.model_name: [int(core) for core in bpu_cores]}
        if kwargs:
            self.runtime.set_scheduling_params(**kwargs)

    def _input_dict(self, tensor):
        return {self.model_name: {self.input_name: tensor}}

    def recognize(self, plate_crop):
        import time
        import logging
        t0 = time.time()
        tensor = preprocess_lprnet_input(
            plate_crop,
            input_shape=self.input_shape,
            input_color=self.input_color,
            input_mean=self.input_mean,
            input_scale=self.input_scale,
        )
        t1 = time.time()
        outputs = self.runtime.run(self._input_dict(tensor))
        t2 = time.time()
        logits = outputs[self.model_name][self.output_name]
        result = decode_lprnet(logits)
        t3 = time.time()

        logger = logging.getLogger("LPRNet")
        logger.info("\033[1;32mLPRNet Pre-process = %.2f ms | Forward = %.2f ms | Post-process = %.2f ms\033[0m", 
                    1000 * (t1 - t0), 1000 * (t2 - t1), 1000 * (t3 - t2))
        return result


def process_frame(img, yolo_model, recognizer, args, source_name="frame", frame_index=None, is_bpu_yolo=False):
    clean_img = img.copy()
    plate_found = False

    if is_bpu_yolo:
        boxes, scores, kpts = yolo_model.predict(img)
        iterator = (pts[:, :2] for pts in kpts if len(pts) >= 4)
    else:
        results = yolo_model(img, conf=args.conf, verbose=False)
        iterator = iter_plate_keypoints(results)

    for plate_index, pts in enumerate(iterator):
        plate_found = True

        try:
            plate_crop = crop_plate(
                clean_img,
                pts,
                crop_scale=args.crop_scale,
                crop_padding=args.crop_padding,
                min_crop_width=args.min_crop_width,
            )
        except Exception as exc:
            print(f"Error warping perspective for plate {plate_index}: {exc}")
            continue

        if args.save_crops:
            save_plate_crop(
                plate_crop,
                args.crop_dir,
                source_name,
                plate_index,
                frame_index=frame_index,
            )

        try:
            raw_text, confidence = recognizer.recognize(plate_crop)
        except Exception as exc:
            print(f"LPRNet inference error for plate {plate_index}: {exc}")
            raw_text, confidence = "", 0.0

        detected_text = clean_plate_number(raw_text)
        if not args.quiet:
            print(
                f"Plate {plate_index}: {detected_text or '<empty>'} "
                f"(raw={raw_text!r}, conf={confidence:.2f})"
            )

        label = f"{detected_text} ({confidence:.2f})"
        img = draw_plate_annotation(img, pts, label)

    return img, plate_found


def process_image(img_path, yolo_model, recognizer, args, is_bpu_yolo=False):
    img_path = Path(img_path)
    img = read_image(img_path)
    if img is None:
        print(f"Error: could not read image: {img_path}")
        return None

    print(f"Running detection on image {img_path}...")
    img_out, plate_found = process_frame(img, yolo_model, recognizer, args, source_name=img_path, is_bpu_yolo=is_bpu_yolo)

    if not plate_found:
        print("No license plate corners detected.")

    if should_show_window(args.no_show):
        cv2.imshow("License Plate Recognition", img_out)
        print("Press any key in the window to exit...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        return None

    output_path = prefixed_output_path(img_path, args.output_dir, prefix=args.output_prefix)
    save_image(output_path, img_out)
    print(f"Output saved to {output_path}")
    return output_path


def process_directory(dir_path, yolo_model, recognizer, args, is_bpu_yolo=False):
    dir_path = Path(dir_path)
    files = iter_image_files(dir_path)

    if not files:
        print(f"No valid images found in {dir_path}")
        return

    print(f"Processing {len(files)} images in {dir_path}...")
    for img_path in files:
        img = read_image(img_path)
        if img is None:
            print(f"Skipping unreadable image: {img_path}")
            continue

        print(f"\nProcessing file: {img_path.name}")
        img_out, _ = process_frame(img, yolo_model, recognizer, args, source_name=img_path, is_bpu_yolo=is_bpu_yolo)

        output_path = prefixed_output_path(
            img_path,
            args.output_dir,
            prefix=args.output_prefix,
        )
        save_image(output_path, img_out)

    print(f"\nBatch processing completed. Results saved to {args.output_dir}")


def process_video(video_source, yolo_model, recognizer, args, is_bpu_yolo=False):
    cap = cv2.VideoCapture(video_source)
    if not cap.isOpened():
        print(f"Error: could not open video source: {video_source}")
        return

    writer = None
    if isinstance(video_source, str):
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        if fps <= 0:
            fps = 25.0

        output_path = prefixed_output_path(
            video_source,
            args.output_dir,
            prefix=args.output_prefix,
        )
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
        print(f"Saving processed video to {output_path}...")

    if should_show_window(args.no_show):
        print("Processing video stream. Press 'q' in the window to quit...")
    else:
        print("Processing video stream...")

    frame_count = 0
    while cap.isOpened():
        ok, frame = cap.read()
        if not ok:
            break

        frame_count += 1
        frame_out, _ = process_frame(
            frame,
            yolo_model,
            recognizer,
            args,
            source_name=video_source,
            frame_index=frame_count,
            is_bpu_yolo=is_bpu_yolo,
        )

        if writer is not None:
            writer.write(frame_out)

        if should_show_window(args.no_show):
            cv2.imshow("License Plate Recognition (Video)", frame_out)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
        elif frame_count % 10 == 0:
            print(f"Processed {frame_count} frames...")

    cap.release()
    if writer is not None:
        writer.release()
    if should_show_window(args.no_show):
        cv2.destroyAllWindows()
    print("Video processing finished.")


def build_parser():
    parser = argparse.ArgumentParser(
        description="License plate detection and RDK LPRNet recognition"
    )
    parser.add_argument(
        "input_source",
        help="Path to image, directory, video file, or camera ID such as 0",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_YOLO_MODEL,
        help="Path to the trained YOLO pose model",
    )
    parser.add_argument(
        "--rec-model",
        default=DEFAULT_RDK_REC_MODEL,
        help="Path to the RDK LPRNet BPU model",
    )
    parser.add_argument("--priority", type=int, default=5, help="hbm_runtime scheduling priority")
    parser.add_argument(
        "--bpu-cores",
        nargs="+",
        type=int,
        default=[0],
        help="BPU core indexes for hbm_runtime",
    )
    parser.add_argument(
        "--input-color",
        choices=("rgb", "bgr"),
        default="rgb",
        help="Color order used when packing LPRNet input tensors",
    )
    parser.add_argument(
        "--input-mean",
        type=float,
        default=127.5,
        help="Mean subtracted from LPRNet input pixels after resize",
    )
    parser.add_argument(
        "--input-scale",
        type=float,
        default=0.007843137,
        help="Scale multiplied into LPRNet input pixels after mean subtraction",
    )
    parser.add_argument("--output-dir", help="Directory for annotated outputs")
    parser.add_argument("--output-prefix", default="output_", help="Output filename prefix")
    parser.add_argument("--conf", type=float, default=0.25, help="YOLO confidence threshold")
    parser.add_argument("--nms-thres", type=float, default=0.70, help="YOLO NMS IoU threshold")
    parser.add_argument("--crop-scale", type=float, default=1.0, help="Scale plate corners outward")
    parser.add_argument("--crop-padding", type=int, default=0, help="Padding around warped plate crop")
    parser.add_argument("--min-crop-width", type=int, default=300, help="Upscale crops below this width")
    parser.add_argument("--save-crops", action="store_true", help="Save warped plate crops for debugging")
    parser.add_argument("--crop-dir", help="Directory for saved plate crops")
    parser.add_argument("--no-show", action="store_true", help="Do not display result windows")
    parser.add_argument("--quiet", action="store_true", help="Reduce per-plate logging")
    return parser


def main():
    import logging
    logging.basicConfig(level=logging.INFO)
    parser = build_parser()
    args = parser.parse_args()

    source, is_camera = parse_source(args.input_source)
    source_path = None if is_camera else resolve_repo_path(source)
    if not is_camera and not source_path.exists():
        print(f"Error: input source not found: {source}")
        return 1

    args.output_dir = Path(args.output_dir) if args.output_dir else default_output_dir_for(source_path or ".")
    args.crop_dir = Path(args.crop_dir) if args.crop_dir else Path(args.output_dir) / "plate_crops"
    args.model = resolve_repo_path(args.model)
    args.rec_model = resolve_repo_path(args.rec_model)
    if not args.model.exists():
        print(f"Error: YOLO model file not found: {args.model}")
        return 1
    if not args.rec_model.exists():
        print(f"Error: RDK LPRNet model file not found: {args.rec_model}")
        return 1

    print(f"Loading YOLO model from {args.model}...")
    try:
        if args.model.suffix == ".bin":
            from utils.ultralytics_yolo_pose import UltralyticsYOLOPose, UltralyticsYOLOPoseConfig
            cfg = UltralyticsYOLOPoseConfig(
                model_path=str(args.model),
                nkpt=4,
                score_thres=args.conf,
                nms_thres=args.nms_thres,
            )
            yolo_model = UltralyticsYOLOPose(cfg)
            is_bpu_yolo = True
        else:
            yolo_model = load_yolo_model(args.model)
            is_bpu_yolo = False
    except Exception as exc:
        print(f"Error loading YOLO model: {exc}")
        return 1

    print(f"Initializing RDK LPRNet recognizer from {args.rec_model}...")
    try:
        recognizer = LPRNetRecognizer(
            args.rec_model,
            priority=args.priority,
            bpu_cores=args.bpu_cores,
            input_color=args.input_color,
            input_mean=args.input_mean,
            input_scale=args.input_scale,
        )
    except Exception as exc:
        print(f"Error initializing RDK LPRNet recognizer: {exc}")
        return 1

    if is_camera:
        process_video(source, yolo_model, recognizer, args, is_bpu_yolo=is_bpu_yolo)
    elif source_path.is_dir():
        process_directory(source_path, yolo_model, recognizer, args, is_bpu_yolo=is_bpu_yolo)
    elif source_path.suffix.lower() in VIDEO_EXTENSIONS:
        process_video(str(source_path), yolo_model, recognizer, args, is_bpu_yolo=is_bpu_yolo)
    else:
        process_image(source_path, yolo_model, recognizer, args, is_bpu_yolo=is_bpu_yolo)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

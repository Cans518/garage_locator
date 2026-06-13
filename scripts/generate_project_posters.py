from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports"
POSTER_DIR = REPORT_DIR / "posters"
ASSET_DIR = POSTER_DIR / "assets"
PORTRAIT_BG = ASSET_DIR / "garage_locator_bg_9x16_image2.png"
LANDSCAPE_BG = ASSET_DIR / "garage_locator_bg_16x9_image2.png"
PORTRAIT_OUT = POSTER_DIR / "竖版海报_精排版.png"
LANDSCAPE_OUT = POSTER_DIR / "横版海报_精排版.png"


COLORS = {
    "ink": (9, 22, 45),
    "text": (32, 47, 74),
    "muted": (84, 104, 135),
    "white": (245, 251, 255),
    "cyan": (34, 211, 238),
    "blue": (59, 130, 246),
    "green": (52, 211, 153),
    "amber": (251, 191, 36),
    "purple": (168, 85, 247),
}


def font_path(bold: bool = False) -> str:
    candidates = [
        Path(r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
        Path(r"C:\Windows\Fonts\simsun.ttc"),
        Path(r"C:\Windows\Fonts\arial.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    return ""


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = font_path(bold)
    if path:
        return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def cover_resize(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_w, target_h = size
    src_w, src_h = image.size
    scale = max(target_w / src_w, target_h / src_h)
    resized = image.resize((int(src_w * scale), int(src_h * scale)), Image.Resampling.LANCZOS)
    left = (resized.width - target_w) // 2
    top = (resized.height - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def text_width(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


def wrap_line(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    if not text:
        return [""]
    lines: list[str] = []
    current = ""
    for char in text:
        candidate = current + char
        if current and text_width(draw, candidate, font) > max_width:
            lines.append(current)
            current = char
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def draw_wrapped(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font,
    fill: tuple[int, int, int],
    max_width: int,
    line_gap: int = 8,
) -> int:
    x, y = xy
    line_height = font.size + line_gap
    for raw in text.split("\n"):
        for line in wrap_line(draw, raw, font, max_width):
            draw.text((x, y), line, font=font, fill=fill)
            y += line_height
    return y


def rounded_panel(
    layer: Image.Image,
    xy: tuple[int, int, int, int],
    fill: tuple[int, int, int, int],
    outline: tuple[int, int, int, int],
    radius: int = 36,
    width: int = 3,
) -> None:
    draw = ImageDraw.Draw(layer, "RGBA")
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def add_panel_text(
    base: Image.Image,
    xy: tuple[int, int, int, int],
    title: str,
    body: list[str],
    accent: tuple[int, int, int],
    *,
    dark: bool = False,
    title_size: int = 40,
    body_size: int = 29,
) -> None:
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    fill = (244, 251, 255, 232) if not dark else (5, 17, 34, 218)
    outline = (*accent, 220)
    rounded_panel(overlay, xy, fill, outline, radius=34, width=3)
    base.alpha_composite(overlay)

    draw = ImageDraw.Draw(base)
    x1, y1, x2, _ = xy
    pad_x = 34
    pad_y = 28
    title_font = load_font(title_size, bold=True)
    body_font = load_font(body_size)
    title_fill = accent if dark else COLORS["ink"]
    body_fill = COLORS["white"] if dark else COLORS["text"]
    draw.text((x1 + pad_x, y1 + pad_y), title, font=title_font, fill=title_fill)
    y = y1 + pad_y + title_size + 22
    max_width = x2 - x1 - pad_x * 2
    for item in body:
        bullet = "• " + item
        y = draw_wrapped(draw, (x1 + pad_x, y), bullet, body_font, body_fill, max_width, line_gap=8)
        y += 8


def add_chip_row(
    base: Image.Image,
    x: int,
    y: int,
    chips: list[str],
    *,
    max_right: int,
    dark: bool = True,
    font_size: int = 24,
) -> int:
    draw = ImageDraw.Draw(base, "RGBA")
    font = load_font(font_size, bold=True)
    cursor_x = x
    cursor_y = y
    for chip in chips:
        w = text_width(draw, chip, font) + 34
        h = font_size + 22
        if cursor_x + w > max_right:
            cursor_x = x
            cursor_y += h + 12
        fill = (12, 31, 58, 220) if dark else (237, 249, 255, 235)
        outline = (*COLORS["cyan"], 190)
        draw.rounded_rectangle((cursor_x, cursor_y, cursor_x + w, cursor_y + h), radius=h // 2, fill=fill, outline=outline, width=2)
        draw.text((cursor_x + 17, cursor_y + 10), chip, font=font, fill=COLORS["white"] if dark else COLORS["ink"])
        cursor_x += w + 12
    return cursor_y + font_size + 22


def draw_portrait() -> None:
    size = (1440, 2560)
    bg = cover_resize(Image.open(PORTRAIT_BG).convert("RGB"), size).convert("RGBA")
    base = bg.filter(ImageFilter.UnsharpMask(radius=1.2, percent=115))
    draw = ImageDraw.Draw(base)

    title_font = load_font(78, bold=True)
    sub_font = load_font(34)
    small_font = load_font(28, bold=True)
    draw.text((96, 92), "地库车辆定位系统", font=title_font, fill=COLORS["ink"])
    draw.text((100, 178), "Garage Vehicle Locator", font=load_font(39, bold=True), fill=(7, 91, 129))
    draw.text((100, 236), "多路视频接入 · YOLO Pose 车牌角点 · OCR/LPRNet 识别 · RDK X5 边缘部署", font=sub_font, fill=COLORS["text"])
    draw.text((100, 302), "从“识别到车牌”到“定位最后出现摄像头”的完整边缘 AI 应用", font=small_font, fill=(15, 118, 110))

    add_panel_text(
        base,
        (72, 1720, 690, 2048),
        "技术路线",
        [
            "摄像头 / RTSP / 视频 / 图片统一接入",
            "LatestFrameBuffer 只保留每路最新帧，Lock + Event 通知推理",
            "YOLO11m-Pose 输出车牌框与四角点，透视裁切车牌区域",
        ],
        COLORS["blue"],
        title_size=37,
        body_size=27,
    )
    add_panel_text(
        base,
        (750, 1720, 1368, 2048),
        "实现逻辑",
        [
            "PC 后端：YOLO .pt + PaddleOCR，适合开发联调",
            "RDK 后端：YOLO .bin + LPRNet .bin，面向 BPU 边缘部署",
            "DetectionResult 统一 box、pts、text、confidence、crop",
        ],
        COLORS["green"],
        title_size=37,
        body_size=27,
    )
    add_panel_text(
        base,
        (72, 2112, 690, 2442),
        "实现效果",
        [
            "Web 控制台展示 4 路监控、通行日志、识别耗时和异常状态",
            "按车牌查询最后出现摄像头、时间、车牌裁切图并高亮路线",
            "训练 400 epoch：Box mAP50 0.99480，Pose mAP50 0.99482",
        ],
        COLORS["purple"],
        title_size=37,
        body_size=27,
    )
    add_panel_text(
        base,
        (750, 2112, 1368, 2442),
        "项目展望",
        [
            "接入真实车库地图、楼层/区域导航和移动端寻车入口",
            "融合跨摄像头轨迹、置信度纠错、告警和历史归档",
            "继续优化 RDK X5 BPU 性能、低照度识别和长期运行稳定性",
        ],
        COLORS["amber"],
        title_size=37,
        body_size=27,
    )

    add_chip_row(
        base,
        92,
        2468,
        ["地库寻车", "车牌识别", "YOLO Pose", "PaddleOCR", "LPRNet", "RDK X5", "SQLite", "多线程", "Web 控制台"],
        max_right=1348,
        dark=True,
        font_size=22,
    )
    base.convert("RGB").save(PORTRAIT_OUT, quality=96)


def draw_landscape() -> None:
    size = (2560, 1440)
    bg = cover_resize(Image.open(LANDSCAPE_BG).convert("RGB"), size).convert("RGBA")
    base = bg.filter(ImageFilter.UnsharpMask(radius=1.1, percent=110))
    draw = ImageDraw.Draw(base)

    add_panel_text(
        base,
        (46, 54, 535, 994),
        "地库车辆定位系统",
        [
            "面向地下停车场的车辆最后位置查询系统",
            "多路视频采集、车牌关键点检测、字符识别、轨迹入库、Web 可视化查询一体化",
            "目标：让管理人员通过车牌快速定位车辆最后出现摄像头和时间",
        ],
        COLORS["cyan"],
        dark=True,
        title_size=48,
        body_size=29,
    )

    title_font = load_font(56, bold=True)
    draw.text((590, 58), "AI 车牌定位：从边缘推理到可视化寻车", font=title_font, fill=COLORS["white"])
    draw.text(
        (592, 128),
        "YOLO Pose 角点检测 · 透视裁切 · OCR/LPRNet 识别 · SQLite 历史轨迹 · /api/events /api/search",
        font=load_font(29, bold=True),
        fill=(168, 244, 255),
    )

    card_y1, card_y2 = 1034, 1370
    cards = [
        (
            (48, card_y1, 520, card_y2),
            "技术路线",
            [
                "输入源：摄像头 / RTSP / 视频 / 图片",
                "最新帧覆盖，避免队列积压",
                "YOLO11m-Pose 检测车牌框与四角点",
            ],
            COLORS["blue"],
        ),
        (
            (540, card_y1, 1015, card_y2),
            "推理后端",
            [
                "PC：YOLO .pt + PaddleOCR",
                "RDK：YOLO .bin + LPRNet .bin",
                "统一 DetectionResult 输出",
            ],
            COLORS["green"],
        ),
        (
            (1036, card_y1, 1510, card_y2),
            "实现效果",
            [
                "4 路监控画面和实时通行日志",
                "按车牌查询最后摄像头、时间和裁切图",
                "路线图高亮入口到目标点位",
            ],
            COLORS["cyan"],
        ),
        (
            (1530, card_y1, 2005, card_y2),
            "训练结果",
            [
                "训练 400 epoch，输入尺寸 640",
                "Box mAP50：0.99480",
                "Pose mAP50-95：0.99461",
            ],
            COLORS["purple"],
        ),
        (
            (2026, card_y1, 2500, card_y2),
            "项目展望",
            [
                "真实车库地图与移动端寻车",
                "跨镜轨迹融合和误识别纠错",
                "BPU 性能优化与长期运维告警",
            ],
            COLORS["amber"],
        ),
    ]
    for xy, title, body, accent in cards:
        add_panel_text(base, xy, title, body, accent, dark=True, title_size=35, body_size=25)

    add_chip_row(
        base,
        586,
        938,
        ["地库寻车", "车牌识别", "YOLO Pose", "PaddleOCR", "LPRNet", "RDK X5", "BPU", "SQLite", "多线程", "Web 控制台", "边缘 AI"],
        max_right=2478,
        dark=True,
        font_size=25,
    )
    base.convert("RGB").save(LANDSCAPE_OUT, quality=96)


def main() -> None:
    POSTER_DIR.mkdir(parents=True, exist_ok=True)
    draw_portrait()
    draw_landscape()
    print(PORTRAIT_OUT)
    print(LANDSCAPE_OUT)


if __name__ == "__main__":
    main()

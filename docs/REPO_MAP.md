# 仓库地图

这份文档面向后续维护者，用来快速理解模块边界、运行入口和数据流。面向使用者的安装与运行说明仍以根目录 [`README.md`](../README.md) 为准。

## 入口

| 路径 | 用途 |
| --- | --- |
| `main.py` | PyQt5 全屏监控台主入口。 |
| `test/test_headless.py` | 无显示器环境自检入口，适合 SSH 到 RDK X5 板端联调。 |
| `utils/detect_plate_rdk.py` | 独立车牌识别 CLI，适合调试单图、目录、视频或摄像头输入。 |

## 核心模块

| 路径 | 职责 |
| --- | --- |
| `utils/camera_worker.py` | 多路采集线程、共享帧缓冲、串行推理线程和画面标注。 |
| `utils/inference.py` | 统一推理后端抽象，封装 PC 与 BPU 两种检测识别路径。 |
| `utils/db_manager.py` | SQLite 轨迹库，保存车牌、摄像头编号、时间和车牌裁切图。 |
| `utils/gui_theme.py` | QSS 主题和离线占位图。 |
| `utils/plate_utils.py` | 车牌四点排序、透视裁切、OCR 文本清洗、图片读写和绘制工具。 |

## 板端适配

| 路径 | 职责 |
| --- | --- |
| `utils/ultralytics_yolo_pose.py` | RDK X5 `hbm_runtime` YOLO pose 包装层。 |
| `utils/preprocess.py` | YOLO pose 输入预处理，包含 letterbox 和 NV12 打包。 |
| `utils/postprocess.py` | YOLO pose 输出解码、NMS、坐标和关键点映射。 |
| `utils/detect_plate_rdk.py` | LPRNet 字符识别和独立 CLI。 |

## 资源目录

| 目录 | 内容 |
| --- | --- |
| `models/` | PC 与板端模型权重。`.gitignore` 默认忽略模型大文件，只显式允许项目自带模型。 |
| `assets/` | 测试图片和 README 展示图片。 |
| `docs/` | 仓库地图和测试说明。 |
| `test/` | 测试、自检入口。 |
| `utils/` | 单层方法文件目录。 |

## 主程序数据流

```text
input source
    │
    ▼
CameraGrabber x N
    │  put(camera_id, frame)
    ▼
FrameBuffer
    │  get_all()
    ▼
InferenceWorker
    │  detector.detect(frame)
    ▼
PCDetectionBackend / BPUDetectionBackend
    │
    ▼
DetectionResult[]
    │
    ├── UI QLabel 更新标注画面
    └── DBManager.record_occurrence()
            │
            ▼
      vehicle_locator.db
```

## 后端差异

| 后端 | 适用环境 | 检测 | OCR |
| --- | --- | --- | --- |
| `pc` | 开发机、本地模拟 | `ultralytics` YOLO pose `.pt` | PaddleOCR |
| `bpu` | RDK X5 板端 | `hbm_runtime` YOLO pose `.bin` | LPRNet `.bin` |

两种后端都返回 `utils.inference.DetectionResult`，因此 UI、数据库和日志逻辑无需关心具体推理实现。

## 数据库

`DBManager` 默认创建 `vehicle_locator.db`，表结构为：

| 字段 | 说明 |
| --- | --- |
| `id` | 自增主键。 |
| `plate_number` | 清洗后的车牌号。 |
| `camera_id` | 摄像头编号，从 1 开始显示。 |
| `timestamp` | 记录写入时间，格式为 `YYYY-MM-DD HH:MM:SS`。 |
| `crop_image` | JPEG 编码后的车牌裁切图。 |

`query_last_location()` 按 `timestamp DESC, id DESC` 查询，保证同一秒内多条记录也能稳定返回最后写入项。

## 维护约定

- 根目录保留 `main.py` 作为主启动入口。
- 方法文件统一放在单层 `utils/` 下。
- 测试或自检入口放在 `test/` 下。
- 不再恢复原始 RDK 示例中的批量评估、性能测试、模型映射和通用可视化工具，除非它们重新成为本应用运行路径的一部分。
- 生成物如 `__pycache__/`、`*.db`、`output_results/`、`plate_crops/`、`output_*.jpg` 不应提交。
- 目录、导入或 CLI 参数变更后，至少运行 [`docs/TESTING.md`](TESTING.md) 中的轻量测试。

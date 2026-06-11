# 仓库地图

这份文档用于快速定位开发入口。运行说明仍以根目录 `README.md` 为准。

## 核心应用

| 文件 | 职责 |
| --- | --- |
| `main.py` | PyQt5 监控大屏入口，负责 UI、线程启动、车牌查询和日志展示。 |
| `utils/camera_worker.py` | 多路采集线程、共享帧缓冲和单路串行推理线程。 |
| `utils/inference.py` | 统一推理后端抽象，封装 PC 与 BPU 两种检测识别路径。 |
| `utils/db_manager.py` | SQLite 轨迹库，保存车牌、摄像头、时间和车牌裁切图。 |
| `utils/gui_theme.py` | QSS 主题和离线占位画面。 |
| `test/test_headless.py` | 无显示器环境自检入口，适合 SSH 到板端验证链路。 |

## 识别与工具

| 文件或目录 | 职责 |
| --- | --- |
| `utils/plate_utils.py` | 车牌四点排序、透视裁切、文本清洗、图片读写与标注工具。 |
| `utils/detect_plate_rdk.py` | RDK LPRNet 识别器，也可作为独立 CLI 处理图片、目录、视频或摄像头。 |
| `utils/ultralytics_yolo_pose.py` | RDK X5 `hbm_runtime` YOLO pose 包装层。 |
| `utils/preprocess.py` / `utils/postprocess.py` | 精简后的 RDK YOLO pose 预处理与后处理。 |

## 资源目录

| 目录 | 内容 |
| --- | --- |
| `models/` | PC 与板端模型权重。`.gitignore` 默认忽略模型大文件，只显式允许项目自带的三个模型。 |
| `assets/` | 测试图片和 README 展示图片。 |

## 数据流

1. `CameraGrabber` 从摄像头、视频或图片源读取最新帧。
2. `FrameBuffer` 按摄像头槽位覆盖旧帧，避免积压。
3. `InferenceWorker` 串行取帧并调用 `VehiclePlateDetector.detect()`。
4. `PCDetectionBackend` 或 `BPUDetectionBackend` 输出 `DetectionResult`。
5. 主线程更新画面，并通过 `DBManager.record_occurrence()` 持久化通行记录。
6. 查询框调用 `DBManager.query_last_location()` 返回目标车牌最后出现位置。

## 整理原则

- 根目录保留 `main.py` 作为主启动入口，方法文件统一放在单层 `utils/` 下。
- 车牌裁切、文本清洗、绘制等通用逻辑统一放在 `utils/plate_utils.py`。
- 生成物如 `__pycache__/`、`*.db`、`output_results/`、`plate_crops/` 不应提交。

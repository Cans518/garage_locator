# 仓库地图

这份文档面向后续维护者，用来快速理解模块边界、运行入口和数据流。面向使用者的安装与运行说明仍以根目录 [`README.md`](../README.md) 为准。

## 入口

| 路径 | 用途 |
| --- | --- |
| `web_app.py` | Web 控制台服务入口，负责 HTTP API、静态资源和推理运行时。 |
| `webview_app.py` | PyQt WebView 桌面壳入口，自动启动本地 Web 服务。 |
| `web/` | Web 控制台前端页面、样式和交互脚本。 |
| `test/test_headless.py` | 无显示器环境自检入口，适合 SSH 到 RDK X5 板端联调。 |
| `utils/detect_plate_rdk.py` | 独立车牌识别 CLI，适合调试单图、目录、视频或摄像头输入。 |

## 核心模块

| 路径 | 职责 |
| --- | --- |
| `utils/camera_worker.py` | 多路采集线程、共享帧缓冲、串行推理线程和画面标注。 |
| `utils/inference.py` | 统一推理后端抽象，封装 PC 与 BPU 两种检测识别路径。 |
| `utils/db_manager.py` | SQLite 轨迹库，保存车牌、摄像头编号、时间和车牌裁切图。 |
| `utils/gui_theme.py` | Qt 主题和离线占位图，供保留的 Qt 自检或桌面壳扩展复用。 |
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
| `docs/` | 安装部署教程、仓库地图和测试说明。 |
| `test/` | 测试、自检入口。 |
| `utils/` | 单层方法文件目录。 |
| `web/` | Web 控制台前端资源。 |

## 文档目录

| 路径 | 内容 |
| --- | --- |
| `README.md` | 项目概览、快速运行和文档入口。 |
| `docs/visual-tutorial.html` | 可直接打开的静态可视化教程，包含架构图、部署路线和技术链接。 |
| `docs/INSTALL_AND_DEPLOY.md` | 从 Conda 安装到 PC / RDK X5 部署的完整教程。 |
| `docs/REPO_MAP.md` | 模块边界、数据流和维护约定。 |
| `docs/TESTING.md` | 轻量测试、PC 联调和 RDK 联调命令。 |
| `utils/README.md` | `utils/` 目录内各模块职责。 |

## 主程序数据流

```text
input source
    │
    ▼
CameraCaptureThread x N
    │  put(camera_id, frame)
    ▼
LatestFrameBuffer
    │  get_all()
    ▼
WebInferenceRuntime
    │  detector.detect(frame)
    ▼
PCDetectionBackend / BPUDetectionBackend
    │
    ▼
DetectionResult[]
    │
    ├── /api/events 更新监控画面和通行日志
    └── DBManager.record_occurrence()
            │
            ▼
      vehicle_locator.db
```

## 线程安排与通信

Web 控制台运行时由三类并发执行单元组成：

| 执行单元 | 创建位置 | 主要职责 | 通信对象 |
| --- | --- | --- | --- |
| `CameraCaptureThread` x N | `WebInferenceRuntime.start()` | 每路输入一个采集线程，读取摄像头、视频、RTSP 或图片源。图片源每秒重复投递，视频文件读到末尾后循环。 | 调用 `LatestFrameBuffer.put(camera_id, frame)` |
| 推理线程 | `threading.Thread(target=self._run_inference)` | 等待任意通道有新帧，批量取出当前最新帧，串行调用 `detector.detect(frame)`，更新标注图、延迟、事件和错误列表。 | 读取 `LatestFrameBuffer`；写 `camera_frames`、`events`、`latency_by_camera`、`errors` 和 SQLite |
| HTTP 请求线程 | `ThreadingHTTPServer` | 每个请求独立处理静态文件、`/api/events` 和 `/api/search`。 | 通过 `WEB_RUNTIME.snapshot()` 读取运行时快照，或直接查询 SQLite |

同步策略：

- `LatestFrameBuffer` 使用 `threading.Lock` 保护 `frames` 字典，用 `threading.Event` 通知推理线程有新帧。
- `put()` 覆盖同一路旧帧，避免队列堆积；`get_all()` 复制当前批次后清空槽位，保证实时性优先。
- `WebInferenceRuntime.lock` 保护 `camera_frames`、`events`、`latency_by_camera` 和 `errors`，HTTP 请求只读取复制后的快照。
- 推理后端实例只被单个推理线程调用，避免 PC 模型 runtime 或 RDK BPU runtime 被多线程同时访问。
- SQLite 连接按写入或查询短期开启，不跨线程共享 cursor。

## 后端差异

| 后端 | 适用环境 | 检测 | OCR |
| --- | --- | --- | --- |
| `pc` | 开发机、本地模拟 | `ultralytics` YOLO pose `.pt` | PaddleOCR |
| `bpu` | RDK X5 板端 | `hbm_runtime` YOLO pose `.bin` | LPRNet `.bin` |

两种后端都返回 `utils.inference.DetectionResult`，因此 UI、数据库和日志逻辑无需关心具体推理实现。

`DetectionResult` 字段约定：

| 字段 | 含义 | 消费方 |
| --- | --- | --- |
| `box` | 车牌矩形框 4 点，用于画检测框。 | `draw_annotations()` |
| `pts` | 车牌四角关键点，用于透视裁切。 | `crop_plate()` |
| `text` | 清洗后的车牌号。 | 事件日志、SQLite、查询结果 |
| `confidence` | OCR 或 LPRNet 识别置信度。 | 前端日志、标注文字 |
| `crop` | 车牌裁切图。 | `DBManager.record_occurrence()` |

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

- 根目录保留 `web_app.py` 和 `webview_app.py` 作为主启动入口。
- 方法文件统一放在单层 `utils/` 下。
- 测试或自检入口放在 `test/` 下。
- 不再恢复原始 RDK 示例中的批量评估、性能测试、模型映射和通用可视化工具，除非它们重新成为本应用运行路径的一部分。
- 生成物如 `__pycache__/`、`*.db`、`*.zip`、`output_results/`、`plate_crops/`、`output_*.jpg` 不应提交。
- 目录、导入、依赖或 CLI 参数变更后，同步更新 [`docs/INSTALL_AND_DEPLOY.md`](INSTALL_AND_DEPLOY.md) 和 [`docs/TESTING.md`](TESTING.md)。

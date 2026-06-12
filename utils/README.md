# Utils

`utils/` 是项目的方法文件目录。这里保持单层结构，所有主应用依赖的业务模块、板端适配模块和公共工具都放在这一层，方便在 `web_app.py`、`webview_app.py`、`test/test_headless.py` 和独立 CLI 中复用。

## 文件职责

| 文件 | 职责 |
| --- | --- |
| `camera_worker.py` | 定义 `FrameBuffer`、`CameraGrabber`、`InferenceWorker`，负责多路采集、最新帧缓冲和串行推理线程。 |
| `db_manager.py` | 管理 SQLite 轨迹库，提供车牌出现记录、末次位置查询和模糊查询。 |
| `detect_plate_rdk.py` | 封装 `LPRNetRecognizer`，也提供独立 CLI 处理图片、目录、视频和摄像头。 |
| `gui_theme.py` | 提供 PyQt5 QSS 主题和离线通道占位图。 |
| `inference.py` | 定义统一检测结果结构和 PC / BPU 两种推理后端。 |
| `plate_utils.py` | 提供车牌四点排序、透视裁切、文本清洗、图片读写、标注绘制等通用能力。 |
| `preprocess.py` | RDK YOLO pose 输入预处理，包含 resize、letterbox、BGR 到 NV12 转换。 |
| `postprocess.py` | RDK YOLO pose 输出后处理，包含分类过滤、框解码、关键点解码、NMS、坐标映射。 |
| `ultralytics_yolo_pose.py` | RDK X5 上的 YOLO pose `hbm_runtime` 包装层。 |

## 导入约定

项目根目录作为运行工作目录时，外部入口使用包导入：

```python
from utils.inference import PCDetectionBackend, BPUDetectionBackend
from utils.camera_worker import FrameBuffer, CameraGrabber, InferenceWorker
```

`utils/` 内部模块之间优先使用相对导入：

```python
from .plate_utils import clean_plate_number, crop_plate
```

需要作为脚本直接运行的文件，例如 `utils/detect_plate_rdk.py`，会在启动时把项目根目录加入 `sys.path`，再使用 `utils.*` 导入。

## 维护边界

- 与车牌几何、文本清洗、图片保存相关的公共逻辑放在 `plate_utils.py`。
- 与 PyQt5 线程和图像信号相关的逻辑放在 `camera_worker.py`。
- 与模型 runtime、预处理、后处理相关的逻辑放在 `inference.py`、`ultralytics_yolo_pose.py`、`preprocess.py`、`postprocess.py`。
- 原始 RDK 示例中的批量评估、性能测试、可视化、文件 I/O、模型检查等工具已移除，只保留本应用运行路径需要的代码。

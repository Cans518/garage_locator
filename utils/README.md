# Utils

`utils/` 是项目的方法文件目录，保持单层结构，避免业务代码分散在根目录或多层工具目录里。

## 文件职责

| 文件 | 职责 |
| --- | --- |
| `camera_worker.py` | 多路采集线程、共享帧缓冲和串行推理线程。 |
| `db_manager.py` | SQLite 车辆轨迹记录与查询。 |
| `detect_plate_rdk.py` | RDK LPRNet 识别器，也可作为独立 CLI 使用。 |
| `gui_theme.py` | PyQt5 QSS 主题和离线占位图。 |
| `inference.py` | PC / BPU 两种推理后端的统一封装。 |
| `plate_utils.py` | 车牌透视裁切、文本清洗、绘制、图片读写工具。 |
| `ultralytics_yolo_pose.py` | RDK X5 YOLO pose BPU runtime 包装层。 |
| `preprocess.py` | RDK YOLO 输入预处理。 |
| `postprocess.py` | RDK YOLO 输出解码、NMS 和坐标映射。 |


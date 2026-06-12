# 测试说明

本项目同时支持 PC 测试后端和 RDK X5 BPU 后端。日常提交前建议先跑轻量测试，确认目录结构、导入路径和基础数据库逻辑没有被破坏。

## 轻量测试

这些命令不会启动全屏 GUI，也不会加载 PC 或 BPU 模型。

### 语法编译

```bash
python3 -m py_compile \
  web_app.py \
  webview_app.py \
  utils/__init__.py \
  utils/camera_worker.py \
  utils/db_manager.py \
  utils/detect_plate_rdk.py \
  utils/gui_theme.py \
  utils/inference.py \
  utils/plate_utils.py \
  utils/preprocess.py \
  utils/postprocess.py \
  utils/ultralytics_yolo_pose.py \
  test/test_headless.py
```

Windows PowerShell 可使用反引号续行，或直接写成一行：

```powershell
python -m py_compile web_app.py webview_app.py utils\__init__.py utils\camera_worker.py utils\db_manager.py utils\detect_plate_rdk.py utils\gui_theme.py utils\inference.py utils\plate_utils.py utils\preprocess.py utils\postprocess.py utils\ultralytics_yolo_pose.py test\test_headless.py
```

### 核心导入烟测

```bash
python3 -c "import web_app; import webview_app; import utils.camera_worker; import utils.db_manager; import utils.inference; import utils.plate_utils; from utils.plate_utils import clean_plate_number; assert clean_plate_number('皖A·S0747') == '皖AS0747'; print('core import smoke OK')"
```

### 数据库烟测

```bash
python3 -c "import tempfile, os, gc; from utils.db_manager import DBManager; fd,p=tempfile.mkstemp(suffix='.db'); os.close(fd); db=DBManager(p); db.record_occurrence('皖AS0747',1); db.record_occurrence('皖AS0747',2); db.record_occurrence('皖AQ4025',3); assert db.query_last_location('皖AS0747')['camera_id']==2; fuzzy=db.query_fuzzy('皖A'); assert {row['plate_number'] for row in fuzzy}=={'皖AS0747','皖AQ4025'}; db=None; gc.collect(); os.remove(p); print('db smoke OK')"
```

### CLI 参数解析

```bash
python3 web_app.py --help
python3 webview_app.py --help
python3 test/test_headless.py --help
python3 utils/detect_plate_rdk.py --help
```

## PC 后端联调

需要额外安装 `ultralytics`、`paddlepaddle`、`paddleocr`。

```bash
python3 web_app.py \
  --backend pc \
  --inputs assets/test_plate.jpg assets/test_plate2.jpg \
  --yolo-model models/yolo11m-pose-carplate.pt
```

该命令会启动浏览器 Web 控制台服务。若需要桌面窗口，可把入口替换为 `webview_app.py`。

## RDK X5 板端联调

需要在板端环境中可导入 `hbm_runtime`。

无界面自检：

```bash
python3 test/test_headless.py \
  --backend bpu \
  --inputs assets/test_plate.jpg \
  --yolo-bin models/yolo11m-pose-carplate_bayese_640x640_nv12.bin \
  --lpr-bin models/lpr.bin
```

全屏监控台：

```bash
python3 web_app.py \
  --backend bpu \
  --host 0.0.0.0 \
  --port 8080 \
  --inputs /dev/video0 assets/test_plate.jpg \
  --yolo-bin models/yolo11m-pose-carplate_bayese_640x640_nv12.bin \
  --lpr-bin models/lpr.bin
```

## 测试后清理

测试可能生成以下文件或目录：

- `__pycache__/`
- `vehicle_locator.db`
- `headless_test.db`
- `output_results/`
- `plate_crops/`
- `output_*.jpg`

这些路径已在 `.gitignore` 中忽略，不应提交。

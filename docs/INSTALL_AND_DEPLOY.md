# 安装与部署教程

这份文档从零开始说明如何安装 Conda、构建 PC 开发环境、启动 Web 控制台，并把同一套代码部署到 RDK X5 板端使用 BPU 推理。

如果只想快速跑起来，可以先看根目录 [`README.md`](../README.md)。如果要交付、复现或排障，请按本文顺序执行。

## 1. 先理解运行模式

项目有两种推理后端：

| 后端 | 入口参数 | 运行位置 | 检测模型 | 识别模型 | 典型用途 |
| --- | --- | --- | --- | --- | --- |
| PC 后端 | `--backend pc` | Windows / Linux / macOS 开发机 | `models/yolo11m-pose-carplate.pt` | PaddleOCR | 本地调试、演示、前端联调 |
| RDK BPU 后端 | `--backend bpu` | RDK X5 板端 | `models/yolo11m-pose-carplate_bayese_640x640_nv12.bin` | `models/lpr.bin` | 地库现场部署、BPU 加速 |
| 数据库浏览 | `--backend none` | PC 或板端 | 不加载模型 | 不加载模型 | 只查看已有数据库和页面 |

入口文件：

| 文件 | 用法 |
| --- | --- |
| `web_app.py` | 启动 HTTP Web 控制台。PC 浏览器和 RDK 部署都推荐这个入口。 |
| `webview_app.py` | 启动本地 HTTP 服务，并用 PyQt WebView 打开桌面窗口。只推荐 PC 桌面端使用。 |
| `test/test_headless.py` | 无界面自检脚本，适合 SSH 到 RDK 后验证 BPU 和模型。 |
| `utils/detect_plate_rdk.py` | 独立车牌识别 CLI，适合单图、目录、视频和摄像头调试。 |

重要原则：

- PC 端推荐使用 Conda 隔离环境。
- RDK X5 的 BPU 后端依赖厂商系统里的 `hbm_runtime`，默认推荐使用板端系统 Python。不要把 PC 的 Conda 环境直接复制到 RDK 上。
- Web 控制台只需要浏览器访问；RDK 板端不需要安装 PyQtWebEngine。

## 2. 准备清单

开始前确认以下内容：

| 项目 | PC 开发机 | RDK X5 |
| --- | --- | --- |
| Python | Conda 环境中的 Python 3.10 或 3.11 | 板端系统 Python 3 |
| Git | 需要 | 需要，或用 `scp` 复制代码 |
| OpenCV | 通过 pip/conda 安装 | 可用系统包或 pip 安装 |
| YOLO `.pt` | `models/yolo11m-pose-carplate.pt` | 可选，仅 PC 后端需要 |
| YOLO `.bin` | 可保留 | `models/yolo11m-pose-carplate_bayese_640x640_nv12.bin` |
| LPR `.bin` | 可保留 | `models/lpr.bin` |
| 浏览器 | Chrome / Edge / Firefox 均可 | 可在 PC 浏览器访问板端 IP |
| 端口 | 默认 `8080` | 默认 `8080`，需要防火墙允许局域网访问 |

模型文件检查：

```bash
python -c "from pathlib import Path; files=['models/yolo11m-pose-carplate.pt','models/yolo11m-pose-carplate_bayese_640x640_nv12.bin','models/lpr.bin']; [print(p, Path(p).exists()) for p in files]"
```

如果输出中有 `False`，先补齐对应模型文件。

## 3. 安装 Conda

Conda 用在 PC 开发机上，负责创建独立 Python 环境。推荐安装 Miniconda 或 Miniforge；二者都能提供 `conda create`、`conda activate` 等命令。

官方参考：

- Conda 安装入口：<https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html>
- Miniconda 安装说明：<https://www.anaconda.com/docs/getting-started/miniconda/install/overview>
- Conda 官方文档首页：<https://docs.conda.io/>

### 3.1 Windows 安装

1. 访问 Conda 或 Miniconda 官方安装页面。
2. 下载 Windows x86_64 安装器。
3. 双击 `.exe`，一路使用默认选项即可。
4. 安装完成后，从开始菜单打开 `Anaconda Prompt` 或 `Miniconda Prompt`。
5. 验证安装：

```powershell
conda --version
conda list
```

如果命令不存在，不要急着手动改系统 PATH。优先使用开始菜单中的 Conda Prompt；需要 PowerShell 支持时再执行：

```powershell
conda init powershell
```

关闭并重新打开 PowerShell 后再试。

### 3.2 Linux 安装

下载安装脚本后执行，文件名以官网页面为准：

```bash
bash Miniconda3-latest-Linux-x86_64.sh
```

安装时建议选择当前用户目录，例如 `$HOME/miniconda3`。安装完成后重开终端，验证：

```bash
conda --version
conda list
```

如果当前 shell 没有初始化：

```bash
source ~/miniconda3/bin/activate
conda init
```

### 3.3 macOS 安装

Apple Silicon 选择 arm64 安装器，Intel Mac 选择 x86_64 安装器。使用 `.pkg` 图形安装器或终端脚本均可。终端安装示例：

```bash
bash Miniconda3-latest-MacOSX-arm64.sh
```

验证：

```bash
conda --version
conda list
```

### 3.4 常用 Conda 命令

| 目的 | 命令 |
| --- | --- |
| 创建环境 | `conda create -n garage_ocr python=3.10 -y` |
| 进入环境 | `conda activate garage_ocr` |
| 退出环境 | `conda deactivate` |
| 查看环境 | `conda env list` |
| 删除环境 | `conda env remove -n garage_ocr` |
| 查看 Python 路径 | `python -c "import sys; print(sys.executable)"` |

Windows 上如果 `conda run` 打印中文帮助时遇到 GBK 编码错误，可以先设置：

```powershell
$env:PYTHONUTF8 = "1"
```

也可以直接调用环境里的解释器，例如：

```powershell
D:\miniconda3\envs\garage_ocr\python.exe web_app.py --help
```

## 4. 获取项目代码

已有仓库时直接进入目录：

```bash
cd garage_locator
```

从 Git 克隆时：

```bash
git clone <repo-url> garage_locator
cd garage_locator
```

确认目录结构：

```bash
python -c "from pathlib import Path; print(Path('web_app.py').exists(), Path('web').exists(), Path('utils').exists())"
```

应输出 `True True True`。

## 5. PC 环境构建

### 5.1 创建基础环境

Windows PowerShell / Conda Prompt：

```powershell
conda create -n garage_ocr python=3.10 -y
conda activate garage_ocr
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
```

Linux / macOS：

```bash
conda create -n garage_ocr python=3.10 -y
conda activate garage_ocr
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
```

基础依赖包含：

- `PyQt5`、`PyQtWebEngine`：桌面 WebView 入口需要。
- `numpy`、`opencv-python`、`Pillow`、`pyclipper`：图像处理、绘制、裁切和 Web 画面编码需要。

### 5.2 安装 PC 推理依赖

PC 后端还需要 `ultralytics`、`paddlepaddle`、`paddleocr`：

```bash
python -m pip install ultralytics paddlepaddle paddleocr
```

PaddlePaddle 的 GPU 包和 CUDA 版本强相关。如果只是先验证流程，推荐先安装 CPU 版 `paddlepaddle`。需要 GPU 加速时，按 PaddlePaddle 官方安装页选择匹配本机 CUDA 的命令：

- PaddlePaddle 安装文档：<https://www.paddlepaddle.org.cn/documentation/docs/en/install/index_en.html>
- PaddleOCR 安装文档：<https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/installation.en.md>

### 5.3 Linux 图形依赖

Linux 上 `opencv-python` 或 QtWebEngine 可能需要系统库。Ubuntu 常见补齐命令：

```bash
sudo apt update
sudo apt install -y libgl1 libglib2.0-0 libxkbcommon-x11-0 libxcb-cursor0
```

如果只启动 `web_app.py` 并从浏览器访问，通常不需要桌面显示；如果启动 `webview_app.py`，需要有图形桌面或可用的 X11/Wayland 环境。

### 5.4 PC 环境验证

在激活 `garage_ocr` 后执行：

```bash
python -c "import cv2, numpy, PIL; print('base deps OK')"
python -c "from PyQt5.QtCore import QUrl; from PyQt5.QtWebEngineWidgets import QWebEngineView; print('qt deps OK')"
python -c "from ultralytics import YOLO; from paddleocr import PaddleOCR; print('pc inference deps OK')"
```

如果只打算用 `--backend none` 查看数据库，可以不安装 `ultralytics` 和 PaddleOCR。

## 6. PC 运行和部署

### 6.1 只启动页面和数据库查询

这个模式不加载模型，适合先验证前端和 HTTP 服务：

```bash
python web_app.py --backend none --host 127.0.0.1 --port 8080
```

浏览器打开：

```text
http://127.0.0.1:8080/
```

### 6.2 用测试图片启动 PC 推理

```bash
python web_app.py \
  --backend pc \
  --host 127.0.0.1 \
  --port 8080 \
  --inputs assets/test_plate.jpg assets/test_plate2.jpg \
  --yolo-model models/yolo11m-pose-carplate.pt
```

Windows PowerShell 一行命令：

```powershell
python web_app.py --backend pc --host 127.0.0.1 --port 8080 --inputs assets/test_plate.jpg assets/test_plate2.jpg --yolo-model models/yolo11m-pose-carplate.pt
```

未传 `--inputs` 时，程序会从 `assets/` 中按文件名取最多 4 张图片作为输入源。

### 6.3 使用摄像头、视频或 RTSP

`--inputs` 最多 4 路，顺序对应页面上的 C1 到 C4：

```bash
python web_app.py --backend pc --inputs 0 1
```

```bash
python web_app.py --backend pc --inputs videos/cam1.mp4 videos/cam2.mp4
```

```bash
python web_app.py --backend pc --inputs rtsp://user:password@192.168.1.10:554/stream1
```

输入源规则：

- 纯数字字符串会转为 OpenCV 摄像头编号，如 `0`、`1`。
- 图片文件会每秒重复投递一帧，适合演示。
- 视频文件读到末尾后会循环播放。
- RTSP/HTTP 流由 OpenCV `VideoCapture` 打开，断线后会自动重试。

### 6.4 启动桌面 WebView

只推荐 PC 桌面端使用：

```bash
python webview_app.py --backend pc
```

指定输入：

```bash
python webview_app.py --backend pc --inputs assets/test_plate.jpg assets/test_plate2.jpg
```

`webview_app.py` 默认 `--port 0`，表示自动选择空闲端口。

### 6.5 局域网访问

如果要让同一局域网其他设备访问 PC 服务：

```bash
python web_app.py --backend pc --host 0.0.0.0 --port 8080
```

然后在其他设备浏览器打开：

```text
http://<PC-IP>:8080/
```

Windows 防火墙如果弹窗，允许 Python 在专用网络中通信。

### 6.6 API 自检

服务启动后可访问：

```bash
curl http://127.0.0.1:8080/api/events
curl "http://127.0.0.1:8080/api/search?plate=皖AS0747"
```

Windows PowerShell：

```powershell
Invoke-RestMethod http://127.0.0.1:8080/api/events
Invoke-RestMethod "http://127.0.0.1:8080/api/search?plate=皖AS0747"
```

## 7. RDK X5 部署

RDK 相关官方参考：

- RDK 文档下载资源：<https://developer.d-robotics.cc/rdk_doc/en/Quick_start/download/>
- RDK Model Zoo：<https://github.com/D-Robotics/rdk_model_zoo>

本项目的板端代码按 RDK X5 的 `hbm_runtime` Python 运行库整理，推荐使用与模型文件匹配的 RDK OS，并确认板端可以导入 `hbm_runtime`。

### 7.1 板端系统确认

SSH 登录 RDK：

```bash
ssh sunrise@<RDK-IP>
```

确认系统和 Python：

```bash
uname -a
python3 --version
python3 -c "import sys; print(sys.executable)"
```

确认 BPU Python runtime：

```bash
python3 -c "import hbm_runtime; print('hbm_runtime OK')"
```

如果这里失败，先检查 RDK OS 镜像和厂商 Python 包，不要急着用 pip 安装 `hbm_runtime`。

### 7.2 获取代码到 RDK

方式一：板端直接克隆：

```bash
git clone <repo-url> garage_locator
cd garage_locator
```

方式二：从 PC 复制：

```bash
scp -r garage_locator sunrise@<RDK-IP>:/home/sunrise/garage_locator
```

大型数据集压缩包、数据库和缓存不需要复制。确认模型在板端存在：

```bash
cd ~/garage_locator
ls -lh models/
```

应至少看到：

```text
yolo11m-pose-carplate_bayese_640x640_nv12.bin
lpr.bin
```

### 7.3 安装 RDK 最小依赖

板端 Web 服务不需要 PyQt5 / PyQtWebEngine。推荐安装最小依赖：

```bash
cd ~/garage_locator
python3 -m pip install --user -r requirements-rdk.txt
```

如果 RDK 系统已经内置了 OpenCV，也可以先验证：

```bash
python3 -c "import cv2, numpy, PIL, pyclipper; print('rdk python deps OK')"
```

如果安装 `opencv-python-headless` 很慢或失败，可以改用系统包：

```bash
sudo apt update
sudo apt install -y python3-opencv python3-pil
python3 -m pip install --user numpy pyclipper
```

### 7.4 RDK 无界面自检

先跑 20 秒自检，确认 BPU 后端能加载模型并写入测试数据库：

```bash
python3 test/test_headless.py \
  --backend bpu \
  --inputs assets/test_plate.jpg \
  --yolo-bin models/yolo11m-pose-carplate_bayese_640x640_nv12.bin \
  --lpr-bin models/lpr.bin
```

期望现象：

- 终端显示 BPU 后端初始化成功。
- 终端输出通道推理耗时。
- 生成 `headless_test.db`。

如果模型加载失败，优先确认 `.bin` 文件是否匹配当前 RDK OS 和 BPU runtime。

### 7.5 RDK 启动 Web 控制台

单摄像头：

```bash
python3 web_app.py \
  --backend bpu \
  --host 0.0.0.0 \
  --port 8080 \
  --inputs /dev/video0 \
  --yolo-bin models/yolo11m-pose-carplate_bayese_640x640_nv12.bin \
  --lpr-bin models/lpr.bin
```

测试图片：

```bash
python3 web_app.py \
  --backend bpu \
  --host 0.0.0.0 \
  --port 8080 \
  --inputs assets/test_plate.jpg assets/test_plate2.jpg \
  --yolo-bin models/yolo11m-pose-carplate_bayese_640x640_nv12.bin \
  --lpr-bin models/lpr.bin
```

多路摄像头：

```bash
python3 web_app.py \
  --backend bpu \
  --host 0.0.0.0 \
  --port 8080 \
  --inputs /dev/video0 /dev/video1 rtsp://user:password@192.168.1.30:554/stream1 \
  --yolo-bin models/yolo11m-pose-carplate_bayese_640x640_nv12.bin \
  --lpr-bin models/lpr.bin
```

在 PC 浏览器打开：

```text
http://<RDK-IP>:8080/
```

### 7.6 摄像头检查

查看视频设备：

```bash
ls -l /dev/video*
```

用 OpenCV 快速读一帧：

```bash
python3 -c "import cv2; cap=cv2.VideoCapture('/dev/video0'); ok, frame=cap.read(); print(ok, None if frame is None else frame.shape); cap.release()"
```

如果 `ok` 是 `False`：

- 检查摄像头是否被其他进程占用。
- 检查权限，当前用户是否能访问 `/dev/video0`。
- USB 摄像头可尝试重新插拔或换端口。
- RTSP 流先用 VLC 或 `ffplay` 验证地址、账号和密码。

### 7.7 设置开机服务

如果要让板端开机后自动启动 Web 控制台，可以创建 systemd 服务。

创建文件：

```bash
sudo nano /etc/systemd/system/garage-locator.service
```

写入，按实际用户名和路径调整：

```ini
[Unit]
Description=Garage Vehicle Locator Web Console
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=sunrise
WorkingDirectory=/home/sunrise/garage_locator
ExecStart=/usr/bin/python3 /home/sunrise/garage_locator/web_app.py --backend bpu --host 0.0.0.0 --port 8080 --inputs /dev/video0 --yolo-bin models/yolo11m-pose-carplate_bayese_640x640_nv12.bin --lpr-bin models/lpr.bin
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启用：

```bash
sudo systemctl daemon-reload
sudo systemctl enable garage-locator
sudo systemctl start garage-locator
sudo systemctl status garage-locator
```

查看日志：

```bash
journalctl -u garage-locator -f
```

停止：

```bash
sudo systemctl stop garage-locator
```

## 8. 模型和数据说明

### 8.1 模型文件

| 文件 | 用途 | 运行端 |
| --- | --- | --- |
| `models/yolo11m-pose-carplate.pt` | Ultralytics YOLO pose 模型，输出车牌框和 4 个角点 | PC |
| `models/yolo11m-pose-carplate_bayese_640x640_nv12.bin` | RDK BPU YOLO pose 模型 | RDK X5 |
| `models/lpr.bin` | RDK BPU LPRNet 字符识别模型 | RDK X5 |

如果替换模型，需要保证：

- 检测模型输出的是车牌框和至少 4 个关键点。
- 关键点顺序能被 `utils/plate_utils.py` 中的排序和透视裁切逻辑正确处理。
- RDK `.bin` 模型与当前 RDK runtime 兼容。
- LPRNet 输出类别与 `utils/detect_plate_rdk.py` 中的 `CHARS` 表一致。

### 8.2 数据库

默认数据库：

```text
vehicle_locator.db
```

表结构由 `utils/db_manager.py` 自动创建：

| 字段 | 说明 |
| --- | --- |
| `id` | 自增主键 |
| `plate_number` | 清洗后的车牌号 |
| `camera_id` | 摄像头编号，页面从 1 开始显示 |
| `timestamp` | 写入时间 |
| `crop_image` | JPEG 编码后的车牌裁切图 |

查询逻辑按 `timestamp DESC, id DESC` 取最后一次出现位置。

### 8.3 生成物

以下文件不应提交：

- `vehicle_locator.db`
- `headless_test.db`
- `__pycache__/`
- `output_results/`
- `plate_crops/`
- `output_*.jpg`
- `*.zip`

这些路径已由 `.gitignore` 忽略。

## 9. 常用参数速查

`web_app.py` 和 `webview_app.py` 共享以下推理参数：

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--backend` | `pc` | `pc`、`bpu` 或 `none` |
| `--inputs` | 空 | 摄像头、视频、图片或 RTSP 输入，最多 4 路 |
| `--yolo-model` | `models/yolo11m-pose-carplate.pt` | PC YOLO pose 权重 |
| `--yolo-bin` | `models/yolo11m-pose-carplate_bayese_640x640_nv12.bin` | RDK YOLO `.bin` |
| `--lpr-bin` | `models/lpr.bin` | RDK LPRNet `.bin` |
| `--host` | `127.0.0.1` | 监听地址，局域网访问用 `0.0.0.0` |
| `--port` | `8080` / WebView 为 `0` | HTTP 端口，WebView 的 `0` 表示自动分配 |

`utils/detect_plate_rdk.py` 常用参数：

| 参数 | 说明 |
| --- | --- |
| `input_source` | 图片、目录、视频或摄像头编号 |
| `--model` | YOLO `.pt` 或 RDK `.bin` |
| `--rec-model` | RDK LPRNet `.bin` |
| `--conf` | YOLO 置信度阈值 |
| `--nms-thres` | NMS IoU 阈值 |
| `--save-crops` | 保存车牌裁切图 |
| `--no-show` | 不弹出窗口，适合 SSH |
| `--output-dir` | 标注输出目录 |

## 10. 提交前验证

PC 环境：

```bash
python -m py_compile web_app.py webview_app.py utils/__init__.py utils/camera_worker.py utils/db_manager.py utils/detect_plate_rdk.py utils/gui_theme.py utils/inference.py utils/plate_utils.py utils/preprocess.py utils/postprocess.py utils/ultralytics_yolo_pose.py test/test_headless.py
python web_app.py --help
python webview_app.py --help
python test/test_headless.py --help
python utils/detect_plate_rdk.py --help
python -c "import web_app; import webview_app; import utils.camera_worker; import utils.db_manager; import utils.inference; import utils.plate_utils; from utils.plate_utils import clean_plate_number; assert clean_plate_number('皖A·S0747') == '皖AS0747'; print('core import smoke OK')"
```

数据库烟测：

```bash
python -c "import tempfile, os, gc; from utils.db_manager import DBManager; fd,p=tempfile.mkstemp(suffix='.db'); os.close(fd); db=DBManager(p); db.record_occurrence('皖AS0747',1); db.record_occurrence('皖AS0747',2); db.record_occurrence('皖AQ4025',3); assert db.query_last_location('皖AS0747')['camera_id']==2; fuzzy=db.query_fuzzy('皖A'); assert {row['plate_number'] for row in fuzzy}=={'皖AS0747','皖AQ4025'}; db=None; gc.collect(); os.remove(p); print('db smoke OK')"
```

RDK 环境：

```bash
python3 -c "import hbm_runtime; print('hbm_runtime OK')"
python3 -c "import cv2, numpy, PIL, pyclipper; print('rdk deps OK')"
python3 web_app.py --help
python3 utils/detect_plate_rdk.py --help
```

## 11. 常见问题

### `ModuleNotFoundError: No module named 'cv2'`

PC：

```bash
conda activate garage_ocr
python -m pip install opencv-python
```

RDK：

```bash
python3 -m pip install --user opencv-python-headless
```

或使用系统包：

```bash
sudo apt install -y python3-opencv
```

### `ModuleNotFoundError: No module named 'PyQt5'`

只启动浏览器 Web 控制台时，不需要 PyQt5，使用：

```bash
python web_app.py --backend none
```

需要桌面 WebView 时：

```bash
python -m pip install PyQt5 PyQtWebEngine
```

RDK 板端不建议为了 WebView 安装 PyQtWebEngine。

### `ModuleNotFoundError: No module named 'paddleocr'`

PC 后端需要 PaddleOCR：

```bash
python -m pip install paddlepaddle paddleocr
```

如果本机是 NVIDIA GPU，请按 PaddlePaddle 官方页面选择与 CUDA 匹配的 `paddlepaddle-gpu` 安装命令。

### `hbm_runtime not found`

这个错误只应该出现在 RDK BPU 后端。处理顺序：

1. 确认在 RDK X5 板端运行，而不是 PC。
2. 确认使用系统 Python：`python3 -c "import sys; print(sys.executable)"`。
3. 确认 RDK OS 镜像版本和厂商 Python SDK 完整。
4. 不要在普通 PC conda 环境里运行 `--backend bpu`。

### 端口被占用

换端口：

```bash
python web_app.py --backend none --port 8090
```

Windows 查看端口：

```powershell
netstat -ano | findstr :8080
```

Linux / RDK 查看端口：

```bash
ss -ltnp | grep 8080
```

### 页面能打开但没有实时画面

按顺序检查：

1. `/api/events` 是否能返回 JSON。
2. `--inputs` 路径是否存在，摄像头编号是否正确。
3. 图片输入是否能被 OpenCV 读取。
4. 终端是否打印推理异常。
5. `vehicle_locator.db` 是否有新记录。

### 能检测但车牌为空

可能原因：

- 车牌裁切太小或角点顺序异常。
- PC PaddleOCR 识别失败或模型下载不完整。
- RDK `lpr.bin` 与 LPRNet 字符表不匹配。
- 图像过暗、反光、运动模糊或车牌角度太大。

RDK 上可先用独立 CLI 保存裁切图：

```bash
python3 utils/detect_plate_rdk.py assets/test_plate.jpg --model models/yolo11m-pose-carplate_bayese_640x640_nv12.bin --rec-model models/lpr.bin --save-crops --no-show
```

PC 上如果使用 `.pt` 模型但没有 RDK LPRNet，可直接用 Web PC 后端验证 PaddleOCR。

### 中文标注显示为方块

安装中文字体。Ubuntu / RDK 可尝试：

```bash
sudo apt install -y fonts-noto-cjk fonts-wqy-microhei
```

Windows 通常已有微软雅黑或黑体。

### RDK 上安装 `requirements.txt` 失败

`requirements.txt` 是 PC 桌面环境依赖，包含 PyQt5 / PyQtWebEngine。RDK 只跑 Web 服务时使用：

```bash
python3 -m pip install --user -r requirements-rdk.txt
```

如果确实需要在 RDK 上显示桌面窗口，需要单独处理 Qt 和系统图形栈，不建议作为默认部署路径。

## 12. 推荐交付流程

PC 开发：

1. 创建 Conda 环境。
2. 安装 `requirements.txt` 和 PC 推理依赖。
3. 用 `--backend none` 验证 Web。
4. 用测试图片运行 `--backend pc`。
5. 跑 `docs/TESTING.md` 中的轻量测试。

RDK 部署：

1. 确认 `hbm_runtime` 可导入。
2. 复制代码和 `.bin` 模型。
3. 安装 `requirements-rdk.txt`。
4. 用 `test/test_headless.py --backend bpu` 做 20 秒自检。
5. 用 `web_app.py --backend bpu --host 0.0.0.0` 启动服务。
6. 从 PC 浏览器访问 `http://<RDK-IP>:8080/`。
7. 需要长期运行时配置 systemd 服务。

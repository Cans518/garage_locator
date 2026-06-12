# 地库车辆定位系统 (Garage Vehicle Locator System)

基于 **Web 控制台 + PyQt WebView 桌面壳** 和地瓜派 **RDK X5 BPU 硬件加速** 的多路摄像头车牌定位与轨迹检索系统。系统会实时读取地库摄像头画面，检测车牌四角，裁切矫正后识别车牌，并把车辆最近一次出现的位置写入本地 SQLite 数据库，方便通过车牌号快速查询“最后出现位置”。

## 功能概览

- 支持最多 4 路摄像头、视频文件或测试图片输入。
- 使用槽位式共享帧缓冲，采集线程只保留每路最新画面，避免视频积压。
- 使用单独推理线程串行调用 PC 或 BPU 后端，降低 BPU 资源冲突风险。
- 支持 PC 测试后端：YOLO pose + PaddleOCR。
- 支持 RDK X5 板端后端：YOLO pose `.bin` + LPRNet `.bin`。
- 使用 SQLite 保存车牌、摄像头编号、时间和车牌裁切图。
- Web 控制台支持实时日志、车牌末次位置查询和路径示意。
- PyQt WebView 桌面壳可把 Web 控制台打包为桌面窗口运行。
- 提供 SSH 无界面自检脚本，便于板端联调。

## 效果展示

系统使用 YOLO pose 模型定位车牌四角，再进行透视变换裁切和字符识别。以下是板端测试图的标注效果：

| 样例一：皖A·S0747 | 样例二：皖A·Q4025 |
| :---: | :---: |
| ![皖A·S0747](assets/output_test_plate_bpu.jpg) | ![皖A·Q4025](assets/output_test_plate2_bpu.jpg) |

## 架构说明

核心并发模型是 **多路采集线程 + 最新帧槽位 + 单线程串行推理**。

1. Web 运行时为每路输入启动一个采集线程，从摄像头、视频或图片源读取画面。
2. 最新帧缓冲区按 `camera_id` 保存画面，新帧覆盖旧帧，保证实时性。
3. 推理线程等待任意通道更新，然后串行取出当前批次帧并调用检测后端。
4. `PCDetectionBackend` 或 `BPUDetectionBackend` 输出统一的 `DetectionResult`。
5. Web API 更新监控画面、通行日志和统计，并通过 `DBManager` 记录车牌出现事件。
6. 查询接口按车牌号查询 SQLite 中的最后出现位置。

更细的模块职责见 [`docs/REPO_MAP.md`](docs/REPO_MAP.md)。

## 目录结构

```text
garage_locator/
├── assets/                     # 测试图片和 README 展示图片
├── docs/
│   ├── INSTALL_AND_DEPLOY.md   # Conda、PC 与 RDK X5 完整部署教程
│   ├── REPO_MAP.md             # 模块地图和数据流
│   └── TESTING.md              # 轻量测试说明
├── models/                     # PC 与板端模型权重
│   ├── yolo11m-pose-carplate.pt
│   ├── yolo11m-pose-carplate_bayese_640x640_nv12.bin
│   └── lpr.bin
├── test/
│   └── test_headless.py        # 板端无界面自检入口
├── utils/                      # 单层方法文件目录
│   ├── camera_worker.py
│   ├── db_manager.py
│   ├── detect_plate_rdk.py
│   ├── gui_theme.py
│   ├── inference.py
│   ├── plate_utils.py
│   ├── preprocess.py
│   ├── postprocess.py
│   └── ultralytics_yolo_pose.py
├── web_app.py                  # Web 控制台服务入口
├── webview_app.py              # PyQt WebView 桌面壳入口
├── web/                        # Web 控制台前端页面
├── requirements.txt
├── requirements-rdk.txt
└── .gitignore
```

`utils/` 保持单层目录，避免方法文件分散。各文件职责见 [`utils/README.md`](utils/README.md)。

## 完整文档

- 从 Conda 安装、PC 环境构建到 RDK X5 部署：[`docs/INSTALL_AND_DEPLOY.md`](docs/INSTALL_AND_DEPLOY.md)
- 仓库结构、模块边界和数据流：[`docs/REPO_MAP.md`](docs/REPO_MAP.md)
- 提交前验证和测试命令：[`docs/TESTING.md`](docs/TESTING.md)
- `utils/` 内部模块说明：[`utils/README.md`](utils/README.md)

## 环境准备（快速版）

基础依赖：

```bash
pip3 install -r requirements.txt
```

PC 端推理还需要安装 `ultralytics`、`paddlepaddle`、`paddleocr`：

```bash
pip3 install ultralytics paddlepaddle paddleocr
```

RDK X5 板端推理需要系统中可导入 `hbm_runtime`。板端只运行浏览器 Web 控制台时建议安装最小依赖：

```bash
pip3 install --user -r requirements-rdk.txt
```

更详细的 Conda 安装、PC 和 RDK 环境构建步骤见 [`docs/INSTALL_AND_DEPLOY.md`](docs/INSTALL_AND_DEPLOY.md)。

Windows PowerShell 可把下面命令里的 `python3` 换成 `python`。

## 运行方式

### 桌面 WebView 控制台（推荐）

```bash
python3 webview_app.py --backend pc
```

该入口会自动启动本地 Web 服务、采集/推理后台线程，并用 PyQt WebView 打开桌面窗口。未指定 `--inputs` 时会从 `assets/` 中取测试图片作为 1 到 4 号通道输入。

Windows + conda 环境：

```powershell
conda run -n garage_ocr python webview_app.py --backend pc
```

指定 4 路输入：

```powershell
conda run -n garage_ocr python webview_app.py --backend pc --inputs assets/test_plate.jpg assets/test_plate2.jpg
```

只查看现有数据库和 Web 页面、不启动推理：

```powershell
conda run -n garage_ocr python webview_app.py --backend none
```

### 浏览器 Web 控制台

```bash
python3 web_app.py --host 127.0.0.1 --port 8080 --backend pc
```

浏览器打开 `http://127.0.0.1:8080/`。Web 端会启动采集/推理线程，实时写入 `vehicle_locator.db`，并提供车牌查询、路径示意、监控证据图和实时通行日志展示。若只想查看现有数据库，可使用 `--backend none`。

### RDK X5 无界面自检

```bash
python3 test/test_headless.py \
  --backend bpu \
  --inputs assets/test_plate.jpg \
  --yolo-bin models/yolo11m-pose-carplate_bayese_640x640_nv12.bin \
  --lpr-bin models/lpr.bin
```

脚本会运行约 20 秒，输出检测日志，并生成 `headless_test.db`。该数据库已被 `.gitignore` 忽略。

### RDK X5 Web 控制台

```bash
python3 web_app.py \
  --backend bpu \
  --host 0.0.0.0 \
  --port 8080 \
  --inputs /dev/video0 assets/test_plate.jpg \
  --yolo-bin models/yolo11m-pose-carplate_bayese_640x640_nv12.bin \
  --lpr-bin models/lpr.bin
```

使用方式：

- 在同一局域网浏览器打开 `http://<RDK-IP>:8080/`。
- 查询框输入车牌并回车，页面会显示末次摄像头、时间、车牌裁切图和路径示意。
- 未配置输入源的通道会使用资源图或空画面占位。

### 独立车牌识别 CLI

`utils/detect_plate_rdk.py` 可单独处理图片、目录、视频或摄像头，适合调试模型和裁切参数：

```bash
python3 utils/detect_plate_rdk.py assets/test_plate.jpg \
  --model models/yolo11m-pose-carplate_bayese_640x640_nv12.bin \
  --rec-model models/lpr.bin \
  --no-show
```

## 测试

轻量验证命令：

```bash
python3 -m py_compile web_app.py webview_app.py utils/*.py test/test_headless.py
python3 web_app.py --help
python3 webview_app.py --help
python3 test/test_headless.py --help
python3 utils/detect_plate_rdk.py --help
```

更多测试说明见 [`docs/TESTING.md`](docs/TESTING.md)。

## 数据与生成物

- 主程序默认数据库：`vehicle_locator.db`。
- 无界面自检数据库：`headless_test.db`。
- 独立识别 CLI 默认输出目录：`output_results/` 或输入目录下的输出目录。
- 车牌裁切调试目录：`plate_crops/`。
- 数据集压缩包和其他 `.zip` 文件。

这些运行生成物均不应提交，已在 `.gitignore` 中忽略。

## 开发约定

- 根目录保留 `web_app.py` 和 `webview_app.py` 作为主入口。
- 方法文件统一放在单层 `utils/` 下。
- 测试和自检入口放在 `test/` 下。
- 车牌几何裁切、文本清洗、图片读写和绘制工具统一放在 `utils/plate_utils.py`。
- BPU runtime 相关封装保持在 `utils/ultralytics_yolo_pose.py` 和 `utils/detect_plate_rdk.py`。
- 修改目录结构后，至少运行 `docs/TESTING.md` 中的轻量测试。

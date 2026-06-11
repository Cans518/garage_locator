# 地库车辆定位系统 (Garage Vehicle Locator System)

这是一个基于 **PyQt5** 和地瓜派 **RDK X5 BPU 硬件加速** 构建的多路摄像头车牌定位与轨迹检索系统。本系统能够实时抓取并处理地库多个摄像头的监控画面，记录所有车辆在各个摄像头的最新通行轨迹，并提供车牌检索功能，帮助迅速确认目标车辆的“最后出现位置”。

---

## 1. 效果展示

本系统使用高精度的 YOLOv11m-pose 模型进行车牌四角检测，定位极度精准，并对车牌进行透视变换裁切后交由 OCR 字符识别模块，以下为系统在板端对测试车牌执行的推理绘制效果：

### 车牌定位与几何切片效果
| 样例一：皖A·S0747 定位与识别 | 样例二：皖A·Q4025 定位与识别 |
| :---: | :---: |
| ![皖A·S0747](assets/output_test_plate_bpu.jpg) | ![皖A·Q4025](assets/output_test_plate2_bpu.jpg) |

---

## 2. 核心架构与多线程设计

由于 BPU（板端神经网络加速核心）在运行前向前向推理时是**串行**的，为防止多路高频视频流同时抢占 BPU 资源造成硬件阻塞与延迟堆积，我们设计了**槽位式共享缓冲区 (FrameBuffer) + 独立串行推理线程**的并发模型：

* **摄像头采集线程 (`CameraGrabber` x 4)**：每个摄像头由一个独立的轻量线程维护。它们只负责从物理摄像头或测试视频文件中拉流，并实时将最新帧写入 `FrameBuffer` 的对应槽位中（若有旧帧则直接覆盖，保证绝对的实时性，消除积压）。支持断线自恢复和视频文件循环播放。
* **共享缓冲槽 (`FrameBuffer`)**：槽位式线程安全缓冲区。
* **独立推理线程 (`InferenceWorker` x 1)**：后台唯一的排他推理线程。当收到画面更新事件时，按顺序从槽位提取待处理帧，串行调起 BPU 执行 YOLO 车牌定位与 LPRNet 车牌识别，绘制框图并把轨迹持久化保存到 SQLite 数据库中。
* **主 UI 线程**：仅负责接收推理线程发送的标注完毕后的视频信号并绘制大屏，完全不参与推理阻塞，保障监控画面极致流畅。

---

## 3. 项目目录结构

```text
garage_locator/
├── assets/                     # 系统资源与效果展示图片
│   ├── test_plate.jpg          # 测试车牌图 1
│   ├── test_plate2.jpg         # 测试车牌图 2
│   ├── output_test_plate_bpu.jpg
│   └── output_test_plate2_bpu.jpg
├── models/                     # PC与板端推理模型权重
│   ├── yolo11m-pose-carplate.pt                       # PC端 PyTorch 模型权重
│   ├── yolo11m-pose-carplate_bayese_640x640_nv12.bin  # 板端 BPU 关键点定位模型
│   └── lpr.bin                                        # 板端 BPU LPRNet 识别模型
├── inference.py                # 统一的推理后端（兼容 PC 与 BPU）
├── camera_worker.py            # 多线程图像采集与串行推理逻辑
├── db_manager.py               # 本地 SQLite 历史轨迹数据库管理器
├── gui_theme.py                # 企业级深色科技监控台 QSS 样式表与离线占位图
├── main.py                     # 全屏监控大屏主控程序
├── test_headless.py            # 板端无显示器 SSH 环境自检工具
├── requirements.txt            # 项目依赖说明书
└── .gitignore                  # Git 忽略配置
```

---

## 4. 快速运行指南

### 4.1 安装依赖
在项目目录下运行以下命令安装基础依赖包：
```bash
pip3 install -r requirements.txt
```

### 4.2 本地测试 (PC 端模拟运行)
如果在开发机电脑上测试，请确保您在 `requirements.txt` 中取消了可选依赖（`ultralytics`, `paddleocr`）的注释并正确完成安装：
```bash
# 启动本地模拟。使用 PC 后端，输入两个测试图片（模拟 2 路通道监控画面）
python3 main.py \
  --backend pc \
  --inputs assets/test_plate.jpg assets/test_plate2.jpg \
  --yolo-model models/yolo11m-pose-carplate.pt
```

### 4.3 板端 SSH 终端自检 (无界面模式)
若通过 SSH 连接到地瓜派（RDK X5），且没有接 HDMI 屏幕，可以使用 `test_headless.py` 进行逻辑联调自检（会自动启动 Qt 事件循环和线程，在后台做车牌检测并写进 SQLite 数据库）：
```bash
python3 test_headless.py \
  --backend bpu \
  --inputs assets/test_plate.jpg \
  --yolo-bin models/yolo11m-pose-carplate_bayese_640x640_nv12.bin \
  --lpr-bin models/lpr.bin
```
*(运行 20 秒后会自动退出，并在当前目录生成 `headless_test.db`，控制台会输出完整的检测识别日志。)*

### 4.4 板端全功能大屏运行 (外接显示器模式)
如果开发板外接了 HDMI 显示屏幕，可以通过以下命令直接拉起全屏深色科技风的监控台：
```bash
# 指定 BPU 加速，并传入两个输入源（例如 /dev/video0 和测试视频），其余通道显示离线占位画面
DISPLAY=:0 python3 main.py \
  --backend bpu \
  --inputs /dev/video0 assets/test_plate.jpg \
  --yolo-bin models/yolo11m-pose-carplate_bayese_640x640_nv12.bin \
  --lpr-bin models/lpr.bin
```
*(查询框输入车牌并按回车即可查找最后出现的摄像头、通行时间及车牌裁切小图。Esc 键可退出全屏监控台。)*

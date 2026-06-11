def get_qss_theme() -> str:
    """返回地库车辆定位系统的主题 QSS 样式表"""
    return """
    /* 主窗口与背景 */
    QMainWindow {
        background-color: #0A0D14;
        color: #E4E6EB;
    }

    /* 标签与常规文字 */
    QLabel {
        color: #E4E6EB;
        font-family: 'Inter', 'Segoe UI', 'Microsoft YaHei';
        font-size: 14px;
    }

    /* 卡片式面板 */
    QFrame#panel_frame {
        background-color: #121824;
        border: 1px solid #1E293B;
        border-radius: 8px;
    }

    /* 监控窗口网格单项样式 */
    QLabel#camera_view {
        background-color: #121824;
        border: 2px solid #1E293B;
        border-radius: 6px;
    }
    QLabel#camera_view[active="true"] {
        border: 2px solid #00F2C3;
    }

    /* 输入框 */
    QLineEdit {
        background-color: #1B2436;
        border: 1px solid #2D3D5A;
        border-radius: 6px;
        padding: 8px 12px;
        color: #FFFFFF;
        font-size: 14px;
        font-family: 'Segoe UI', 'Microsoft YaHei';
    }
    QLineEdit:focus {
        border: 1px solid #1F8EF1;
        background-color: #202B41;
    }

    /* 按钮样式 */
    QPushButton {
        background-color: #1F8EF1;
        color: #FFFFFF;
        border: none;
        border-radius: 6px;
        padding: 9px 16px;
        font-weight: bold;
        font-size: 14px;
        font-family: 'Segoe UI', 'Microsoft YaHei';
    }
    QPushButton:hover {
        background-color: #389BFA;
    }
    QPushButton:pressed {
        background-color: #0C7CD5;
    }

    /* 日志列表框 */
    QListWidget {
        background-color: #121824;
        border: 1px solid #1E293B;
        border-radius: 8px;
        padding: 4px;
        color: #A0AEC0;
        font-size: 13px;
        font-family: 'Consolas', 'Monaco', 'Microsoft YaHei';
    }
    QListWidget::item {
        border-bottom: 1px solid #1E293B;
        padding: 8px 6px;
    }
    QListWidget::item:hover {
        background-color: #1B2436;
        color: #FFFFFF;
        border-radius: 4px;
    }

    /* 滚动条 */
    QScrollBar:vertical {
        border: none;
        background: #0D111A;
        width: 8px;
        margin: 0px;
    }
    QScrollBar::handle:vertical {
        background: #2D3D5A;
        min-height: 20px;
        border-radius: 4px;
    }
    QScrollBar::handle:vertical:hover {
        background: #1F8EF1;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }
    """

def get_no_signal_pixmap(width=640, height=480, name="Camera"):
    """使用 OpenCV 动态生成一个科技感十足的 'NO SIGNAL' 占位图"""
    import cv2
    import numpy as np
    
    # 建立暗灰蓝色背景
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:, :] = (20, 16, 11)  # BGR 格式的深蓝色底 `#0B1014`

    # 画一些科技风的网格线
    grid_size = 40
    for y in range(0, height, grid_size):
        cv2.line(img, (0, y), (width, y), (30, 26, 20), 1)
    for x in range(0, width, grid_size):
        cv2.line(img, (x, 0), (x, height), (30, 26, 20), 1)

    # 画科技风的四角框标记
    pad = 20
    length = 30
    color = (90, 80, 70) # 灰色科技框
    # 左上
    cv2.line(img, (pad, pad), (pad + length, pad), color, 2)
    cv2.line(img, (pad, pad), (pad, pad + length), color, 2)
    # 右上
    cv2.line(img, (width - pad, pad), (width - pad - length, pad), color, 2)
    cv2.line(img, (width - pad, pad), (width - pad, pad + length), color, 2)
    # 左下
    cv2.line(img, (pad, height - pad), (pad + length, height - pad), color, 2)
    cv2.line(img, (pad, height - pad), (pad, height - pad - length), color, 2)
    # 右下
    cv2.line(img, (width - pad, height - pad), (width - pad - length, height - pad), color, 2)
    cv2.line(img, (width - pad, height - pad), (width - pad, height - pad - length), color, 2)

    # 绘制文字 "SIGNAL LOSS" 或 "NO SIGNAL"
    text1 = f"{name} - OFFLINE"
    text2 = "NO VIDEO SIGNAL"
    
    font = cv2.FONT_HERSHEY_SIMPLEX
    # 第一排文字
    t1_size = cv2.getTextSize(text1, font, 0.7, 2)[0]
    t1_x = (width - t1_size[0]) // 2
    t1_y = height // 2 - 15
    cv2.putText(img, text1, (t1_x, t1_y), font, 0.7, (140, 130, 120), 2, cv2.LINE_AA)

    # 第二排文字
    t2_size = cv2.getTextSize(text2, font, 0.6, 1)[0]
    t2_x = (width - t2_size[0]) // 2
    t2_y = height // 2 + 20
    cv2.putText(img, text2, (t2_x, t2_y), font, 0.6, (90, 80, 70), 1, cv2.LINE_AA)

    return img

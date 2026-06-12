def get_qss_theme() -> str:
    """返回地库车辆定位系统的主题 QSS 样式表"""
    return """
    QMainWindow {
        background-color: #F1F5F9; /* slate-100 */
        color: #0F172A;            /* slate-900 */
    }

    QLabel {
        color: #0F172A;
        font-family: 'Microsoft YaHei UI', 'Segoe UI', 'Microsoft YaHei';
        font-size: 18px;
    }

    QLabel#app_title {
        color: #0F172A;
        font-size: 34px;
        font-weight: 800;
    }

    QLabel#app_subtitle {
        color: #64748B; /* slate-500 */
        font-size: 18px;
    }

    QLabel#section_title {
        color: #0F172A;
        font-size: 21px;
        font-weight: 800;
    }

    QLabel#rail_title {
        color: #334155; /* slate-700 */
        font-size: 18px;
        font-weight: 800;
    }

    QLabel#result_text {
        color: #0F172A;
        background: transparent;
        font-size: 20px;
        line-height: 1.5;
    }

    QLabel#hint_text {
        color: #64748B;
        font-size: 16px;
    }

    QLabel#top_time {
        color: #475569;
        font-size: 16px;
        font-weight: 600;
    }

    QFrame#top_bar {
        background-color: #FFFFFF;
        border: 1px solid #D8E2EA;
        border-radius: 12px;
    }

    QFrame#primary_panel,
    QFrame#side_panel,
    QFrame#rail_card,
    QFrame#result_card {
        background-color: #FFFFFF;
        border: 1px solid #D8E2EA;
        border-radius: 12px;
    }

    QFrame#search_card {
        background-color: #F8FBFD;
        border: 1px solid #BAE6FD; /* sky-200 */
        border-radius: 12px;
    }

    QLabel#status_pill {
        background-color: #ECFDF5; /* emerald-50 */
        color: #047857;            /* emerald-700 */
        border: 1px solid #A7F3D0; /* emerald-200 */
        border-radius: 16px;
        padding: 7px 14px;
        font-weight: 800;
        font-size: 14px;
    }

    QLabel#soft_pill {
        background-color: #F0F9FF; /* sky-50 */
        color: #0369A1;            /* sky-700 */
        border: 1px solid #BAE6FD; /* sky-200 */
        border-radius: 16px;
        padding: 7px 14px;
        font-weight: 800;
        font-size: 14px;
    }

    QFrame#metric_card {
        background-color: #F8FBFD;
        border: 1px solid #D8E2EA;
        border-radius: 12px;
    }

    QLabel#metric_value {
        color: #0891B2; /* cyan-600 */
        font-size: 30px;
        font-weight: 900;
    }

    QLabel#metric_label {
        color: #64748B;
        font-size: 15px;
        font-weight: 700;
    }

    QLabel#plate_crop {
        background-color: #F8FAFC;
        border: 1px solid #CBD5E1;
        border-radius: 10px;
    }

    QLabel#camera_view {
        background-color: #0F172A;
        border: 1px solid #CBD5E1;
        border-radius: 10px;
    }
    QLabel#camera_view[active="true"] {
        border: 2px solid #10B981;
    }

    QLineEdit {
        background-color: #FFFFFF;
        border: 1px solid #CBD5E1;
        border-radius: 10px;
        padding: 12px 18px;
        color: #0F172A;
        font-size: 24px;
        font-weight: 800;
        font-family: 'Microsoft YaHei UI', 'Segoe UI', 'Microsoft YaHei';
        selection-background-color: #A5F3FC;
    }
    QLineEdit:focus {
        border: 2px solid #06B6D4;
        background-color: #F8FBFD;
    }

    QPushButton {
        background-color: #06B6D4; /* cyan-500 */
        color: #FFFFFF;
        border: none;
        border-radius: 10px;
        padding: 12px 22px;
        font-weight: 800;
        font-size: 21px;
        font-family: 'Microsoft YaHei UI', 'Segoe UI', 'Microsoft YaHei';
    }
    QPushButton:hover {
        background-color: #0891B2; /* cyan-600 */
    }
    QPushButton:pressed {
        background-color: #0E7490; /* cyan-700 */
        color: #F8FAFC;
    }

    QListWidget {
        background-color: #F8FAFC;
        border: 1px solid #D8E2EA;
        border-radius: 10px;
        padding: 6px;
        color: #334155;
        font-size: 15px;
        font-family: 'Consolas', 'Monaco', 'Microsoft YaHei';
    }
    QListWidget::item {
        border-bottom: 1px solid #E2E8F0;
        padding: 8px 10px;
    }
    QListWidget::item:hover {
        background-color: #E0F2FE;
        color: #0F172A;
        border-radius: 6px;
    }

    QScrollBar:vertical {
        border: none;
        background: #F1F5F9;
        width: 8px;
        margin: 0px;
    }
    QScrollBar::handle:vertical {
        background: #CBD5E1;
        min-height: 20px;
        border-radius: 4px;
    }
    QScrollBar::handle:vertical:hover {
        background: #06B6D4;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }
    """

def get_no_signal_pixmap(width=640, height=480, name="Camera"):
    """使用 OpenCV 动态生成一个清爽冷色的 'NO SIGNAL' 占位图"""
    import cv2
    import numpy as np
    
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:, :] = (42, 31, 15)  # BGR: slate-900

    grid_size = 40
    for y in range(0, height, grid_size):
        cv2.line(img, (0, y), (width, y), (58, 45, 30), 1)
    for x in range(0, width, grid_size):
        cv2.line(img, (x, 0), (x, height), (58, 45, 30), 1)

    pad = 20
    length = 30
    color = (212, 180, 103)  # cyan-300 in BGR
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

    text1 = f"{name} - OFFLINE"
    text2 = "NO VIDEO SIGNAL"
    
    font = cv2.FONT_HERSHEY_SIMPLEX
    # 第一排文字
    t1_size = cv2.getTextSize(text1, font, 0.7, 2)[0]
    t1_x = (width - t1_size[0]) // 2
    t1_y = height // 2 - 15
    cv2.putText(img, text1, (t1_x, t1_y), font, 0.7, (241, 245, 249), 2, cv2.LINE_AA)

    t2_size = cv2.getTextSize(text2, font, 0.6, 1)[0]
    t2_x = (width - t2_size[0]) // 2
    t2_y = height // 2 + 20
    cv2.putText(img, text2, (t2_x, t2_y), font, 0.6, (226, 232, 240), 1, cv2.LINE_AA)

    return img

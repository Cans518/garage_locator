import sqlite3
import datetime
import cv2
import numpy as np

class DBManager:
    """车辆历史轨迹数据库管理器"""
    def __init__(self, db_path="vehicle_locator.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vehicle_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plate_number TEXT NOT NULL,
                    camera_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    crop_image BLOB
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_plate_number 
                ON vehicle_history (plate_number)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON vehicle_history (timestamp)
            """)
            conn.commit()

    def record_occurrence(self, plate_number: str, camera_id: int, crop_img: np.ndarray = None):
        """记录一次车辆车牌检测事件"""
        if not plate_number:
            return

        # 获取当前时间
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 将 OpenCV 图像编码为二进制 JPG 字节流
        img_blob = None
        if crop_img is not None and crop_img.size > 0:
            ok, encoded_img = cv2.imencode(".jpg", crop_img)
            if ok:
                img_blob = sqlite3.Binary(encoded_img.tobytes())

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO vehicle_history (plate_number, camera_id, timestamp, crop_image)
                VALUES (?, ?, ?, ?)
            """, (plate_number, camera_id, timestamp, img_blob))
            conn.commit()

    def query_last_location(self, plate_number: str) -> dict | None:
        """根据车牌号精确查询该车最后出现的信息"""
        if not plate_number:
            return None

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT camera_id, timestamp, crop_image 
                FROM vehicle_history 
                WHERE plate_number = ? 
                ORDER BY timestamp DESC 
                LIMIT 1
            """, (plate_number,))
            row = cursor.fetchone()

        if not row:
            return None

        camera_id, timestamp, img_blob = row
        crop_img = None
        if img_blob:
            # 还原 OpenCV 图像
            nparr = np.frombuffer(img_blob, np.uint8)
            crop_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        return {
            "camera_id": camera_id,
            "timestamp": timestamp,
            "crop_image": crop_img
        }

    def query_fuzzy(self, search_term: str) -> list[dict]:
        """模糊查找包含关键词的所有车牌最新记录"""
        if not search_term:
            return []

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT plate_number, camera_id, timestamp 
                FROM vehicle_history 
                WHERE plate_number LIKE ? 
                GROUP BY plate_number 
                ORDER BY timestamp DESC
            """, (f"%{search_term}%",))
            rows = cursor.fetchall()

        results = []
        for row in rows:
            results.append({
                "plate_number": row[0],
                "camera_id": row[1],
                "timestamp": row[2]
            })
        return results

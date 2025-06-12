import torch
import numpy as np
import cv2
from typing import Tuple, List, Dict

class YOLODetector:
    def __init__(self, model_path: str = "/home/thanhkhaii/pbl5/yolov5/best.pt"):  # Sử dụng đường dẫn tuyệt đối
        """Khởi tạo YOLOv5 model."""
        self.model = torch.hub.load('ultralytics/yolov5', 'custom', path=model_path, force_reload=True)
        print("YOLOv5 model loaded successfully")

    def detect(self, frame: np.ndarray) -> Tuple[np.ndarray, List[Dict]]:
        """Phát hiện đối tượng trong frame và trả về frame đã vẽ và detections."""
        results = self.model(frame)
        detections = results.pandas().xyxy[0]
        labels = detections['name'].tolist()
        print("Phát hiện:", labels)

        for _, det in detections.iterrows():
            x1, y1, x2, y2 = int(det['xmin']), int(det['ymin']), int(det['xmax']), int(det['ymax'])
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
            cv2.putText(frame, det['name'], (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)

        detection_data = [
            {'label': row['name'], 'x1': row['xmin'], 'y1': row['ymin'], 'x2': row['xmax'], 'y2': row['ymax']}
            for _, row in detections.iterrows()
        ]
        return frame, detection_data
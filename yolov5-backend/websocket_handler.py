import base64
import cv2
import time
import asyncio
from fastapi import WebSocket
from .esp32_interface import get_image_from_esp32, get_ultrasonic_distance
from .yolo_detection import YOLODetector

class WebSocketHandler:
    def __init__(self, yolo_detector: YOLODetector, navigation_complete: asyncio.Event, robot_controller):  # Thêm robot_controller
        self.yolo_detector = yolo_detector
        self.navigation_complete = navigation_complete
        self.active_connections: list[WebSocket] = []
        self.robot_controller = robot_controller  # Lưu tham chiếu đến RobotController

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"WebSocket connected: {websocket.client}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        print(f"WebSocket disconnected: {websocket.client}")

# Trong websocket_handler.py
    async def stream_video(self):
        while True:
            if not self.robot_controller.robot_running:
                await asyncio.sleep(0.1)
                continue

            try:
                frame = get_image_from_esp32()
                if frame is None:
                    print("No frame from ESP32-CAM, skipping...")
                    await asyncio.sleep(1)
                    continue

                ultrasonic_distance = get_ultrasonic_distance()
                frame, detections = self.yolo_detector.detect(frame)

                _, buffer = cv2.imencode('.jpg', frame)
                img_str = base64.b64encode(buffer).decode('utf-8')
                #print("Base64 length:", len(img_str), "Sample:", img_str[:50])

                data = {
                    'image': img_str,
                    'detections': detections,
                    'ultrasonic_distance': ultrasonic_distance
                }

                for connection in self.active_connections:
                    try:
                        await connection.send_json(data)
                        print(f"Sent data to {connection.client}")
                    except Exception as e:
                        print(f"Error sending to {connection.client}: {e}")
                        self.active_connections.remove(connection)
                await asyncio.sleep(0.1)
            except Exception as e:
                print(f"Error in stream_video: {e}")
                await asyncio.sleep(1)
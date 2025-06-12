import requests
import numpy as np
import cv2
from typing import Optional, Tuple

# Địa chỉ ESP32-CAM
ESP32_CAM_URL = "http://192.168.107.231/cam.jpg"
ESP32_CONTROL_URL = "http://192.168.107.231/command"
ESP32_ULTRASONIC_URL = "http://192.168.107.231/ultrasonic"

def get_image_from_esp32() -> Optional[np.ndarray]:
    """Lấy hình ảnh từ ESP32-CAM và trả về dưới dạng numpy array."""
    try:
        response = requests.get(ESP32_CAM_URL, stream=True, timeout=10)
        img_array = np.asarray(bytearray(response.content), dtype=np.uint8)
        frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if frame is None:
            print("Error: Could not decode frame from ESP32-CAM.")
            return None
        return frame
    except Exception as e:
        print(f"Error fetching image: {e}")
        return None

def get_ultrasonic_distance() -> float:
    """Lấy dữ liệu siêu âm từ ESP32-CAM."""
    try:
        response = requests.get(ESP32_ULTRASONIC_URL, timeout=10)
        if response.status_code == 200:
            data = response.json()
            distance = data.get("distance", -1)
            if distance < 0 or distance > 400:
                print(f"Dữ liệu siêu âm không hợp lệ: {distance} cm, bỏ qua")
                return -1
            print(f"Đọc dữ liệu siêu âm: {distance} cm")
            return distance
        else:
            print(f"Lỗi đọc dữ liệu siêu âm, status code: {response.status_code}")
            return -1
    except Exception as e:
        print(f"Lỗi kết nối siêu âm: {e}")
        return -1

def control_robot(command: str, speed: int) -> bool:
    """Gửi lệnh điều khiển đến ESP32-CAM."""
    try:
        if command in ["S", "stop"]:
            full_command = "S"
        else:
            full_command = f"{command},{speed},{speed}"
        url = f"{ESP32_CONTROL_URL}?cmd={full_command}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            print(f"Sent command: {full_command}")
            return True
        else:
            print(f"Failed to send command, status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"Gửi lệnh thất bại: {e}")
        return False
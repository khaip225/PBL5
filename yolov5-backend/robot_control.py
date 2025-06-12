from heapq import heappush, heappop
import time
import threading
from typing import List, Tuple, Optional
from .esp32_interface import control_robot, get_ultrasonic_distance, get_image_from_esp32
from .yolo_detection import YOLODetector
import cv2

# Cấu hình
GRID_SIZE = (5, 7)
obstacles = {
    (0,1), (0,2),
    (1,1), (1,4), (1,6),
    (2,3), (2,4),
    (3,0), (3,1), (3,5),
    (4,3)
}
MAX_SPEED_CM_PER_SEC = 100
CELL_SIZE_CM = 8
TURN_90_DEGREE_TIME = 1
MOVE_TIME = 0.008

class RobotController:
    def __init__(self, yolo_detector: YOLODetector):
        self.current_speed = 120
        self.current_direction = "backward"
        self.current_position: Optional[Tuple[int, int]] = None
        self.goal_position: Optional[Tuple[int, int]] = None
        self.path: List[Tuple[int, int]] = []
        self.path_index = 0
        self.last_intersection_time = time.time()
        self.robot_running = False
        self.stop_event = threading.Event()
        self.navigation_complete = threading.Event()
        self.traffic_light_state = "green"
        self.yolo_detector = yolo_detector

    def manhattan_distance(self, pos1: Tuple[int, int], pos2: Tuple[int, int]) -> int:
        return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])

    def a_star(self, start: Tuple[int, int], goal: Tuple[int, int]) -> List[Tuple[int, int]]:
        if start in obstacles or goal in obstacles:
            return []
        open_set = []
        heappush(open_set, (0, start))
        came_from = {}
        g_score = {start: 0}
        f_score = {start: self.manhattan_distance(start, goal)}
        while open_set:
            _, current = heappop(open_set)
            if current == goal:
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                path.append(start)
                return path[::-1]
            directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
            for dx, dy in directions:
                next_pos = (current[0] + dx, current[1] + dy)
                if (0 <= next_pos[0] < GRID_SIZE[0] and 0 <= next_pos[1] < GRID_SIZE[1] and
                    next_pos not in obstacles):
                    tentative_g_score = g_score[current] + 1
                    if next_pos not in g_score or tentative_g_score < g_score[next_pos]:
                        came_from[next_pos] = current
                        g_score[next_pos] = tentative_g_score
                        f_score[next_pos] = tentative_g_score + self.manhattan_distance(next_pos, goal)
                        heappush(open_set, (f_score[next_pos], next_pos))
        return []

    def get_next_direction(self, current_pos: Tuple[int, int], next_pos: Tuple[int, int], current_dir: str) -> str:
        dx = next_pos[0] - current_pos[0]
        dy = next_pos[1] - current_pos[1]
        if dx == 1 and dy == 0:
            target_direction = "backward"
        elif dx == -1 and dy == 0:
            target_direction = "up"
        elif dx == 0 and dy == 1:
            target_direction = "right"
        elif dx == 0 and dy == -1:
            target_direction = "left"
        else:
            target_direction = current_dir
        if current_dir == target_direction:
            return "B"
        if current_dir == "backward":
            if target_direction == "right":
                return "R"
            elif target_direction == "left":
                return "L"
            elif target_direction == "up":
                return "R"
        if current_dir == "right":
            if target_direction == "backward":
                return "L"
            elif target_direction == "up":
                return "R"
            elif target_direction == "left":
                return "L"
        if current_dir == "left":
            if target_direction == "backward":
                return "R"
            elif target_direction == "up":
                return "L"
            elif target_direction == "right":
                return "R"
        if current_dir == "up":
            if target_direction == "right":
                return "L"
            elif target_direction == "left":
                return "R"
            elif target_direction == "backward":
                return "R"
        return "B"

    def calculate_time_to_travel_cell(self) -> float:
        if self.current_speed == 120:
            return MOVE_TIME
        return 0.01 * 120 / self.current_speed

    def turn_90_degrees(self, turn_direction: str):
        print(f"Turning {turn_direction} for 90 degrees...")
        control_robot(turn_direction, self.current_speed)
        time.sleep(TURN_90_DEGREE_TIME)
        control_robot("S", self.current_speed)
        print(f"Finished turning {turn_direction}")

    def start_navigation(self, start: Tuple[int, int], goal: Tuple[int, int]):
        self.current_position = start
        self.goal_position = goal
        self.current_direction = "backward"
        self.path = self.a_star(start, goal)
        self.path_index = 0
        self.last_intersection_time = time.time()
        self.robot_running = True
        self.stop_event.clear()
        self.navigation_complete.clear()
        print("Lộ trình A*:", self.path)
        return self.path

    def stop_navigation(self):
        self.robot_running = False
        self.navigation_complete.set()
        self.stop_event.set()
        control_robot("S", self.current_speed)

    def run(self):
        while True:
            if self.stop_event.is_set() or not self.robot_running:
                print("Robot dừng hoặc không chạy")
                time.sleep(1)
                continue
            try:
                ultrasonic_distance = get_ultrasonic_distance()
                frame = get_image_from_esp32()
                if frame is None:
                    print("Error: Could not decode frame.")
                    time.sleep(2)
                    continue

                frame, detections = self.yolo_detector.detect(frame)
                labels = [det['label'] for det in detections]
                print("Phát hiện:", labels)

                command = "B"
                command_sent = False

                if 'Red-light' in labels:
                    self.traffic_light_state = "red"
                    command = "S"
                    control_robot(command, self.current_speed)
                    command_sent = True
                    print("Dừng do đèn đỏ")
                elif 'Green-light' in labels:
                    self.traffic_light_state = "green"
                elif self.traffic_light_state == "red":
                    command = "S"
                    control_robot(command, self.current_speed)
                    command_sent = True
                    print("Dừng do trạng thái đèn đỏ trước đó")

                if not command_sent and 'No-entry' in labels:
                    command = "S"
                    control_robot(command, self.current_speed)
                    command_sent = True
                    print("Dừng do biển cấm")

                if not command_sent:
                    car_detected = False
                    for det in detections:
                        if det['label'] == 'Car':
                            car_detected = True
                            x1, y1, x2, y2 = det['x1'], det['y1'], det['x2'], det['y2']
                            bbox_height = y2 - y1
                            print(f"Phát hiện xe, bbox height: {bbox_height}")

                            if ultrasonic_distance >= 0 and ultrasonic_distance < 10:
                                if bbox_height > 300:
                                    command = "S"
                                    print(f"Xe quá gần (bbox height: {bbox_height}, siêu âm: {ultrasonic_distance} cm), dừng lại")
                                elif bbox_height > 200:
                                    self.current_speed = max(80, self.current_speed - 20)
                                    command = "B"
                                    print(f"Xe gần (bbox height: {bbox_height}, siêu âm: {ultrasonic_distance} cm), giảm tốc xuống {self.current_speed}")
                                else:
                                    command = "B"
                            else:
                                if bbox_height > 300:
                                    command = "S"
                                    print(f"Xe quá gần (bbox height: {bbox_height}), dừng lại")
                                elif bbox_height > 200:
                                    self.current_speed = max(80, self.current_speed - 20)
                                    command = "B"
                                    print(f"Xe gần (bbox_height: {bbox_height}), giảm tốc xuống {self.current_speed}")
                                elif bbox_height < 100:
                                    self.current_speed = min(140, self.current_speed + 20)
                                    command = "B"
                                    print(f"Xe xa (bbox height: {bbox_height}), tăng tốc lên {self.current_speed}")
                            break

                    if not car_detected and ultrasonic_distance >= 0 and ultrasonic_distance < 10:
                        self.current_speed = max(80, self.current_speed - 20)
                        command = "B"
                        print(f"Vật cản gần (siêu âm: {ultrasonic_distance} cm), giảm tốc xuống {self.current_speed}")

                if not command_sent and self.traffic_light_state == "green":
                    time_to_travel_cell = self.calculate_time_to_travel_cell()
                    if time.time() - self.last_intersection_time > time_to_travel_cell:
                        if self.path_index < len(self.path):
                            self.path_index += 1
                            self.current_position = self.path[self.path_index - 1]
                            print(f"Giả định đã đến ô: {self.current_position} (dựa trên dead reckoning)")
                            self.last_intersection_time = time.time()
                        if self.current_position == self.goal_position:
                            print("Đã đến đích!")
                            command = "S"
                            control_robot(command, self.current_speed)
                            self.robot_running = False
                            self.navigation_complete.set()
                            break
                        if self.current_position is None:
                            print("Lỗi: current_position không được định nghĩa!")
                            self.robot_running = False
                            self.navigation_complete.set()
                            break
                        next_pos = self.path[self.path_index]
                        command = self.get_next_direction(self.current_position, next_pos, self.current_direction)
                        print(f"Đi từ {self.current_position} đến {next_pos}, lệnh: {command}, hướng hiện tại: {self.current_direction}")
                        dx = next_pos[0] - self.current_position[0]
                        dy = next_pos[1] - self.current_position[1]
                        if dx == 1 and dy == 0:
                            target_direction = "backward"
                        elif dx == -1 and dy == 0:
                            target_direction = "up"
                        elif dx == 0 and dy == 1:
                            target_direction = "right"
                        elif dx == 0 and dy == -1:
                            target_direction = "left"
                        else:
                            target_direction = self.current_direction
                        if command == "B":
                            control_robot(command, self.current_speed)
                        elif command in ["R", "L"]:
                            self.turn_90_degrees(command)
                            if (self.current_direction == "backward" and target_direction == "up") or \
                               (self.current_direction == "up" and target_direction == "backward") or \
                               (self.current_direction == "right" and target_direction == "left") or \
                               (self.current_direction == "left" and target_direction == "right"):
                                print("Cần quay 180 độ, thực hiện quay 90 độ lần 2...")
                                self.turn_90_degrees(command)
                        if command == "R":
                            if self.current_direction == "backward":
                                self.current_direction = "right"
                            elif self.current_direction == "right":
                                self.current_direction = "up"
                            elif self.current_direction == "up":
                                self.current_direction = "left"
                            elif self.current_direction == "left":
                                self.current_direction = "backward"
                        elif command == "L":
                            if self.current_direction == "backward":
                                self.current_direction = "left"
                            elif self.current_direction == "left":
                                self.current_direction = "up"
                            elif self.current_direction == "up":
                                self.current_direction = "right"
                            elif self.current_direction == "right":
                                self.current_direction = "backward"

                if not command_sent:
                    control_robot(command, self.current_speed)
                    command_sent = True

                time.sleep(0.5)
            except Exception as e:
                print("Lỗi:", e)
                time.sleep(2)
                continue
        cv2.destroyAllWindows()
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import asyncio
import threading
from typing import Dict, List, Tuple
from pydantic import BaseModel
from .robot_control import RobotController
from .yolo_detection import YOLODetector
from .websocket_handler import WebSocketHandler

app = FastAPI()

# Thiết lập CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Khởi tạo các thành phần
yolo_detector = YOLODetector()
robot_controller = RobotController(yolo_detector)
navigation_complete = asyncio.Event()
websocket_handler = WebSocketHandler(yolo_detector, navigation_complete, robot_controller)  # Truyền robot_controller

# Chạy robot_controller trong một thread riêng
robot_thread = None

class NavigationRequest(BaseModel):
    start: List[int]
    end: List[int]

@app.post("/start-navigation")
async def start_navigation(request: NavigationRequest) -> Dict:
    global robot_thread
    start = tuple(request.start)
    end = tuple(request.end)

    if not (0 <= start[0] < 5 and 0 <= start[1] < 7):
        raise HTTPException(status_code=400, detail="Vị trí đầu không hợp lệ!")
    if not (0 <= end[0] < 5 and 0 <= end[1] < 7):
        raise HTTPException(status_code=400, detail="Vị trí đích không hợp lệ!")

    if robot_thread and robot_thread.is_alive():
        robot_controller.stop_navigation()
        robot_thread.join(timeout=2)
        navigation_complete.set()

    path = robot_controller.start_navigation(start, end)

    robot_thread = threading.Thread(target=robot_controller.run, daemon=True)
    robot_thread.start()

    return {'path': path, 'status': 'navigation_started'}

@app.post("/stop-navigation")
async def stop_navigation() -> Dict:
    robot_controller.stop_navigation()
    return {"status": "stopped"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket_handler.connect(websocket)
    try:
        while True:
            # Giữ kết nối WebSocket mở
            await websocket.receive_text()
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        websocket_handler.disconnect(websocket)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(websocket_handler.stream_video())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
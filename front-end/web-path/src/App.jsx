import React, { useState, useEffect, useRef } from "react";
import axios from "axios";

const rows = 5;
const cols = 7;
const cellSize = 50;

const obstacles = [
  [0, 1], [0, 2],
  [1, 1], [1, 4], [1, 6],
  [2, 3], [2, 4],
  [3, 0], [3, 1], [3, 5],
  [4, 3],
];

const isObstacle = (r, c) => obstacles.some(([x, y]) => x === r && y === c);

export default function App() {
  const [start, setStart] = useState(null);
  const [end, setEnd] = useState(null);
  const [path, setPath] = useState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [robotRunning, setRobotRunning] = useState(false);
  const [streamImage, setStreamImage] = useState(null);
  const [detections, setDetections] = useState([]);
  const [ultrasonicDistance, setUltrasonicDistance] = useState(null);
  const mapCanvasRef = useRef(null);
  const ws = useRef(null);

  useEffect(() => {
    ws.current = new WebSocket('ws://localhost:8000/ws');

    ws.current.onopen = () => {
      console.log('WebSocket connected');
    };

    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log('Received stream data:', data);
      if (data && data.image) {
        const imgSrc = `data:image/jpeg;base64,${data.image}`;
        setStreamImage(imgSrc);
        const img = new Image();
        img.onload = () => {
          console.log('Image loaded, size:', img.width, 'x', img.height);
        };
        img.onerror = (e) => {
          console.error('Image load error:', e);
        };
        img.src = imgSrc;
      }
      setDetections(data.detections || []);
      setUltrasonicDistance(data.ultrasonic_distance || null);
    };

    ws.current.onclose = () => {
      console.log('WebSocket disconnected');
    };

    ws.current.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    drawMap(); // Vẽ bản đồ ban đầu

    return () => {
      if (ws.current) ws.current.close();
    };
  }, [path]); // Dependency path để vẽ lại khi path thay đổi

  const handleClick = (r, c) => {
    if (isObstacle(r, c)) return;
    if (!start) {
      setStart([r, c]);
      setMessage(`Đã chọn điểm bắt đầu: (${r}, ${c})`);
    } else if (!end && (r !== start[0] || c !== start[1])) {
      setEnd([r, c]);
      setMessage(`Đã chọn điểm kết thúc: (${r}, ${c})`);
    }
    drawMap();
  };

  const startNavigation = async () => {
    if (!start || !end) {
      setMessage("Vui lòng chọn điểm bắt đầu và kết thúc!");
      return;
    }
    if (start[0] === end[0] && start[1] === end[1]) {
      setMessage("Điểm bắt đầu và điểm kết thúc không được trùng nhau!");
      return;
    }
    setLoading(true);
    setMessage("Đang gửi yêu cầu điều hướng...");
    try {
      const res = await axios.post("http://localhost:8000/start-navigation", { start, end });
      setPath(res.data.path || []);
      setRobotRunning(true);
      setMessage("Robot đã bắt đầu di chuyển!");
      drawMap(); // Vẽ lại bản đồ sau khi nhận path
      console.log("Path received:", res.data.path);
    } catch (err) {
      console.error("Lỗi startNavigation:", err);
      setMessage(err.response?.data?.message || "Không thể bắt đầu điều hướng. Kiểm tra backend!");
    } finally {
      setLoading(false);
    }
  };

  const stopNavigation = async () => {
    setLoading(true);
    setMessage("Đang gửi yêu cầu dừng robot...");
    try {
      await axios.post("http://localhost:8000/stop-navigation");
      setRobotRunning(false);
      setMessage("Robot đã dừng!");
    } catch (err) {
      console.error("Lỗi stopNavigation:", err);
      setMessage("Không thể dừng robot. Kiểm tra backend!");
    } finally {
      setLoading(false);
    }
  };

  const resetGrid = () => {
    setStart(null);
    setEnd(null);
    setPath([]);
    setRobotRunning(false);
    drawMap();
    setMessage("Đã reset lưới. Chọn lại điểm bắt đầu và kết thúc.");
  };

  const drawMap = () => {
    const canvas = mapCanvasRef.current;
    if (!canvas) {
      console.log("Canvas không tồn tại!");
      return;
    }
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        ctx.strokeStyle = "#d1d5db";
        ctx.strokeRect(c * cellSize, r * cellSize, cellSize, cellSize);

        if (isObstacle(r, c)) {
          ctx.fillStyle = "#ffffff";
          ctx.fillRect(c * cellSize, r * cellSize, cellSize, cellSize);
        } else {
          ctx.fillStyle = "#000000";
          ctx.fillRect(c * cellSize, r * cellSize, cellSize, cellSize);
        }
      }
    }

    path.forEach(([r, c]) => {
      if (!isObstacle(r, c) && r >= 0 && r < rows && c >= 0 && c < cols) {
        ctx.fillStyle = "#22c55e";
        ctx.fillRect(c * cellSize, r * cellSize, cellSize, cellSize);
      }
    });

    if (start) {
      ctx.fillStyle = "#ef4444";
      ctx.fillRect(start[1] * cellSize + 2, start[0] * cellSize + 2, cellSize - 4, cellSize - 4);
    }

    if (end) {
      ctx.fillStyle = "#3b82f6";
      ctx.fillRect(end[1] * cellSize + 2, end[0] * cellSize + 2, cellSize - 4, cellSize - 4);
    }
    console.log("Map drawn with path:", path);
  };

  return (
    <div className="p-4 max-w-6xl mx-auto">
      <h1 className="text-xl font-bold mb-4 text-center">Robot Pathfinder</h1>
      <div className="flex flex-row space-x-4">
        <div>
          <canvas
            ref={mapCanvasRef}
            width={cols * cellSize}
            height={rows * cellSize}
            style={{ border: "1px solid #d1d5db" }}
            onClick={(e) => {
              const rect = e.target.getBoundingClientRect();
              const x = e.clientX - rect.left;
              const y = e.clientY - rect.top;
              const r = Math.floor(y / cellSize);
              const c = Math.floor(x / cellSize);
              if (r >= 0 && r < rows && c >= 0 && c < cols) handleClick(r, c);
            }}
          />
        </div>
        <div className="flex-1">
          {streamImage ? (
            <img
              src={streamImage}
              alt="Video Stream"
              style={{ border: "1px solid #d1d5db", width: "800px", height: "600px" }}
              onError={(e) => console.log("Failed to load video stream:", e)}
              onLoad={() => console.log("Video stream loaded successfully")}
            />
          ) : (
            <div
              style={{
                border: "1px solid #d1d5db",
                width: "800px",
                height: "600px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#666",
              }}
            >
              Đang chờ video stream...
            </div>
          )}
        </div>
      </div>
      <div className="flex justify-center space-x-2 mt-4">
        <button
          className={`px-4 py-2 bg-blue-600 text-white rounded ${loading ? "opacity-50 cursor-not-allowed" : ""}`}
          onClick={startNavigation}
          disabled={loading}
        >
          {loading ? "Đang xử lý..." : "Bắt đầu điều hướng"}
        </button>
        <button
          className={`px-4 py-2 bg-red-600 text-white rounded ${loading || !robotRunning ? "opacity-50 cursor-not-allowed" : ""}`}
          onClick={stopNavigation}
          disabled={loading || !robotRunning}
        >
          Dừng robot
        </button>
        <button
          className="px-4 py-2 bg-gray-500 text-white rounded"
          onClick={resetGrid}
        >
          Reset
        </button>
      </div>
      {message && <p className="mt-2 text-center text-sm text-gray-700">{message}</p>}
      {ultrasonicDistance !== null && (
        <p className="mt-2 text-center text-sm text-gray-700">
          Khoảng cách siêu âm: {ultrasonicDistance} cm
        </p>
      )}
    </div>
  );
}
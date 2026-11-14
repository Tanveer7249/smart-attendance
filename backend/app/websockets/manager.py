from typing import Dict, List, Any
from fastapi import WebSocket
import json

class ConnectionManager:
    def __init__(self):
        # session_id -> list of active WebSockets
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, session_id: int, websocket: WebSocket):
        await websocket.accept()
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
        self.active_connections[session_id].append(websocket)

    def disconnect(self, session_id: int, websocket: WebSocket):
        if session_id in self.active_connections:
            if websocket in self.active_connections[session_id]:
                self.active_connections[session_id].remove(websocket)
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]

    async def broadcast_to_session(self, session_id: int, message: Dict[str, Any]):
        if session_id in self.active_connections:
            serialized = json.dumps(message, default=str)
            dead_connections = []
            for connection in self.active_connections[session_id]:
                try:
                    await connection.send_text(serialized)
                except Exception:
                    dead_connections.append(connection)
            for dead in dead_connections:
                if dead in self.active_connections[session_id]:
                    self.active_connections[session_id].remove(dead)

ws_manager = ConnectionManager()


from fastapi import WebSocket
from typing import Any
import json


class ConnectionManager:
    def __init__(self):
        self.faculty_connections: dict[int, WebSocket] = {}
        self.agent_connections: dict[str, WebSocket] = {}

    async def connect_faculty(self, faculty_id: int, ws: WebSocket):
        await ws.accept()
        self.faculty_connections[faculty_id] = ws

    def disconnect_faculty(self, faculty_id: int):
        self.faculty_connections.pop(faculty_id, None)

    async def connect_agent(self, device_id: str, ws: WebSocket):
        await ws.accept()
        self.agent_connections[device_id] = ws

    def disconnect_agent(self, device_id: str):
        self.agent_connections.pop(device_id, None)

    async def send_to_faculty(self, faculty_id: int, event: str, data: Any):
        ws = self.faculty_connections.get(faculty_id)
        if ws:
            try:
                await ws.send_json({"event": event, "data": data})
            except Exception:
                self.disconnect_faculty(faculty_id)

    async def send_to_agent(self, device_id: str, event: str, data: Any):
        ws = self.agent_connections.get(device_id)
        if ws:
            try:
                await ws.send_json({"event": event, "data": data})
            except Exception:
                self.disconnect_agent(device_id)

    async def broadcast_faculty(self, event: str, data: Any):
        for fid in list(self.faculty_connections.keys()):
            await self.send_to_faculty(fid, event, data)

    async def broadcast_agents(self, event: str, data: Any):
        for did in list(self.agent_connections.keys()):
            await self.send_to_agent(did, event, data)

    def is_agent_connected(self, device_id: str) -> bool:
        return device_id in self.agent_connections


manager = ConnectionManager()

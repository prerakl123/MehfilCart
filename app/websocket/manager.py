"""
WebSocket connection manager -- manages rooms and broadcasting.
Uses FastAPI's native WebSocket support.
"""

import json

from fastapi import WebSocket


class ConnectionManager:
    """
    Manages active WebSocket connections, room memberships, and event broadcasting.

    Rooms:
      - session:{session_id}  -- all session members see cart/session events
      - staff:{restaurant_id} -- waitstaff see incoming orders
      - admin:{restaurant_id} -- admins see all operational events
    """

    def __init__(self):
        # user_id -> WebSocket
        self._connections: dict[str, WebSocket] = {}
        # room_name -> set of user_ids
        self._rooms: dict[str, set[str]] = {}

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        """Accept a WebSocket connection and register the user."""
        await websocket.accept()
        self._connections[user_id] = websocket

    async def disconnect(self, user_id: str) -> None:
        """Remove a user from all rooms and close the connection."""
        self._connections.pop(user_id, None)
        for room in list(self._rooms.keys()):
            self._rooms[room].discard(user_id)
            if not self._rooms[room]:
                del self._rooms[room]

    def join_room(self, user_id: str, room: str) -> None:
        """Add a user to a room."""
        if room not in self._rooms:
            self._rooms[room] = set()
        self._rooms[room].add(user_id)

    def leave_room(self, user_id: str, room: str) -> None:
        """Remove a user from a room."""
        if room in self._rooms:
            self._rooms[room].discard(user_id)
            if not self._rooms[room]:
                del self._rooms[room]

    async def broadcast_to_room(self, room: str, event: str, payload: dict) -> None:
        """Send an event to all users in a room."""
        message = json.dumps({"event": event, "data": payload})
        user_ids = self._rooms.get(room, set())
        for uid in list(user_ids):
            ws = self._connections.get(uid)
            if ws:
                try:
                    await ws.send_text(message)
                except Exception:
                    # Client disconnected; clean up
                    await self.disconnect(uid)

    async def send_to_user(self, user_id: str, event: str, payload: dict) -> None:
        """Send an event directly to a specific user."""
        ws = self._connections.get(user_id)
        if ws:
            message = json.dumps({"event": event, "data": payload})
            try:
                await ws.send_text(message)
            except Exception:
                await self.disconnect(user_id)


# Singleton instance
ws_manager = ConnectionManager()

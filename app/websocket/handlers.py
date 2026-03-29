"""
WebSocket handlers -- parse incoming messages and dispatch events.
"""

import json

from fastapi import WebSocket, WebSocketDisconnect

from app.core.exceptions import UnauthorizedException
from app.core.security import verify_access_token
from app.websocket.manager import ws_manager


async def websocket_endpoint(websocket: WebSocket):
    """
    Main WebSocket endpoint handler.
    Authenticates via token query param, then listens for client events.
    """
    # Authenticate: expect token in query string ?token=...
    token = websocket.query_params.get("token")
    if not token:
        await websocket.accept()
        await websocket.close(code=4001, reason="Authentication required")
        return

    try:
        payload = verify_access_token(token)
        user_id = payload["sub"]
    except (UnauthorizedException, Exception) as e:
        print(f"WS Auth Error: {e}")
        await websocket.accept()
        await websocket.close(code=4001, reason="Invalid token")
        return

    await ws_manager.connect(websocket, user_id)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
                event = message.get("event", "")
                data = message.get("data", {})
                await _handle_client_event(user_id, event, data)
            except json.JSONDecodeError:
                await ws_manager.send_to_user(
                    user_id, "error", {"message": "Invalid JSON"}
                )
    except WebSocketDisconnect:
        await ws_manager.disconnect(user_id)


async def _handle_client_event(user_id: str, event: str, data: dict):
    """Route incoming client events to the appropriate handler."""
    if event == "join:session":
        session_id = data.get("session_id", "")
        ws_manager.join_room(user_id, f"session:{session_id}")

    elif event == "leave:session":
        session_id = data.get("session_id", "")
        ws_manager.leave_room(user_id, f"session:{session_id}")

    elif event == "join:staff":
        restaurant_id = data.get("restaurant_id", "")
        ws_manager.join_room(user_id, f"staff:{restaurant_id}")

    elif event == "join:admin":
        restaurant_id = data.get("restaurant_id", "")
        ws_manager.join_room(user_id, f"admin:{restaurant_id}")

    # TODO: Handle cart:add-item, cart:remove-item, etc. via WebSocket
    # For now, cart operations go through REST endpoints and broadcast via manager

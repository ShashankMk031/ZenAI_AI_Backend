from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.websocket.connection_manager import ConnectionManager
import asyncio
import json

router = APIRouter()
manager = ConnectionManager()


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """
    Streams AI responses to the frontend in real time.
    """
    await manager.connect(websocket)
    await manager.send_personal("Connected to ZenAI WebSocket server.", websocket)

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            user_msg = payload.get("message", "")

            await manager.send_personal(f"You said: {user_msg}", websocket)
            await asyncio.sleep(0.5)

            # Simulated streaming output
            response_text = "ZenAI is generating your project summary..."
            for token in response_text.split():
                await asyncio.sleep(0.15)
                await manager.send_personal(token, websocket)

            await manager.send_personal("[END_STREAM]", websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)

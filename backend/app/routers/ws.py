from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.services.auth import decode_token
from app.services.progress_hub import progress_hub

router = APIRouter(tags=["websocket"])


@router.websocket("/api/v1/ws/datasets/{dataset_id}")
async def dataset_progress_ws(
    websocket: WebSocket,
    dataset_id: str,
    token: str = Query(..., description="JWT access_token"),
):
    payload = decode_token(token)
    if not payload:
        await websocket.close(code=4401)
        return
    room = f"dataset:{dataset_id}"
    await progress_hub.connect(room, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await progress_hub.disconnect(room, websocket)

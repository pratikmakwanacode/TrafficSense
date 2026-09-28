import asyncio
import json
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.db_models import Notification
from app.services.notification_service import NotificationService

router = APIRouter()

@router.get("/active")
def get_active_notifications(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    Returns the most recent active traffic notifications.
    """
    notifications = db.query(Notification)\
        .order_by(Notification.timestamp.desc())\
        .limit(limit)\
        .all()
        
    return [
        {
            "id": n.id,
            "video_id": n.video_id,
            "type": n.type,
            "message": n.message,
            "junction": n.junction,
            "timestamp": n.timestamp.isoformat()
        }
        for n in notifications
    ]

@router.get("/stream")
async def stream_notifications(request: Request):
    """
    SSE stream of live notifications.
    """
    queue = await NotificationService.subscribe()

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    notification = await asyncio.wait_for(queue.get(), timeout=5.0)
                    yield f"data: {json.dumps(notification)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            NotificationService.unsubscribe(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

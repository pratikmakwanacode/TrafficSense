import asyncio
import json
from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.models.db_models import Notification

class NotificationService:
    # List of active client subscription queues
    _listeners: List[asyncio.Queue] = []

    @classmethod
    async def subscribe(cls) -> asyncio.Queue:
        queue = asyncio.Queue()
        cls._listeners.append(queue)
        return queue

    @classmethod
    def unsubscribe(cls, queue: asyncio.Queue):
        if queue in cls._listeners:
            cls._listeners.remove(queue)

    @classmethod
    def broadcast(cls, notification_data: Dict[str, Any]):
        for queue in cls._listeners:
            queue.put_nowait(notification_data)

    @classmethod
    def create_and_broadcast_notification(
        cls, db: Session, video_id: int, notif_type: str, message: str, junction: str
    ) -> Notification:
        """
        Persists an active notification to the database and broadcasts it to all SSE subscribers.
        """
        db_notif = Notification(
            video_id=video_id,
            type=notif_type,
            message=message,
            junction=junction,
            timestamp=datetime.utcnow()
        )
        db.add(db_notif)
        db.commit()
        db.refresh(db_notif)

        payload = {
            "id": db_notif.id,
            "video_id": db_notif.video_id,
            "type": db_notif.type,
            "message": db_notif.message,
            "junction": db_notif.junction,
            "timestamp": db_notif.timestamp.isoformat()
        }
        cls.broadcast(payload)
        return db_notif

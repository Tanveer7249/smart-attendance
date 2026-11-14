from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from app.models.models import Notification, NotificationType

class NotificationService:

    @staticmethod
    def create_notification(
        db: Session,
        user_id: int,
        title: str,
        message: str,
        notif_type: NotificationType = NotificationType.ALERT,
        link_url: Optional[str] = None
    ) -> Notification:
        notif = Notification(
            user_id=user_id,
            title=title,
            message=message,
            type=notif_type,
            link_url=link_url,
            is_read=False,
            created_at=datetime.now(timezone.utc)
        )
        db.add(notif)
        db.commit()
        db.refresh(notif)
        return notif


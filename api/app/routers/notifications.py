from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.services.database import get_db
from app.utils.auth import get_current_user
from app.services.notification_service import NotificationService
from app.schemas import TokenData

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationResponse(BaseModel):
    id: str
    notification_type: str
    title: str
    message: str
    action_url: Optional[str]
    priority: str
    is_read: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class NotificationCountResponse(BaseModel):
    unread_count: int


@router.get("", response_model=List[NotificationResponse])
def get_my_notifications(
    unread_only: bool = False,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    notifications = NotificationService.get_user_notifications(
        db=db,
        user_id=current_user.user_id,
        unread_only=unread_only,
        limit=limit
    )
    return notifications


@router.get("/count", response_model=NotificationCountResponse)
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    count = NotificationService.get_unread_count(db, current_user.user_id)
    return {"unread_count": count}


@router.post("/{notification_id}/read")
def mark_notification_read(
    notification_id: str,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    success = NotificationService.mark_as_read(db, notification_id, current_user.user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"message": "Notification marked as read"}


@router.post("/read-all")
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    count = NotificationService.mark_all_as_read(db, current_user.user_id)
    return {"message": f"Marked {count} notifications as read"}

from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import (
    LeaveRequest, Student, User, UserRole, LeaveStatus, Notification, NotificationType, AuditLog
)
from app.schemas.schemas import (
    LeaveRequestCreate, LeaveRequestReview, LeaveRequestResponse
)
from app.api.deps import get_current_user, require_role

router = APIRouter(prefix="/leaves", tags=["Leave Management"])

def format_leave(req: LeaveRequest) -> LeaveRequestResponse:
    return LeaveRequestResponse(
        id=req.id,
        student_id=req.student_id,
        student_name=req.student.user.full_name if req.student and req.student.user else None,
        student_roll=req.student.roll_number if req.student else None,
        batch_name=req.student.batch.name if req.student and req.student.batch else None,
        start_date=req.start_date,
        end_date=req.end_date,
        reason=req.reason,
        status=req.status,
        reviewed_by_name=req.reviewer.full_name if req.reviewer else None,
        review_notes=req.review_notes,
        created_at=req.created_at
    )

@router.get("", response_model=List[LeaveRequestResponse])
def get_leaves(
    student_id: Optional[int] = None,
    status_filter: Optional[LeaveStatus] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(LeaveRequest)
    if current_user.role == UserRole.STUDENT:
        query = query.filter(LeaveRequest.student_id == current_user.student_profile.id)
    elif student_id:
        query = query.filter(LeaveRequest.student_id == student_id)

    if status_filter:
        query = query.filter(LeaveRequest.status == status_filter)

    leaves = query.order_by(LeaveRequest.created_at.desc()).all()
    return [format_leave(l) for l in leaves]

@router.post("", response_model=LeaveRequestResponse)
def submit_leave(
    data: LeaveRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.STUDENT]))
):
    if not current_user.student_profile:
        raise HTTPException(status_code=400, detail="Student profile not found")

    leave = LeaveRequest(
        student_id=current_user.student_profile.id,
        start_date=data.start_date,
        end_date=data.end_date,
        reason=data.reason,
        status=LeaveStatus.PENDING
    )
    db.add(leave)
    db.commit()
    db.refresh(leave)
    return format_leave(leave)

@router.put("/{leave_id}/review", response_model=LeaveRequestResponse)
def review_leave(
    leave_id: int,
    review: LeaveRequestReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.TEACHER]))
):
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")

    leave.status = review.status
    leave.reviewed_by_user_id = current_user.id
    leave.review_notes = review.review_notes
    leave.updated_at = datetime.now(timezone.utc)

    student_user_id = leave.student.user_id if leave.student else None
    if student_user_id:
        notif = Notification(
            user_id=student_user_id,
            title=f"Leave Request {review.status.value}",
            message=f"Your leave request for {leave.start_date} to {leave.end_date} has been {review.status.value.lower()}.",
            type=NotificationType.LEAVE
        )
        db.add(notif)

    audit = AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        action="LEAVE_REVIEWED",
        entity_type="LeaveRequest",
        entity_id=leave.id,
        details=f"Leave request marked {review.status.value}. Notes: {review.review_notes}"
    )
    db.add(audit)

    db.commit()
    db.refresh(leave)
    return format_leave(leave)

from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import (
    AttendanceDispute, AttendanceRecord, Student, User, UserRole,
    DisputeStatus, AttendanceStatus, Notification, NotificationType, AuditLog
)
from app.schemas.schemas import (
    AttendanceDisputeCreate, AttendanceDisputeResolve, AttendanceDisputeResponse
)
from app.api.deps import get_current_user, require_role

router = APIRouter(prefix="/disputes", tags=["Attendance Disputes"])

def format_dispute(d: AttendanceDispute) -> AttendanceDisputeResponse:
    rec = d.attendance_record
    return AttendanceDisputeResponse(
        id=d.id,
        attendance_record_id=d.attendance_record_id,
        session_title=rec.class_session.title if rec and rec.class_session else None,
        session_date=rec.class_session.session_date if rec and rec.class_session else None,
        subject_name=rec.class_session.subject.name if rec and rec.class_session and rec.class_session.subject else None,
        current_attendance_status=rec.status.value if rec else None,
        student_id=d.student_id,
        student_name=d.student.user.full_name if d.student and d.student.user else None,
        student_roll=d.student.roll_number if d.student else None,
        reason=d.reason,
        requested_status=d.requested_status,
        status=d.status,
        resolution_notes=d.resolution_notes,
        resolved_by_name=d.resolver.full_name if d.resolver else None,
        created_at=d.created_at
    )

@router.get("", response_model=List[AttendanceDisputeResponse])
def get_disputes(
    status_filter: Optional[DisputeStatus] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(AttendanceDispute)
    if current_user.role == UserRole.STUDENT:
        query = query.filter(AttendanceDispute.student_id == current_user.student_profile.id)

    if status_filter:
        query = query.filter(AttendanceDispute.status == status_filter)

    disputes = query.order_by(AttendanceDispute.created_at.desc()).all()
    return [format_dispute(d) for d in disputes]

@router.post("", response_model=AttendanceDisputeResponse)
def create_dispute(
    data: AttendanceDisputeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.STUDENT]))
):
    if not current_user.student_profile:
        raise HTTPException(status_code=400, detail="Student profile not found")

    record = db.query(AttendanceRecord).filter(
        AttendanceRecord.id == data.attendance_record_id,
        AttendanceRecord.student_id == current_user.student_profile.id
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Attendance record not found for your account")

    existing = db.query(AttendanceDispute).filter(
        AttendanceDispute.attendance_record_id == data.attendance_record_id,
        AttendanceDispute.status == DisputeStatus.PENDING
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="A dispute is already pending for this attendance record")

    dispute = AttendanceDispute(
        attendance_record_id=data.attendance_record_id,
        student_id=current_user.student_profile.id,
        reason=data.reason,
        requested_status=data.requested_status or "PRESENT",
        status=DisputeStatus.PENDING
    )
    db.add(dispute)
    db.commit()
    db.refresh(dispute)
    return format_dispute(dispute)

@router.put("/{dispute_id}/resolve", response_model=AttendanceDisputeResponse)
def resolve_dispute(
    dispute_id: int,
    data: AttendanceDisputeResolve,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.TEACHER]))
):
    dispute = db.query(AttendanceDispute).filter(AttendanceDispute.id == dispute_id).first()
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")

    dispute.status = data.status
    dispute.resolution_notes = data.resolution_notes
    dispute.resolved_by_user_id = current_user.id
    dispute.updated_at = datetime.now(timezone.utc)

    if data.status == DisputeStatus.RESOLVED and data.apply_status_change and dispute.attendance_record:
        old_status = dispute.attendance_record.status.value
        new_status = data.new_attendance_status or AttendanceStatus.PRESENT
        dispute.attendance_record.status = new_status
        dispute.attendance_record.teacher_confirmation = True
        dispute.attendance_record.student_confirmation = True
        dispute.attendance_record.is_manual_correction = True
        dispute.attendance_record.manual_correction_reason = f"Dispute #{dispute.id} Resolved: {data.resolution_notes}"
        dispute.attendance_record.manual_corrected_by_user_id = current_user.id

        audit = AuditLog(
            user_id=current_user.id,
            user_email=current_user.email,
            action="DISPUTE_RESOLVED_ATTENDANCE_UPDATED",
            entity_type="AttendanceRecord",
            entity_id=dispute.attendance_record.id,
            details=f"Dispute #{dispute.id} resolved. Status changed from {old_status} to {new_status.value}.",
            old_values=f'{{"status": "{old_status}"}}',
            new_values=f'{{"status": "{new_status.value}"}}'
        )
        db.add(audit)

    student_user_id = dispute.student.user_id if dispute.student else None
    if student_user_id:
        notif = Notification(
            user_id=student_user_id,
            title=f"Attendance Dispute {data.status.value}",
            message=f"Your attendance dispute has been {data.status.value.lower()}. {data.resolution_notes}",
            type=NotificationType.DISPUTE
        )
        db.add(notif)

    db.commit()
    db.refresh(dispute)
    return format_dispute(dispute)

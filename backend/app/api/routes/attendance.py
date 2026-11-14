from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import (
    AttendanceRecord, ClassSession, Student, Teacher, User, UserRole,
    AttendanceStatus
)
from app.schemas.schemas import (
    StudentMarkAttendanceRequest, TeacherConfirmRequest,
    TeacherRejectRequest, ManualAttendanceCorrectionRequest,
    AttendanceRecordResponse
)
from app.services.attendance_service import AttendanceEngine
from app.api.deps import get_current_user, require_role

router = APIRouter(prefix="/attendance", tags=["Attendance Verification Engine"])

def format_record(r: AttendanceRecord) -> AttendanceRecordResponse:
    return AttendanceRecordResponse(
        id=r.id,
        class_session_id=r.class_session_id,
        session_title=r.class_session.title if r.class_session else None,
        subject_name=r.class_session.subject.name if r.class_session and r.class_session.subject else None,
        session_date=r.class_session.session_date if r.class_session else None,
        student_id=r.student_id,
        student_name=r.student.user.full_name if r.student and r.student.user else None,
        student_roll=r.student.roll_number if r.student else None,
        student_confirmation=r.student_confirmation,
        student_confirmed_at=r.student_confirmed_at,
        student_lat=r.student_lat,
        student_lng=r.student_lng,
        student_device=r.student_device,
        teacher_confirmation=r.teacher_confirmation,
        teacher_confirmed_at=r.teacher_confirmed_at,
        confirmed_by_teacher_name=r.confirmed_by_teacher.user.full_name if r.confirmed_by_teacher and r.confirmed_by_teacher.user else None,
        status=r.status,
        rejection_reason=r.rejection_reason,
        is_manual_correction=r.is_manual_correction,
        manual_correction_reason=r.manual_correction_reason,
        created_at=r.created_at,
        updated_at=r.updated_at
    )

@router.post("/mark-present", response_model=AttendanceRecordResponse)
async def mark_attendance(
    data: StudentMarkAttendanceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.STUDENT]))
):
    if not current_user.student_profile:
        raise HTTPException(status_code=400, detail="Student profile not found for user")

    record = await AttendanceEngine.student_mark_present(
        db=db,
        session_id=data.session_id,
        student_id=current_user.student_profile.id,
        token=data.token,
        pin=data.pin,
        lat=data.latitude,
        lng=data.longitude,
        device_info=data.device_info
    )
    return format_record(record)

@router.post("/confirm", response_model=List[AttendanceRecordResponse])
async def confirm_students(
    data: TeacherConfirmRequest,
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.TEACHER, UserRole.ADMIN]))
):
    teacher_id = None
    if current_user.role == UserRole.TEACHER:
        if not current_user.teacher_profile:
            raise HTTPException(status_code=400, detail="Teacher profile not found")
        teacher_id = current_user.teacher_profile.id
    else:
        session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
        teacher_id = session.teacher_id if session else 1

    records = await AttendanceEngine.teacher_confirm_students(
        db=db,
        session_id=session_id,
        teacher_id=teacher_id,
        record_ids=data.record_ids,
        as_status=data.status
    )
    return [format_record(r) for r in records]

@router.post("/reject", response_model=AttendanceRecordResponse)
async def reject_student(
    data: TeacherRejectRequest,
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.TEACHER, UserRole.ADMIN]))
):
    teacher_id = current_user.teacher_profile.id if current_user.teacher_profile else 1
    record = await AttendanceEngine.teacher_reject_student(
        db=db,
        session_id=session_id,
        teacher_id=teacher_id,
        record_id=data.record_id,
        reason=data.reason
    )
    return format_record(record)

@router.post("/manual-correction", response_model=AttendanceRecordResponse)
async def manual_correction(
    data: ManualAttendanceCorrectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.TEACHER, UserRole.ADMIN]))
):
    record = await AttendanceEngine.manual_correction(
        db=db,
        user=current_user,
        record_id=data.record_id,
        new_status=data.status,
        reason=data.reason
    )
    return format_record(record)

@router.get("/my-history", response_model=List[AttendanceRecordResponse])
def get_my_attendance_history(
    subject_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.STUDENT]))
):
    student_id = current_user.student_profile.id
    query = db.query(AttendanceRecord).join(ClassSession).filter(
        AttendanceRecord.student_id == student_id
    )
    if subject_id:
        query = query.filter(ClassSession.subject_id == subject_id)

    records = query.order_by(ClassSession.session_date.desc(), AttendanceRecord.id.desc()).all()
    return [format_record(r) for r in records]

@router.get("/records", response_model=List[AttendanceRecordResponse])
def get_all_records(
    session_id: Optional[int] = None,
    student_id: Optional[int] = None,
    status_filter: Optional[AttendanceStatus] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.TEACHER]))
):
    query = db.query(AttendanceRecord).join(ClassSession)
    if session_id:
        query = query.filter(AttendanceRecord.class_session_id == session_id)
    if student_id:
        query = query.filter(AttendanceRecord.student_id == student_id)
    if status_filter:
        query = query.filter(AttendanceRecord.status == status_filter)

    records = query.order_by(ClassSession.session_date.desc(), AttendanceRecord.id.desc()).limit(200).all()
    return [format_record(r) for r in records]

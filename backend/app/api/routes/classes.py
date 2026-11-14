import random
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import (
    ClassSession, Subject, Batch, Teacher, Student, AttendanceRecord,
    TeacherStudentAssignment, SessionStatus, AttendanceStatus, User, UserRole
)
from app.schemas.schemas import (
    ClassSessionCreate, ClassSessionResponse, AttendanceRecordResponse
)
from app.services.attendance_service import AttendanceEngine
from app.api.deps import get_current_user, require_role

router = APIRouter(prefix="/classes", tags=["Class Sessions"])

def format_session_response(session: ClassSession, db: Session, hide_pin_for_student: bool = False) -> ClassSessionResponse:
    # Count students rostered in this session
    enrolled_count = db.query(AttendanceRecord).filter(
        AttendanceRecord.class_session_id == session.id
    ).count()

    if enrolled_count == 0:
        # Fallback to teacher assigned students
        enrolled_count = db.query(TeacherStudentAssignment).filter(
            TeacherStudentAssignment.teacher_id == session.teacher_id
        ).count()

    marked_student = db.query(AttendanceRecord).filter(
        AttendanceRecord.class_session_id == session.id,
        AttendanceRecord.student_confirmation == True
    ).count()

    confirmed_present = db.query(AttendanceRecord).filter(
        AttendanceRecord.class_session_id == session.id,
        AttendanceRecord.status == AttendanceStatus.PRESENT
    ).count()

    total_late = db.query(AttendanceRecord).filter(
        AttendanceRecord.class_session_id == session.id,
        AttendanceRecord.status == AttendanceStatus.LATE
    ).count()

    total_absent = db.query(AttendanceRecord).filter(
        AttendanceRecord.class_session_id == session.id,
        AttendanceRecord.status == AttendanceStatus.ABSENT
    ).count()

    return ClassSessionResponse(
        id=session.id,
        teacher_id=session.teacher_id,
        teacher_name=session.teacher.user.full_name if session.teacher and session.teacher.user else None,
        subject_id=session.subject_id,
        subject_name=session.subject.name if session.subject else None,
        subject_code=session.subject.code if session.subject else None,
        batch_id=session.batch_id,
        batch_name=session.batch.name if session.batch else None,
        title=session.title,
        session_date=session.session_date,
        start_time=session.start_time,
        end_time=session.end_time,
        duration_minutes=session.duration_minutes,
        room_number=session.room_number,
        status=session.status,
        attendance_pin=None if hide_pin_for_student else session.attendance_pin,
        current_qr_token=session.current_qr_token,
        qr_token_expires_at=session.qr_token_expires_at,
        late_threshold_minutes=session.late_threshold_minutes,
        require_gps=session.require_gps,
        target_latitude=session.target_latitude,
        target_longitude=session.target_longitude,
        gps_radius_meters=session.gps_radius_meters,
        total_enrolled=enrolled_count,
        total_marked_student=marked_student,
        total_confirmed_present=confirmed_present,
        total_late=total_late,
        total_absent=total_absent,
        created_at=session.created_at
    )

@router.get("", response_model=List[ClassSessionResponse])
def get_classes(
    subject_id: Optional[int] = None,
    teacher_id: Optional[int] = None,
    session_status: Optional[SessionStatus] = None,
    session_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(ClassSession)

    is_student = (current_user.role == UserRole.STUDENT and current_user.student_profile is not None)

    if is_student:
        student_id = current_user.student_profile.id
        # Student ONLY sees classes specifically assigned to them!
        query = query.join(
            AttendanceRecord, AttendanceRecord.class_session_id == ClassSession.id
        ).filter(
            AttendanceRecord.student_id == student_id
        )
    elif current_user.role == UserRole.TEACHER and current_user.teacher_profile is not None:
        query = query.filter(ClassSession.teacher_id == current_user.teacher_profile.id)
    elif teacher_id:
        query = query.filter(ClassSession.teacher_id == teacher_id)

    if subject_id:
        query = query.filter(ClassSession.subject_id == subject_id)
    if session_status:
        query = query.filter(ClassSession.status == session_status)
    if session_date:
        query = query.filter(ClassSession.session_date == session_date)

    sessions = query.order_by(ClassSession.session_date.desc(), ClassSession.start_time.desc()).all()
    return [format_session_response(s, db, hide_pin_for_student=is_student) for s in sessions]

@router.post("", response_model=ClassSessionResponse)
def create_class(
    data: ClassSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.TEACHER]))
):
    teacher_id = None
    if current_user.role == UserRole.TEACHER:
        if not current_user.teacher_profile:
            raise HTTPException(status_code=400, detail="Teacher profile not found")
        teacher_id = current_user.teacher_profile.id
    else:
        first_t = db.query(Teacher).first()
        teacher_id = first_t.id if first_t else 1

    pin = f"{random.randint(100000, 999999)}"

    session = ClassSession(
        teacher_id=teacher_id,
        subject_id=data.subject_id,
        batch_id=data.batch_id,
        title=data.title,
        session_date=data.session_date,
        start_time=data.start_time,
        duration_minutes=data.duration_minutes,
        room_number=data.room_number,
        late_threshold_minutes=data.late_threshold_minutes,
        require_gps=data.require_gps,
        target_latitude=data.target_latitude,
        target_longitude=data.target_longitude,
        gps_radius_meters=data.gps_radius_meters,
        attendance_pin=pin,
        status=SessionStatus.SCHEDULED
    )
    db.add(session)
    db.flush()

    # Determine which student(s) this class is scheduled for
    target_student_ids = []
    if data.student_ids and len(data.student_ids) > 0:
        target_student_ids = data.student_ids
    else:
        # Fallback to all students assigned to this teacher
        assigned = db.query(TeacherStudentAssignment).filter(
            TeacherStudentAssignment.teacher_id == teacher_id
        ).all()
        target_student_ids = [a.student_id for a in assigned]

    # Pre-populate AttendanceRecord for these specific students
    for s_id in set(target_student_ids):
        student_obj = db.query(Student).filter(Student.id == s_id).first()
        if student_obj:
            record = AttendanceRecord(
                class_session_id=session.id,
                student_id=s_id,
                status=AttendanceStatus.NOT_MARKED
            )
            db.add(record)

    db.commit()
    db.refresh(session)
    return format_session_response(session, db)

@router.post("/{session_id}/start", response_model=ClassSessionResponse)
def start_class_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.TEACHER]))
):
    session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Class session not found")

    if current_user.role == UserRole.TEACHER:
        if not current_user.teacher_profile or session.teacher_id != current_user.teacher_profile.id:
            raise HTTPException(status_code=403, detail="You can only start your own assigned class")

    session.status = SessionStatus.ACTIVE
    session.started_at = datetime.now(timezone.utc)
    db.commit()

    AttendanceEngine.generate_qr_token(db, session.id)
    db.refresh(session)
    return format_session_response(session, db)

@router.post("/{session_id}/qr-token")
def refresh_qr_token(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.TEACHER]))
):
    token = AttendanceEngine.generate_qr_token(db, session_id, expiry_seconds=30)
    session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    return {
        "token": token,
        "expires_at": session.qr_token_expires_at.isoformat() if session.qr_token_expires_at else None,
        "pin": session.attendance_pin
    }

@router.post("/{session_id}/close", response_model=ClassSessionResponse)
async def close_and_finalize_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.TEACHER]))
):
    session = await AttendanceEngine.finalize_and_close_session(db, session_id, current_user)
    return format_session_response(session, db)

@router.get("/{session_id}/attendees", response_model=List[AttendanceRecordResponse])
def get_session_attendees(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Class session not found")

    # Get attendance records specifically rostered for this class session
    session_records = db.query(AttendanceRecord).filter(
        AttendanceRecord.class_session_id == session_id
    ).all()

    results = []
    for rec in session_records:
        st = rec.student
        results.append(AttendanceRecordResponse(
            id=rec.id,
            class_session_id=session.id,
            session_title=session.title,
            subject_name=session.subject.name if session.subject else None,
            session_date=session.session_date,
            student_id=st.id,
            student_name=st.user.full_name if st and st.user else "Student",
            student_roll=st.roll_number if st else None,
            student_confirmation=rec.student_confirmation,
            student_confirmed_at=rec.student_confirmed_at,
            student_lat=rec.student_lat,
            student_lng=rec.student_lng,
            student_device=rec.student_device,
            teacher_confirmation=rec.teacher_confirmation,
            teacher_confirmed_at=rec.teacher_confirmed_at,
            confirmed_by_teacher_name=rec.confirmed_by_teacher.user.full_name if rec.confirmed_by_teacher and rec.confirmed_by_teacher.user else None,
            status=rec.status,
            rejection_reason=rec.rejection_reason,
            is_manual_correction=rec.is_manual_correction,
            manual_correction_reason=rec.manual_correction_reason,
            created_at=rec.created_at,
            updated_at=rec.updated_at
        ))

    return results

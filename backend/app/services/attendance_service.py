import math
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.models import (
    ClassSession, AttendanceRecord, AttendanceToken, Student, Teacher,
    User, Batch, Subject, TeacherStudentAssignment, SessionStatus,
    AttendanceStatus, LeaveRequest, LeaveStatus, AuditLog, Notification,
    NotificationType, UserRole
)
from app.websockets.manager import ws_manager

def calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

class AttendanceEngine:

    @staticmethod
    def generate_qr_token(db: Session, session_id: int, expiry_seconds: int = 30) -> str:
        session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Class session not found")
        if session.status != SessionStatus.ACTIVE:
            raise HTTPException(status_code=400, detail="Class session is not active")

        token_str = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expiry_seconds)

        session.current_qr_token = token_str
        session.qr_token_expires_at = expires_at

        db_token = AttendanceToken(
            class_session_id=session_id,
            token=token_str,
            expires_at=expires_at
        )
        db.add(db_token)
        db.commit()
        db.refresh(session)
        return token_str

    @staticmethod
    def validate_qr_or_pin(db: Session, session: ClassSession, token: Optional[str], pin: Optional[str]):
        now = datetime.now(timezone.utc)
        
        if pin and pin.strip() == session.attendance_pin:
            return True

        if token:
            if session.current_qr_token == token:
                if session.qr_token_expires_at and session.qr_token_expires_at.replace(tzinfo=timezone.utc) >= now:
                    return True
                else:
                    raise HTTPException(status_code=400, detail="QR code has expired. Please scan the refreshed code.")
            
            recent_token = db.query(AttendanceToken).filter(
                AttendanceToken.class_session_id == session.id,
                AttendanceToken.token == token
            ).order_by(AttendanceToken.id.desc()).first()

            if recent_token:
                if recent_token.expires_at.replace(tzinfo=timezone.utc) >= now:
                    return True
                else:
                    raise HTTPException(status_code=400, detail="QR code has expired. Please scan the refreshed code.")

        raise HTTPException(
            status_code=400,
            detail="Invalid or expired attendance QR token / PIN"
        )

    @staticmethod
    async def student_mark_present(
        db: Session,
        session_id: int,
        student_id: int,
        token: Optional[str] = None,
        pin: Optional[str] = None,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
        device_info: Optional[str] = None
    ) -> AttendanceRecord:
        """
        Step 1: Student marks attendance using PIN or dynamic QR.
        Verifies student is assigned to this teacher or batch.
        Dual confirmation rule: status is STUDENT_MARKED until Teacher also confirms!
        """
        session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Class session not found")

        if session.status != SessionStatus.ACTIVE:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot mark attendance: Class session is {session.status.value}"
            )

        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Student profile not found")

        # Verify Student is assigned to this Teacher OR rostered in this session
        is_rostered = db.query(AttendanceRecord).filter(
            AttendanceRecord.class_session_id == session.id,
            AttendanceRecord.student_id == student_id
        ).first()

        is_assigned_to_teacher = db.query(TeacherStudentAssignment).filter(
            TeacherStudentAssignment.teacher_id == session.teacher_id,
            TeacherStudentAssignment.student_id == student_id
        ).first()

        if not is_rostered and not is_assigned_to_teacher and (session.batch_id is not None and student.batch_id != session.batch_id):
            raise HTTPException(
                status_code=403,
                detail="Access denied: You are not assigned to this teacher or class session"
            )

        # Validate Token or PIN
        AttendanceEngine.validate_qr_or_pin(db, session, token, pin)

        # GPS Verification
        if session.require_gps:
            if lat is None or lng is None:
                raise HTTPException(
                    status_code=400,
                    detail="This class requires GPS location verification. Please enable GPS permissions."
                )
            if session.target_latitude is not None and session.target_longitude is not None:
                distance = calculate_haversine_distance(
                    lat, lng, session.target_latitude, session.target_longitude
                )
                radius = session.gps_radius_meters or 150.0
                if distance > radius:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Location verification failed: You are {int(distance)}m away (max allowed: {int(radius)}m)"
                    )

        # Check existing attendance record
        record = db.query(AttendanceRecord).filter(
            AttendanceRecord.class_session_id == session_id,
            AttendanceRecord.student_id == student_id
        ).first()

        now = datetime.now(timezone.utc)

        if record:
            if record.student_confirmation:
                raise HTTPException(
                    status_code=400,
                    detail="You have already submitted your attendance for this class session"
                )
        else:
            record = AttendanceRecord(
                class_session_id=session_id,
                student_id=student_id,
                created_at=now
            )
            db.add(record)

        record.student_confirmation = True
        record.student_confirmed_at = now
        record.student_lat = lat
        record.student_lng = lng
        record.student_device = device_info

        # Dual confirmation rule
        if record.teacher_confirmation:
            record.status = AttendanceStatus.PRESENT
        else:
            record.status = AttendanceStatus.STUDENT_MARKED

        db.commit()
        db.refresh(record)

        # Broadcast live update
        await ws_manager.broadcast_to_session(session_id, {
            "type": "STUDENT_SUBMISSION",
            "session_id": session_id,
            "student_id": student.id,
            "student_name": student.user.full_name,
            "roll_number": student.roll_number,
            "status": record.status.value,
            "timestamp": now.isoformat()
        })

        return record

    @staticmethod
    async def teacher_confirm_students(
        db: Session,
        session_id: int,
        teacher_id: int,
        record_ids: List[int],
        as_status: AttendanceStatus = AttendanceStatus.PRESENT
    ) -> List[AttendanceRecord]:
        """
        Step 2: Teacher verifies physical presence in classroom and confirms student(s).
        Dual confirmation rule:
        IF student_confirmation == True AND teacher_confirmation == True -> PRESENT (or LATE)
        """
        session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Class session not found")

        if session.teacher_id != teacher_id:
            raise HTTPException(
                status_code=403,
                detail="Only the assigned teacher can confirm attendance for this class"
            )

        now = datetime.now(timezone.utc)
        updated_records = []

        for r_id in record_ids:
            record = db.query(AttendanceRecord).filter(
                AttendanceRecord.id == r_id,
                AttendanceRecord.class_session_id == session_id
            ).first()

            if not record:
                continue

            record.teacher_confirmation = True
            record.teacher_confirmed_at = now
            record.confirmed_by_teacher_id = teacher_id

            if record.student_confirmation:
                record.status = as_status if as_status in [AttendanceStatus.PRESENT, AttendanceStatus.LATE] else AttendanceStatus.PRESENT
            else:
                record.status = AttendanceStatus.TEACHER_CONFIRMED

            updated_records.append(record)

        db.commit()

        await ws_manager.broadcast_to_session(session_id, {
            "type": "TEACHER_CONFIRMED",
            "session_id": session_id,
            "record_count": len(updated_records),
            "timestamp": now.isoformat()
        })

        return updated_records

    @staticmethod
    async def teacher_reject_student(
        db: Session,
        session_id: int,
        teacher_id: int,
        record_id: int,
        reason: str
    ) -> AttendanceRecord:
        session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Class session not found")

        if session.teacher_id != teacher_id:
            raise HTTPException(status_code=403, detail="Unauthorized teacher")

        record = db.query(AttendanceRecord).filter(
            AttendanceRecord.id == record_id,
            AttendanceRecord.class_session_id == session_id
        ).first()

        if not record:
            raise HTTPException(status_code=404, detail="Attendance record not found")

        record.teacher_confirmation = False
        record.status = AttendanceStatus.REJECTED
        record.rejection_reason = reason
        record.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(record)

        await ws_manager.broadcast_to_session(session_id, {
            "type": "STUDENT_REJECTED",
            "session_id": session_id,
            "record_id": record.id,
            "student_id": record.student_id,
            "reason": reason
        })

        return record

    @staticmethod
    async def manual_correction(
        db: Session,
        user: User,
        record_id: int,
        new_status: AttendanceStatus,
        reason: str
    ) -> AttendanceRecord:
        record = db.query(AttendanceRecord).filter(AttendanceRecord.id == record_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="Attendance record not found")

        session = record.class_session
        if user.role != UserRole.ADMIN:
            if not user.teacher_profile or session.teacher_id != user.teacher_profile.id:
                raise HTTPException(status_code=403, detail="Unauthorized to modify this attendance record")

        old_status = record.status.value
        record.status = new_status
        record.is_manual_correction = True
        record.manual_correction_reason = reason
        record.manual_corrected_by_user_id = user.id
        record.updated_at = datetime.now(timezone.utc)

        if new_status in [AttendanceStatus.PRESENT, AttendanceStatus.LATE]:
            record.teacher_confirmation = True
            record.student_confirmation = True
        elif new_status == AttendanceStatus.ABSENT:
            record.teacher_confirmation = False

        audit = AuditLog(
            user_id=user.id,
            user_email=user.email,
            action="MANUAL_ATTENDANCE_CORRECTION",
            entity_type="AttendanceRecord",
            entity_id=record.id,
            details=f"Status changed from {old_status} to {new_status.value}. Reason: {reason}",
            old_values=f'{{"status": "{old_status}"}}',
            new_values=f'{{"status": "{new_status.value}"}}'
        )
        db.add(audit)
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    async def finalize_and_close_session(
        db: Session,
        session_id: int,
        user: User
    ) -> ClassSession:
        session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Class session not found")

        if user.role != UserRole.ADMIN:
            if not user.teacher_profile or session.teacher_id != user.teacher_profile.id:
                raise HTTPException(status_code=403, detail="Unauthorized to close this class session")

        now = datetime.now(timezone.utc)
        session.status = SessionStatus.COMPLETED
        session.closed_at = now
        session.current_qr_token = None
        session.qr_token_expires_at = None

        # Fetch students assigned to this teacher
        assigned_students = db.query(Student).join(TeacherStudentAssignment).filter(
            TeacherStudentAssignment.teacher_id == session.teacher_id
        ).all()

        if not assigned_students:
            # Fallback to batch students
            assigned_students = db.query(Student).filter(Student.batch_id == session.batch_id).all()

        for student in assigned_students:
            record = db.query(AttendanceRecord).filter(
                AttendanceRecord.class_session_id == session_id,
                AttendanceRecord.student_id == student.id
            ).first()

            has_approved_leave = db.query(LeaveRequest).filter(
                LeaveRequest.student_id == student.id,
                LeaveRequest.status == LeaveStatus.APPROVED,
                LeaveRequest.start_date <= session.session_date,
                LeaveRequest.end_date >= session.session_date
            ).first()

            if not record:
                final_status = AttendanceStatus.ON_LEAVE if has_approved_leave else AttendanceStatus.ABSENT
                record = AttendanceRecord(
                    class_session_id=session_id,
                    student_id=student.id,
                    student_confirmation=False,
                    teacher_confirmation=False,
                    status=final_status,
                    created_at=now
                )
                db.add(record)
            else:
                if record.student_confirmation and record.teacher_confirmation:
                    if record.status not in [AttendanceStatus.PRESENT, AttendanceStatus.LATE]:
                        record.status = AttendanceStatus.PRESENT
                else:
                    record.status = AttendanceStatus.ON_LEAVE if has_approved_leave else AttendanceStatus.ABSENT

        audit = AuditLog(
            user_id=user.id,
            user_email=user.email,
            action="SESSION_CLOSED_AND_FINALIZED",
            entity_type="ClassSession",
            entity_id=session.id,
            details=f"Class session '{session.title}' finalized and closed."
        )
        db.add(audit)
        db.commit()
        db.refresh(session)

        await ws_manager.broadcast_to_session(session_id, {
            "type": "SESSION_CLOSED",
            "session_id": session_id,
            "status": session.status.value,
            "closed_at": now.isoformat()
        })

        return session

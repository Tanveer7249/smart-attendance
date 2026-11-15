from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import (
    User, UserRole, ClassSession, SessionStatus, Teacher, Student,
    AttendanceRecord, AttendanceStatus, LeaveRequest, LeaveStatus,
    Notification, TeacherStudentAssignment, Subject, TeacherCourseAssignment
)
from app.schemas.schemas import (
    AdminDashboardStats, TeacherDashboardStats, StudentDashboardStats,
    ClassSessionResponse, AttendanceRecordResponse, SubjectAttendanceSummary
)
from app.services.analytics_service import AnalyticsService
from app.api.deps import get_current_user, require_role
from app.api.routes.classes import format_session_response
from app.api.routes.attendance import format_record

router = APIRouter(prefix="/analytics", tags=["Analytics & Reports"])

@router.get("/admin", response_model=AdminDashboardStats)
def get_admin_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN]))
):
    stats = AnalyticsService.get_admin_dashboard_stats(db)
    active_sessions = db.query(ClassSession).filter(ClassSession.status == SessionStatus.ACTIVE).all()
    formatted_active = [format_session_response(s, db) for s in active_sessions]

    return AdminDashboardStats(
        total_students=stats["total_students"],
        total_teachers=stats["total_teachers"],
        total_batches=stats["total_batches"],
        total_subjects=stats["total_subjects"],
        classes_conducted_today=stats["classes_conducted_today"],
        present_students_today=stats["present_students_today"],
        absent_students_today=stats["absent_students_today"],
        late_students_today=stats["late_students_today"],
        average_attendance_percentage=stats["average_attendance_percentage"],
        students_below_threshold=stats["students_below_threshold"],
        threshold_percentage=stats["threshold_percentage"],
        at_risk_students=stats["at_risk_students"],
        weekly_trends=stats["weekly_trends"],
        monthly_trends=stats["monthly_trends"],
        active_sessions=formatted_active
    )

@router.get("/teacher", response_model=TeacherDashboardStats)
def get_teacher_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.TEACHER]))
):
    teacher = current_user.teacher_profile
    if not teacher:
        teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
        if not teacher:
            teacher = Teacher(
                user_id=current_user.id,
                employee_id=f"EMP-{current_user.id:04d}",
                department="Academics",
                designation="Faculty"
            )
            db.add(teacher)
            db.commit()
            db.refresh(teacher)

    today_str = date.today().isoformat()
    today_classes = db.query(ClassSession).filter(
        (ClassSession.teacher_id == teacher.id) | (ClassSession.teacher_id == current_user.id),
        ClassSession.session_date == today_str
    ).count()

    active_session = db.query(ClassSession).filter(
        (ClassSession.teacher_id == teacher.id) | (ClassSession.teacher_id == current_user.id),
        ClassSession.status == SessionStatus.ACTIVE
    ).first()

    upcoming_classes = db.query(ClassSession).filter(
        (ClassSession.teacher_id == teacher.id) | (ClassSession.teacher_id == current_user.id),
        ClassSession.status.in_([SessionStatus.SCHEDULED, SessionStatus.ACTIVE])
    ).order_by(ClassSession.session_date, ClassSession.start_time).limit(5).all()

    total_classes = db.query(ClassSession).filter(
        (ClassSession.teacher_id == teacher.id) | (ClassSession.teacher_id == current_user.id),
        ClassSession.status == SessionStatus.COMPLETED
    ).count()

    # Assigned students list (support assignment by Teacher.id or User.id)
    assignments = db.query(TeacherStudentAssignment).filter(
        (TeacherStudentAssignment.teacher_id == teacher.id) |
        (TeacherStudentAssignment.teacher_id == current_user.id)
    ).all()

    assigned_students = []
    seen_students = set()
    for a in assignments:
        st = a.student
        if st and st.user and st.id not in seen_students:
            seen_students.add(st.id)
            assigned_students.append({
                "assignment_id": a.id,
                "student_id": st.id,
                "full_name": st.user.full_name,
                "email": st.user.email,
                "roll_number": st.roll_number or f"STU-{st.id:04d}",
                "batch_name": st.batch.name if st.batch else "General",
                "assigned_at": a.assigned_at.isoformat() if a.assigned_at else None
            })

    # Assigned courses list
    teacher_courses = db.query(Subject).join(TeacherCourseAssignment).filter(
        (TeacherCourseAssignment.teacher_id == teacher.id) | (TeacherCourseAssignment.teacher_id == current_user.id),
        Subject.is_active == True
    ).all()
    from app.schemas.schemas import SubjectResponse
    assigned_courses_resp = [SubjectResponse.model_validate(c) for c in teacher_courses]

    # Average attendance percentage
    teacher_sessions = db.query(ClassSession.id).filter(
        ClassSession.teacher_id == teacher.id,
        ClassSession.status == SessionStatus.COMPLETED
    ).all()
    session_ids = [s[0] for s in teacher_sessions]

    avg_pct = 0.0
    if session_ids:
        pres_count = db.query(AttendanceRecord).filter(
            AttendanceRecord.class_session_id.in_(session_ids),
            AttendanceRecord.status.in_([AttendanceStatus.PRESENT, AttendanceStatus.LATE])
        ).count()
        tot_count = db.query(AttendanceRecord).filter(
            AttendanceRecord.class_session_id.in_(session_ids),
            AttendanceRecord.status.in_([AttendanceStatus.PRESENT, AttendanceStatus.LATE, AttendanceStatus.ABSENT])
        ).count()
        if tot_count > 0:
            avg_pct = round((pres_count / tot_count) * 100.0, 1)

    return TeacherDashboardStats(
        teacher_id=teacher.id,
        teacher_name=current_user.full_name,
        employee_id=teacher.employee_id,
        department=teacher.department,
        assigned_students_count=len(assigned_students),
        assigned_students=assigned_students,
        assigned_courses=assigned_courses_resp,
        today_classes_count=today_classes,
        active_session=format_session_response(active_session, db) if active_session else None,
        total_classes_conducted=total_classes,
        average_attendance_percentage=avg_pct,
        upcoming_classes=[format_session_response(s, db) for s in upcoming_classes]
    )

@router.get("/student", response_model=StudentDashboardStats)
def get_student_dashboard(
    student_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    target_student_id = None
    if current_user.role == UserRole.STUDENT:
        if not current_user.student_profile:
            raise HTTPException(status_code=400, detail="Student profile missing")
        target_student_id = current_user.student_profile.id
    elif current_user.role in [UserRole.ADMIN, UserRole.TEACHER]:
        if not student_id:
            raise HTTPException(status_code=400, detail="student_id required")
        target_student_id = student_id
    else:
        raise HTTPException(status_code=403, detail="Forbidden")

    analytics = AnalyticsService.get_student_analytics(db, target_student_id)
    if not analytics:
        raise HTTPException(status_code=404, detail="Student analytics not found")

    recent_records = db.query(AttendanceRecord).filter(
        AttendanceRecord.student_id == target_student_id
    ).order_by(AttendanceRecord.id.desc()).limit(15).all()

    student = db.query(Student).filter(Student.id == target_student_id).first()
    
    # Active sessions specifically rostered for this student!
    active_sessions = db.query(ClassSession).join(
        AttendanceRecord, AttendanceRecord.class_session_id == ClassSession.id
    ).filter(
        ClassSession.status == SessionStatus.ACTIVE,
        AttendanceRecord.student_id == target_student_id
    ).all()

    pending_leaves = db.query(LeaveRequest).filter(
        LeaveRequest.student_id == target_student_id,
        LeaveRequest.status == LeaveStatus.PENDING
    ).count()

    unread_notifications = db.query(Notification).filter(
        Notification.user_id == student.user_id,
        Notification.is_read == False
    ).count()

    return StudentDashboardStats(
        student_id=analytics["student_id"],
        student_name=analytics["student_name"],
        roll_number=analytics.get("roll_number"),
        batch_name=analytics["batch_name"],
        assigned_teachers=analytics["assigned_teachers"],
        total_classes=analytics["total_classes"],
        present_count=analytics["present_count"],
        late_count=analytics["late_count"],
        absent_count=analytics["absent_count"],
        overall_percentage=analytics["overall_percentage"],
        is_at_risk=analytics["is_at_risk"],
        subject_breakdown=[SubjectAttendanceSummary(**s) for s in analytics["subject_breakdown"]],
        recent_records=[format_record(r) for r in recent_records],
        active_sessions=[format_session_response(s, db, hide_pin_for_student=True) for s in active_sessions],
        pending_leaves=pending_leaves,
        unread_notifications=unread_notifications
    )

@router.get("/export/excel")
def export_excel(
    batch_id: Optional[int] = None,
    subject_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.TEACHER]))
):
    excel_stream = AnalyticsService.export_attendance_excel(db, batch_id=batch_id, subject_id=subject_id)
    filename = f"attendance_report_{date.today().isoformat()}.xlsx"
    return StreamingResponse(
        excel_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/export/pdf")
def export_pdf(
    batch_id: Optional[int] = None,
    subject_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.TEACHER]))
):
    pdf_stream = AnalyticsService.export_attendance_pdf(db, batch_id=batch_id, subject_id=subject_id)
    filename = f"attendance_report_{date.today().isoformat()}.pdf"
    return StreamingResponse(
        pdf_stream,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

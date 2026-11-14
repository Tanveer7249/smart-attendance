import pytest
import os
import sys
from datetime import datetime, date, timedelta, timezone
from fastapi.testclient import TestClient

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.core.database import SessionLocal, Base, engine
from app.models.models import (
    User, UserRole, Teacher, Student, Subject,
    ClassSession, AttendanceRecord, AttendanceStatus, SessionStatus,
    AttendanceToken, AuditLog, TeacherStudentAssignment, TeacherCourseAssignment
)
from app.core.security import get_password_hash, create_access_token

client = TestClient(app)

def get_auth_token(email: str, role: str, user_id: int) -> dict:
    token = create_access_token(data={"sub": email, "role": role, "user_id": user_id})
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()

# Flow 1: Admin logs in
def test_01_admin_login(db):
    res = client.post("/api/auth/login", json={
        "email": "admin@smartattendance.edu",
        "password": "Admin@123"
    })
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["role"] == "ADMIN"
    assert "access_token" in data

# Flow 2: Admin creates new course fresh (no predefined courses)
def test_02_admin_creates_course(db):
    admin = db.query(User).filter(User.role == UserRole.ADMIN).first()
    headers = get_auth_token(admin.email, admin.role.value, admin.id)

    course_payload = {
        "name": "Advanced Software Engineering",
        "code": "ASE-2026",
        "department": "Computer Science",
        "credits": 4,
        "semester": 1
    }
    res = client.post("/api/academics/subjects", json=course_payload, headers=headers)
    assert res.status_code in [200, 400], res.text
    course = db.query(Subject).filter(Subject.code == "ASE-2026").first()
    assert course is not None

# Flow 3: Admin creates Teacher and Student accounts (No roll number required)
def test_03_admin_creates_teacher_and_student(db):
    admin = db.query(User).filter(User.role == UserRole.ADMIN).first()
    headers = get_auth_token(admin.email, admin.role.value, admin.id)

    # Teacher
    teacher_payload = {
        "email": "prof.alan@smartattendance.edu",
        "full_name": "Prof. Alan Turing",
        "password": "Teacher@123",
        "role": "TEACHER",
        "department": "Computer Science",
        "designation": "Professor"
    }
    res_t = client.post("/api/users", json=teacher_payload, headers=headers)
    assert res_t.status_code in [200, 400], res_t.text

    # Student (NO roll number required!)
    student_payload = {
        "email": "grace.student@smartattendance.edu",
        "full_name": "Grace Hopper",
        "password": "Student@123",
        "role": "STUDENT",
        "department": "Computer Science"
    }
    res_s = client.post("/api/users", json=student_payload, headers=headers)
    assert res_s.status_code in [200, 400], res_s.text

    teacher = db.query(Teacher).join(User).filter(User.email == "prof.alan@smartattendance.edu").first()
    student = db.query(Student).join(User).filter(User.email == "grace.student@smartattendance.edu").first()
    assert teacher is not None
    assert student is not None

# Flow 4: Admin assigns Course to Teacher
def test_04_admin_assigns_course_to_teacher(db):
    admin = db.query(User).filter(User.role == UserRole.ADMIN).first()
    headers = get_auth_token(admin.email, admin.role.value, admin.id)

    teacher = db.query(Teacher).join(User).filter(User.email == "prof.alan@smartattendance.edu").first()
    course = db.query(Subject).filter(Subject.code == "ASE-2026").first()

    assign_payload = {
        "teacher_id": teacher.id,
        "subject_ids": [course.id]
    }
    res = client.post("/api/academics/assign-teacher-courses", json=assign_payload, headers=headers)
    assert res.status_code == 200, res.text
    assignments = res.json()
    assert any(a["subject_id"] == course.id for a in assignments)

# Flow 5: Admin assigns Student to Teacher (Many-to-Many test)
def test_05_admin_assigns_student_to_teacher(db):
    admin = db.query(User).filter(User.role == UserRole.ADMIN).first()
    headers = get_auth_token(admin.email, admin.role.value, admin.id)

    teacher = db.query(Teacher).join(User).filter(User.email == "prof.alan@smartattendance.edu").first()
    student = db.query(Student).join(User).filter(User.email == "grace.student@smartattendance.edu").first()
    course = db.query(Subject).filter(Subject.code == "ASE-2026").first()

    assign_payload = {
        "teacher_id": teacher.id,
        "student_ids": [student.id],
        "subject_id": course.id
    }
    res = client.post("/api/users/assign-students", json=assign_payload, headers=headers)
    assert res.status_code == 200, res.text
    assignments = res.json()
    assert any(a["student_id"] == student.id for a in assignments)

# Flow 6: Teacher schedules class selecting the specific course and specific student
def test_06_teacher_schedules_class_for_specific_student(db):
    teacher_user = db.query(User).filter(User.email == "prof.alan@smartattendance.edu").first()
    headers = get_auth_token(teacher_user.email, teacher_user.role.value, teacher_user.id)

    course = db.query(Subject).filter(Subject.code == "ASE-2026").first()
    student = db.query(Student).join(User).filter(User.email == "grace.student@smartattendance.edu").first()

    # Note: NO classroom number!
    class_payload = {
        "subject_id": course.id,
        "title": "Software Architecture Principles",
        "session_date": date.today().isoformat(),
        "start_time": "11:00",
        "duration_minutes": 60,
        "student_ids": [student.id]
    }
    res = client.post("/api/classes", json=class_payload, headers=headers)
    assert res.status_code == 200, res.text
    session_data = res.json()
    session_id = session_data["id"]

    # Start class session
    start_res = client.post(f"/api/classes/{session_id}/start", headers=headers)
    assert start_res.status_code == 200, start_res.text
    assert start_res.json()["status"] == "ACTIVE"

# Flow 7: Student portal verification: PIN is HIDDEN and class is visible
def test_07_student_portal_pin_hidden_and_marked(db):
    student_user = db.query(User).filter(User.email == "grace.student@smartattendance.edu").first()
    headers = get_auth_token(student_user.email, student_user.role.value, student_user.id)

    # 1. Fetch student dashboard
    dash_res = client.get("/api/analytics/student", headers=headers)
    assert dash_res.status_code == 200, dash_res.text
    dash_data = dash_res.json()

    # Verify that the active session is visible to this student!
    assert len(dash_data["active_sessions"]) >= 1
    session = dash_data["active_sessions"][0]

    # CRITICAL SECURITY CHECK:
    # Student portal MUST NOT receive the attendance PIN!
    assert session["attendance_pin"] is None or session["attendance_pin"] == ""

    # Get the real PIN from the active session in DB (simulating asking teacher)
    real_session = db.query(ClassSession).filter(ClassSession.id == session["id"]).first()
    secret_pin = real_session.attendance_pin

    # Student marks attendance with the PIN
    mark_payload = {
        "session_id": session["id"],
        "pin": secret_pin,
        "device_info": "Student Laptop"
    }
    mark_res = client.post("/api/attendance/mark-present", json=mark_payload, headers=headers)
    assert mark_res.status_code == 200, mark_res.text
    rec = mark_res.json()

    # DUAL CONFIRMATION CHECK:
    assert rec["student_confirmation"] is True
    assert rec["teacher_confirmation"] is False
    assert rec["status"] == "STUDENT_MARKED"

# Flow 8: Teacher confirms student -> status becomes PRESENT
def test_08_teacher_confirms_presence(db):
    teacher_user = db.query(User).filter(User.email == "prof.alan@smartattendance.edu").first()
    headers = get_auth_token(teacher_user.email, teacher_user.role.value, teacher_user.id)

    session = db.query(ClassSession).filter(ClassSession.status == SessionStatus.ACTIVE).first()
    student = db.query(Student).join(User).filter(User.email == "grace.student@smartattendance.edu").first()

    record = db.query(AttendanceRecord).filter(
        AttendanceRecord.class_session_id == session.id,
        AttendanceRecord.student_id == student.id
    ).first()
    assert record is not None

    confirm_payload = {
        "session_id": session.id,
        "attendance_record_ids": [record.id],
        "confirmed_status": "PRESENT"
    }
    res = client.post("/api/attendance/teacher-confirm", json=confirm_payload, headers=headers)
    assert res.status_code == 200, res.text
    confirmed = res.json()
    assert len(confirmed) == 1
    assert confirmed[0]["student_confirmation"] is True
    assert confirmed[0]["teacher_confirmation"] is True
    assert confirmed[0]["status"] == "PRESENT"

# Flow 9: Teacher ends and finalizes class
def test_09_teacher_ends_class(db):
    teacher_user = db.query(User).filter(User.email == "prof.alan@smartattendance.edu").first()
    headers = get_auth_token(teacher_user.email, teacher_user.role.value, teacher_user.id)
    session = db.query(ClassSession).filter(ClassSession.status == SessionStatus.ACTIVE).first()

    close_res = client.post(f"/api/classes/{session.id}/close", headers=headers)
    assert close_res.status_code == 200, close_res.text
    assert close_res.json()["status"] == "COMPLETED"

# Flow 10: Admin dashboard stats
def test_10_admin_stats(db):
    admin = db.query(User).filter(User.role == UserRole.ADMIN).first()
    headers = get_auth_token(admin.email, admin.role.value, admin.id)

    res = client.get("/api/analytics/admin", headers=headers)
    assert res.status_code == 200, res.text
    stats = res.json()
    assert stats["total_subjects"] >= 1
    assert stats["total_teachers"] >= 1
    assert stats["total_students"] >= 1
    assert stats["present_students_today"] >= 1

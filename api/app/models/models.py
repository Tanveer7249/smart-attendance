from datetime import datetime, timezone
from enum import Enum as PyEnum
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Float, ForeignKey,
    Enum, Text, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from app.core.database import Base

def utcnow():
    return datetime.now(timezone.utc)

class UserRole(str, PyEnum):
    ADMIN = "ADMIN"
    TEACHER = "TEACHER"
    STUDENT = "STUDENT"

class AttendanceStatus(str, PyEnum):
    NOT_MARKED = "NOT_MARKED"
    STUDENT_MARKED = "STUDENT_MARKED"
    TEACHER_CONFIRMED = "TEACHER_CONFIRMED"
    PRESENT = "PRESENT"
    LATE = "LATE"
    ABSENT = "ABSENT"
    REJECTED = "REJECTED"
    LEAVE_PENDING = "LEAVE_PENDING"
    ON_LEAVE = "ON_LEAVE"

class SessionStatus(str, PyEnum):
    SCHEDULED = "SCHEDULED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

class LeaveStatus(str, PyEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class DisputeStatus(str, PyEnum):
    PENDING = "PENDING"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"

class NotificationType(str, PyEnum):
    ALERT = "ALERT"
    ABSENCE = "ABSENCE"
    LEAVE_UPDATE = "LEAVE_UPDATE"
    TIMETABLE = "TIMETABLE"
    DISPUTE_UPDATE = "DISPUTE_UPDATE"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    phone = Column(String(50), nullable=True)
    avatar_url = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    teacher_profile = relationship("Teacher", back_populates="user", uselist=False, cascade="all, delete-orphan")
    student_profile = relationship("Student", back_populates="user", uselist=False, cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")

class Teacher(Base):
    __tablename__ = "teachers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    employee_id = Column(String(50), unique=True, index=True, nullable=True)
    department = Column(String(100), default="General Faculty")
    designation = Column(String(100), default="Professor")

    # Relationships
    user = relationship("User", back_populates="teacher_profile")
    class_sessions = relationship("ClassSession", back_populates="teacher")
    student_assignments = relationship("TeacherStudentAssignment", back_populates="teacher", cascade="all, delete-orphan")
    course_assignments = relationship("TeacherCourseAssignment", back_populates="teacher", cascade="all, delete-orphan")

class Batch(Base):
    __tablename__ = "batches"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    code = Column(String(50), unique=True, index=True, nullable=False)
    department = Column(String(100), default="General")
    academic_year = Column(String(50), default="2026")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    students = relationship("Student", back_populates="batch")
    class_sessions = relationship("ClassSession", back_populates="batch")

class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    code = Column(String(50), unique=True, index=True, nullable=False)
    department = Column(String(100), default="General")
    credits = Column(Integer, default=3)
    semester = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)

    # Relationships
    class_sessions = relationship("ClassSession", back_populates="subject")
    teacher_assignments = relationship("TeacherCourseAssignment", back_populates="subject", cascade="all, delete-orphan")

class TeacherCourseAssignment(Base):
    """
    Admin assigns Teachers to Courses.
    One teacher can take multiple courses, and multiple teachers can take the same course.
    """
    __tablename__ = "teacher_course_assignments"

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    assigned_at = Column(DateTime, default=utcnow)

    __table_args__ = (
        UniqueConstraint("teacher_id", "subject_id", name="uq_teacher_course"),
    )

    teacher = relationship("Teacher", back_populates="course_assignments")
    subject = relationship("Subject", back_populates="teacher_assignments")

class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    roll_number = Column(String(50), nullable=True) # Optional, not required
    batch_id = Column(Integer, ForeignKey("batches.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    user = relationship("User", back_populates="student_profile")
    batch = relationship("Batch", back_populates="students")
    attendance_records = relationship("AttendanceRecord", back_populates="student", cascade="all, delete-orphan")
    leave_requests = relationship("LeaveRequest", back_populates="student", cascade="all, delete-orphan")
    disputes = relationship("AttendanceDispute", back_populates="student", cascade="all, delete-orphan")
    teacher_assignments = relationship("TeacherStudentAssignment", back_populates="student", cascade="all, delete-orphan")

class TeacherStudentAssignment(Base):
    """
    Direct Assignment: Administrator assigns specific students to specific Teachers.
    Many-to-Many: One or more teachers can have one student, and one or more students can have one teacher.
    """
    __tablename__ = "teacher_student_assignments"

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    assigned_at = Column(DateTime, default=utcnow)

    __table_args__ = (
        UniqueConstraint("teacher_id", "student_id", "subject_id", name="uq_teacher_student_subject"),
    )

    # Relationships
    teacher = relationship("Teacher", back_populates="student_assignments")
    student = relationship("Student", back_populates="teacher_assignments")
    subject = relationship("Subject")

class ClassSession(Base):
    __tablename__ = "class_sessions"

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    batch_id = Column(Integer, ForeignKey("batches.id", ondelete="SET NULL"), nullable=True)
    
    title = Column(String(200), nullable=False)
    session_date = Column(String(20), nullable=False) # YYYY-MM-DD
    start_time = Column(String(20), nullable=False)   # HH:MM
    end_time = Column(String(20), nullable=True)     # HH:MM
    duration_minutes = Column(Integer, default=60, nullable=False)
    room_number = Column(String(50), nullable=True, default=None) # Optional
    status = Column(Enum(SessionStatus), default=SessionStatus.SCHEDULED, nullable=False)
    
    # Verification & Security
    attendance_pin = Column(String(10), nullable=False) # 6 digit PIN
    current_qr_token = Column(String(255), nullable=True)
    qr_token_expires_at = Column(DateTime, nullable=True)
    late_threshold_minutes = Column(Integer, default=15)
    
    # Configurable Geofencing
    require_gps = Column(Boolean, default=False)
    target_latitude = Column(Float, nullable=True)
    target_longitude = Column(Float, nullable=True)
    gps_radius_meters = Column(Float, default=150.0)

    created_at = Column(DateTime, default=utcnow)
    started_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)

    # Relationships
    teacher = relationship("Teacher", back_populates="class_sessions")
    subject = relationship("Subject", back_populates="class_sessions")
    batch = relationship("Batch", back_populates="class_sessions")
    attendance_records = relationship("AttendanceRecord", back_populates="class_session", cascade="all, delete-orphan")
    tokens = relationship("AttendanceToken", back_populates="class_session", cascade="all, delete-orphan")

class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id = Column(Integer, primary_key=True, index=True)
    class_session_id = Column(Integer, ForeignKey("class_sessions.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)

    # DUAL CONFIRMATION LOGIC
    # Attendance is PRESENT only if BOTH student_confirmation AND teacher_confirmation are True!
    student_confirmation = Column(Boolean, default=False, nullable=False)
    student_confirmed_at = Column(DateTime, nullable=True)
    student_lat = Column(Float, nullable=True)
    student_lng = Column(Float, nullable=True)
    student_device = Column(String(255), nullable=True)

    teacher_confirmation = Column(Boolean, default=False, nullable=False)
    teacher_confirmed_at = Column(DateTime, nullable=True)
    confirmed_by_teacher_id = Column(Integer, ForeignKey("teachers.id", ondelete="SET NULL"), nullable=True)

    status = Column(Enum(AttendanceStatus), default=AttendanceStatus.NOT_MARKED, nullable=False)
    rejection_reason = Column(String(255), nullable=True)
    
    # Audit & Manual Correction tracking
    is_manual_correction = Column(Boolean, default=False)
    manual_correction_reason = Column(String(255), nullable=True)
    manual_corrected_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        UniqueConstraint("class_session_id", "student_id", name="uq_session_student"),
        Index("idx_attendance_session_status", "class_session_id", "status"),
    )

    # Relationships
    class_session = relationship("ClassSession", back_populates="attendance_records")
    student = relationship("Student", back_populates="attendance_records")
    confirmed_by_teacher = relationship("Teacher", foreign_keys=[confirmed_by_teacher_id])
    dispute = relationship("AttendanceDispute", back_populates="attendance_record", uselist=False)

class AttendanceToken(Base):
    __tablename__ = "attendance_tokens"

    id = Column(Integer, primary_key=True, index=True)
    class_session_id = Column(Integer, ForeignKey("class_sessions.id", ondelete="CASCADE"), nullable=False)
    token = Column(String(255), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=utcnow)

    class_session = relationship("ClassSession", back_populates="tokens")

class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    start_date = Column(String(20), nullable=False) # YYYY-MM-DD
    end_date = Column(String(20), nullable=False)   # YYYY-MM-DD
    reason = Column(Text, nullable=False)
    status = Column(Enum(LeaveStatus), default=LeaveStatus.PENDING, nullable=False)
    reviewed_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    review_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    # Relationships
    student = relationship("Student", back_populates="leave_requests")
    reviewer = relationship("User", foreign_keys=[reviewed_by_user_id])

class AttendanceDispute(Base):
    __tablename__ = "attendance_disputes"

    id = Column(Integer, primary_key=True, index=True)
    attendance_record_id = Column(Integer, ForeignKey("attendance_records.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    reason = Column(Text, nullable=False)
    requested_status = Column(String(50), default="PRESENT")
    status = Column(Enum(DisputeStatus), default=DisputeStatus.PENDING, nullable=False)
    resolution_notes = Column(Text, nullable=True)
    resolved_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    # Relationships
    attendance_record = relationship("AttendanceRecord", back_populates="dispute")
    student = relationship("Student", back_populates="disputes")
    resolver = relationship("User", foreign_keys=[resolved_by_user_id])

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(Enum(NotificationType), default=NotificationType.ALERT, nullable=False)
    is_read = Column(Boolean, default=False)
    link_url = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    user = relationship("User", back_populates="notifications")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    user_email = Column(String(255), nullable=True)
    action = Column(String(100), nullable=False)
    entity_type = Column(String(100), nullable=False)
    entity_id = Column(Integer, nullable=True)
    details = Column(Text, nullable=True)
    old_values = Column(Text, nullable=True)
    new_values = Column(Text, nullable=True)
    ip_address = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=utcnow)

class SystemSettings(Base):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    min_attendance_threshold = Column(Float, default=75.0)
    default_late_threshold_minutes = Column(Integer, default=15)
    default_qr_refresh_seconds = Column(Integer, default=30)
    allow_pin_fallback = Column(Boolean, default=True)
    gps_verification_enabled = Column(Boolean, default=False)
    campus_latitude = Column(Float, default=37.7749)
    campus_longitude = Column(Float, default=-122.4194)
    campus_radius_meters = Column(Float, default=200.0)

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr
from app.models.models import (
    UserRole, AttendanceStatus, SessionStatus,
    LeaveStatus, DisputeStatus, NotificationType
)

# Authentication schemas
class LoginRequest(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"

class TokenPayload(BaseModel):
    sub: Optional[str] = None
    role: Optional[str] = None
    user_id: Optional[int] = None

# User Schemas
class UserBase(BaseModel):
    email: str
    full_name: str
    role: UserRole
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool = True

class UserCreate(UserBase):
    password: str
    # Teacher fields
    employee_id: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    # Student fields
    roll_number: Optional[str] = None
    batch_id: Optional[int] = None
    assigned_teacher_id: Optional[int] = None

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None

class TeacherProfileResponse(BaseModel):
    id: int
    employee_id: str
    department: str
    designation: Optional[str] = None
    assigned_student_count: Optional[int] = 0

    class Config:
        from_attributes = True

class StudentProfileResponse(BaseModel):
    id: int
    roll_number: Optional[str] = None
    batch_id: Optional[int] = None
    batch_name: Optional[str] = None
    assigned_teacher_name: Optional[str] = None

    class Config:
        from_attributes = True

class UserResponse(UserBase):
    id: int
    created_at: datetime
    teacher_profile: Optional[TeacherProfileResponse] = None
    student_profile: Optional[StudentProfileResponse] = None

    class Config:
        from_attributes = True

# Academics Schemas
class BatchBase(BaseModel):
    name: str
    code: str
    department: str
    academic_year: str
    is_active: bool = True

class BatchCreate(BatchBase):
    pass

class BatchResponse(BatchBase):
    id: int
    student_count: Optional[int] = 0
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class SubjectBase(BaseModel):
    name: str
    code: str
    department: str
    credits: int = 3
    semester: int = 1
    is_active: bool = True

class SubjectCreate(SubjectBase):
    pass

class SubjectResponse(SubjectBase):
    id: int

    class Config:
        from_attributes = True

# Teacher-Course Assignment Schemas
class TeacherCourseAssignmentCreate(BaseModel):
    teacher_id: int
    subject_ids: List[int]

class TeacherCourseAssignmentResponse(BaseModel):
    id: int
    teacher_id: int
    teacher_name: Optional[str] = None
    subject_id: int
    subject_name: Optional[str] = None
    subject_code: Optional[str] = None
    assigned_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Teacher-Student Assignment Schemas
class TeacherStudentAssignmentCreate(BaseModel):
    teacher_id: int
    student_ids: List[int]
    subject_id: Optional[int] = None

class TeacherStudentAssignmentResponse(BaseModel):
    id: int
    teacher_id: int
    teacher_name: Optional[str] = None
    student_id: int
    student_name: Optional[str] = None
    student_roll: Optional[str] = None
    subject_id: Optional[int] = None
    subject_name: Optional[str] = None
    assigned_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Class Session Schemas
class ClassSessionCreate(BaseModel):
    subject_id: int
    title: str
    session_date: str # YYYY-MM-DD
    start_time: str   # HH:MM
    duration_minutes: int = 60
    student_ids: Optional[List[int]] = None # Specific student(s) selected by teacher!
    batch_id: Optional[int] = None
    room_number: Optional[str] = None
    late_threshold_minutes: int = 15
    require_gps: bool = False
    target_latitude: Optional[float] = None
    target_longitude: Optional[float] = None
    gps_radius_meters: Optional[float] = 150.0

class ClassSessionResponse(BaseModel):
    id: int
    teacher_id: int
    teacher_name: Optional[str] = None
    subject_id: int
    subject_name: Optional[str] = None
    subject_code: Optional[str] = None
    batch_id: Optional[int] = None
    batch_name: Optional[str] = None
    title: str
    session_date: str
    start_time: str
    end_time: Optional[str] = None
    duration_minutes: int
    room_number: Optional[str] = None
    status: SessionStatus
    attendance_pin: Optional[str] = None
    current_qr_token: Optional[str] = None
    qr_token_expires_at: Optional[datetime] = None
    late_threshold_minutes: int
    require_gps: bool
    target_latitude: Optional[float] = None
    target_longitude: Optional[float] = None
    gps_radius_meters: Optional[float] = None
    total_enrolled: Optional[int] = 0
    total_marked_student: Optional[int] = 0
    total_confirmed_present: Optional[int] = 0
    total_late: Optional[int] = 0
    total_absent: Optional[int] = 0
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Attendance Schemas
class StudentMarkAttendanceRequest(BaseModel):
    session_id: int
    token: Optional[str] = None
    pin: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    device_info: Optional[str] = None

class TeacherConfirmRequest(BaseModel):
    record_ids: List[int]
    status: AttendanceStatus = AttendanceStatus.PRESENT

class TeacherRejectRequest(BaseModel):
    record_id: int
    reason: str

class ManualAttendanceCorrectionRequest(BaseModel):
    record_id: int
    status: AttendanceStatus
    reason: str

class AttendanceRecordResponse(BaseModel):
    id: int
    class_session_id: int
    session_title: Optional[str] = None
    subject_name: Optional[str] = None
    session_date: Optional[str] = None
    student_id: int
    student_name: Optional[str] = None
    student_roll: Optional[str] = None
    student_confirmation: bool
    student_confirmed_at: Optional[datetime] = None
    student_lat: Optional[float] = None
    student_lng: Optional[float] = None
    student_device: Optional[str] = None
    teacher_confirmation: bool
    teacher_confirmed_at: Optional[datetime] = None
    confirmed_by_teacher_name: Optional[str] = None
    status: AttendanceStatus
    rejection_reason: Optional[str] = None
    is_manual_correction: bool = False
    manual_correction_reason: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Leave Schemas
class LeaveRequestCreate(BaseModel):
    start_date: str
    end_date: str
    reason: str

class LeaveRequestReview(BaseModel):
    status: LeaveStatus
    review_notes: Optional[str] = None

class LeaveRequestResponse(BaseModel):
    id: int
    student_id: int
    student_name: Optional[str] = None
    student_roll: Optional[str] = None
    batch_name: Optional[str] = None
    start_date: str
    end_date: str
    reason: str
    status: LeaveStatus
    reviewed_by_name: Optional[str] = None
    review_notes: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Attendance Dispute Schemas
class AttendanceDisputeCreate(BaseModel):
    attendance_record_id: int
    reason: str
    requested_status: Optional[str] = "PRESENT"

class AttendanceDisputeResolve(BaseModel):
    status: DisputeStatus
    resolution_notes: str
    apply_status_change: bool = True
    new_attendance_status: Optional[AttendanceStatus] = AttendanceStatus.PRESENT

class AttendanceDisputeResponse(BaseModel):
    id: int
    attendance_record_id: int
    session_title: Optional[str] = None
    session_date: Optional[str] = None
    subject_name: Optional[str] = None
    current_attendance_status: Optional[str] = None
    student_id: int
    student_name: Optional[str] = None
    student_roll: Optional[str] = None
    reason: str
    requested_status: str
    status: DisputeStatus
    resolution_notes: Optional[str] = None
    resolved_by_name: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Notification Schemas
class NotificationResponse(BaseModel):
    id: int
    user_id: int
    title: str
    message: str
    type: NotificationType
    is_read: bool
    link_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

# Audit Log Schemas
class AuditLogResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    user_email: Optional[str] = None
    action: str
    entity_type: str
    entity_id: Optional[int] = None
    details: Optional[str] = None
    old_values: Optional[str] = None
    new_values: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

# System Settings Schemas
class SystemSettingsResponse(BaseModel):
    id: int
    min_attendance_threshold: float
    default_late_threshold_minutes: int
    default_qr_refresh_seconds: int
    allow_pin_fallback: bool
    gps_verification_enabled: bool
    campus_latitude: float
    campus_longitude: float
    campus_radius_meters: float

    class Config:
        from_attributes = True

class SystemSettingsUpdate(BaseModel):
    min_attendance_threshold: Optional[float] = None
    default_late_threshold_minutes: Optional[int] = None
    default_qr_refresh_seconds: Optional[int] = None
    allow_pin_fallback: Optional[bool] = None
    gps_verification_enabled: Optional[bool] = None
    campus_latitude: Optional[float] = None
    campus_longitude: Optional[float] = None
    campus_radius_meters: Optional[float] = None

# Analytics & Dashboard Schemas
class SubjectAttendanceSummary(BaseModel):
    subject_id: int
    subject_name: str
    subject_code: str
    total_classes: int
    attended_classes: int
    late_classes: int
    absent_classes: int
    percentage: float
    is_at_risk: bool

class StudentDashboardStats(BaseModel):
    student_id: int
    student_name: str
    roll_number: Optional[str] = None
    batch_name: Optional[str] = None
    assigned_teachers: List[str]
    total_classes: int
    present_count: int
    late_count: int
    absent_count: int
    overall_percentage: float
    is_at_risk: bool
    subject_breakdown: List[SubjectAttendanceSummary]
    recent_records: List[AttendanceRecordResponse]
    active_sessions: List[ClassSessionResponse]
    pending_leaves: int
    unread_notifications: int

class TeacherDashboardStats(BaseModel):
    teacher_id: int
    teacher_name: str
    employee_id: Optional[str] = None
    department: str
    assigned_students_count: int
    assigned_students: List[Dict[str, Any]]
    assigned_courses: Optional[List[SubjectResponse]] = []
    today_classes_count: int
    active_session: Optional[ClassSessionResponse] = None
    total_classes_conducted: int
    average_attendance_percentage: float
    upcoming_classes: List[ClassSessionResponse]

class AdminDashboardStats(BaseModel):
    total_students: int
    total_teachers: int
    total_batches: int
    total_subjects: int
    classes_conducted_today: int
    present_students_today: int
    absent_students_today: int
    late_students_today: int
    average_attendance_percentage: float
    students_below_threshold: int
    threshold_percentage: float
    at_risk_students: List[Dict[str, Any]]
    weekly_trends: List[Dict[str, Any]]
    monthly_trends: List[Dict[str, Any]]
    active_sessions: List[ClassSessionResponse]

export type UserRole = 'ADMIN' | 'TEACHER' | 'STUDENT';

export type AttendanceStatus =
  | 'NOT_MARKED'
  | 'STUDENT_MARKED'
  | 'TEACHER_CONFIRMED'
  | 'PRESENT'
  | 'LATE'
  | 'ABSENT'
  | 'REJECTED'
  | 'LEAVE_PENDING'
  | 'ON_LEAVE';

export type SessionStatus = 'SCHEDULED' | 'ACTIVE' | 'COMPLETED' | 'CANCELLED';

export type LeaveStatus = 'PENDING' | 'APPROVED' | 'REJECTED';

export type DisputeStatus = 'PENDING' | 'RESOLVED' | 'REJECTED';

export type NotificationType = 'ATTENDANCE' | 'LEAVE' | 'DISPUTE' | 'ALERT' | 'TIMETABLE';

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: UserRole;
  phone?: string;
  avatar_url?: string;
  is_active: boolean;
  created_at: string;
  teacher_profile?: {
    id: number;
    employee_id?: string;
    department: string;
    designation?: string;
    assigned_student_count?: number;
  };
  student_profile?: {
    id: number;
    roll_number?: string;
    batch_id?: number;
    batch_name?: string;
    assigned_teacher_name?: string;
  };
}

export interface Batch {
  id: number;
  name: string;
  code: string;
  department: string;
  academic_year: string;
  is_active: boolean;
  student_count?: number;
}

export interface Subject {
  id: number;
  name: string;
  code: string;
  department: string;
  credits: number;
  semester: number;
  is_active: boolean;
}

export interface TeacherCourseAssignment {
  id: number;
  teacher_id: number;
  teacher_name?: string;
  subject_id: number;
  subject_name?: string;
  subject_code?: string;
  assigned_at?: string;
}

export interface TeacherStudentAssignment {
  id: number;
  teacher_id: number;
  teacher_name?: string;
  student_id: number;
  student_name?: string;
  student_roll?: string;
  subject_id?: number;
  subject_name?: string;
  assigned_at?: string;
}

export interface ClassSession {
  id: number;
  teacher_id: number;
  teacher_name?: string;
  subject_id: number;
  subject_name?: string;
  subject_code?: string;
  batch_id?: number;
  batch_name?: string;
  title: string;
  session_date: string;
  start_time: string;
  end_time?: string;
  duration_minutes: number;
  room_number?: string;
  status: SessionStatus;
  attendance_pin?: string;
  current_qr_token?: string;
  qr_token_expires_at?: string;
  late_threshold_minutes: number;
  require_gps: boolean;
  target_latitude?: number;
  target_longitude?: number;
  gps_radius_meters?: number;
  total_enrolled?: number;
  total_marked_student?: number;
  total_confirmed_present?: number;
  total_late?: number;
  total_absent?: number;
  created_at?: string;
}

export interface AttendanceRecord {
  id: number;
  class_session_id: number;
  session_title?: string;
  subject_name?: string;
  session_date?: string;
  student_id: number;
  student_name?: string;
  student_roll?: string;
  student_confirmation: boolean;
  student_confirmed_at?: string;
  student_lat?: number;
  student_lng?: number;
  student_device?: string;
  teacher_confirmation: boolean;
  teacher_confirmed_at?: string;
  confirmed_by_teacher_name?: string;
  status: AttendanceStatus;
  rejection_reason?: string;
  is_manual_correction?: boolean;
  manual_correction_reason?: string;
  created_at?: string;
  updated_at?: string;
}

export interface SubjectAttendanceSummary {
  subject_id: number;
  subject_name: string;
  subject_code: string;
  total_classes: number;
  attended_classes: number;
  late_classes: number;
  absent_classes: number;
  percentage: float;
  is_at_risk: boolean;
}

type float = number;

export interface StudentDashboardStats {
  student_id: number;
  student_name: string;
  roll_number?: string;
  batch_name?: string;
  assigned_teachers: string[];
  total_classes: number;
  present_count: number;
  late_count: number;
  absent_count: number;
  overall_percentage: number;
  is_at_risk: boolean;
  subject_breakdown: SubjectAttendanceSummary[];
  recent_records: AttendanceRecord[];
  active_sessions: ClassSession[];
  pending_leaves: number;
  unread_notifications: number;
}

export interface TeacherDashboardStats {
  teacher_id: number;
  teacher_name: string;
  employee_id?: string;
  department: string;
  assigned_students_count: number;
  assigned_students: Array<{
    assignment_id: number;
    student_id: number;
    full_name: string;
    email: string;
    roll_number?: string;
    batch_name?: string;
    assigned_at: string;
  }>;
  assigned_courses?: Subject[];
  today_classes_count: number;
  active_session?: ClassSession;
  total_classes_conducted: number;
  average_attendance_percentage: number;
  upcoming_classes: ClassSession[];
}

export interface AdminDashboardStats {
  total_students: number;
  total_teachers: number;
  total_batches: number;
  total_subjects: number;
  classes_conducted_today: number;
  present_students_today: number;
  absent_students_today: number;
  late_students_today: number;
  average_attendance_percentage: number;
  students_below_threshold: number;
  threshold_percentage: number;
  at_risk_students: Array<{
    student_id: number;
    name: string;
    roll_number?: string;
    batch_name?: string;
    total_classes: number;
    attended_classes: number;
    percentage: number;
  }>;
  weekly_trends: Array<{
    date?: string;
    day: string;
    present: number;
    absent: number;
    late: number;
  }>;
  monthly_trends: Array<{
    month: string;
    attendance_rate: number;
  }>;
  active_sessions: ClassSession[];
}

export interface LeaveRequest {
  id: number;
  student_id: number;
  student_name?: string;
  student_roll?: string;
  batch_name?: string;
  start_date: string;
  end_date: string;
  reason: string;
  status: LeaveStatus;
  reviewed_by_name?: string;
  review_notes?: string;
  created_at?: string;
}

export interface AttendanceDispute {
  id: number;
  attendance_record_id: number;
  session_title?: string;
  session_date?: string;
  subject_name?: string;
  current_attendance_status?: string;
  student_id: number;
  student_name?: string;
  student_roll?: string;
  reason: string;
  requested_status: string;
  status: DisputeStatus;
  resolution_notes?: string;
  resolved_by_name?: string;
  created_at?: string;
}

export interface AppNotification {
  id: number;
  user_id: number;
  title: string;
  message: string;
  type: NotificationType;
  is_read: boolean;
  link_url?: string;
  created_at: string;
}

export interface AuditLog {
  id: number;
  user_id?: number;
  user_email?: string;
  action: string;
  entity_type: string;
  entity_id?: number;
  details?: string;
  old_values?: string;
  new_values?: string;
  created_at: string;
}

export interface SystemSettings {
  id: number;
  min_attendance_threshold: number;
  default_late_threshold_minutes: number;
  default_qr_refresh_seconds: number;
  allow_pin_fallback: boolean;
  gps_verification_enabled: boolean;
  campus_latitude: number;
  campus_longitude: number;
  campus_radius_meters: number;
}

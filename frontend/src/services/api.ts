import {
  User, Batch, Subject, ClassSession, AttendanceRecord,
  AdminDashboardStats, TeacherDashboardStats, StudentDashboardStats,
  LeaveRequest, AttendanceDispute, AppNotification,
  AuditLog, SystemSettings, AttendanceStatus, SessionStatus,
  TeacherStudentAssignment, TeacherCourseAssignment
} from '../types';

const BASE_URL = '/api';

class ApiClient {
  private getToken(): string | null {
    return localStorage.getItem('auth_token');
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const token = this.getToken();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string> || {}),
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${BASE_URL}${endpoint}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      let errorDetail = 'An error occurred';
      try {
        const errJson = await response.json();
        errorDetail = errJson.detail || errJson.message || errorDetail;
      } catch {
        errorDetail = response.statusText;
      }
      throw new Error(errorDetail);
    }

    if (response.status === 204) {
      return {} as T;
    }

    return response.json();
  }

  // Auth
  async login(email: string, password: string): Promise<{ access_token: string; user: User }> {
    return this.request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
  }

  async getMe(): Promise<User> {
    return this.request('/auth/me');
  }

  // Users Management
  async getUsers(role?: string): Promise<User[]> {
    const query = role ? `?role=${role}` : '';
    return this.request(`/users${query}`);
  }

  async createUser(data: any): Promise<User> {
    return this.request('/users', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateUser(id: number, data: any): Promise<User> {
    return this.request(`/users/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteUser(id: number): Promise<{ message: string }> {
    return this.request(`/users/${id}`, {
      method: 'DELETE',
    });
  }

  // Teacher-Student Assignments
  async assignStudents(data: { teacher_id: number; student_ids: number[]; subject_id?: number }): Promise<TeacherStudentAssignment[]> {
    return this.request('/users/assign-students', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getAssignments(teacherId?: number): Promise<TeacherStudentAssignment[]> {
    const q = teacherId ? `?teacher_id=${teacherId}` : '';
    return this.request(`/users/assignments${q}`);
  }

  async removeAssignment(assignmentId: number): Promise<{ message: string }> {
    return this.request(`/users/assignments/${assignmentId}`, {
      method: 'DELETE',
    });
  }

  // Academics & Courses
  async getBatches(): Promise<Batch[]> {
    return this.request('/academics/batches');
  }

  async createBatch(data: Partial<Batch>): Promise<Batch> {
    return this.request('/academics/batches', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getSubjects(teacherId?: number): Promise<Subject[]> {
    const q = teacherId ? `?teacher_id=${teacherId}` : '';
    return this.request(`/academics/subjects${q}`);
  }

  async createSubject(data: Partial<Subject>): Promise<Subject> {
    return this.request('/academics/subjects', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async assignTeacherCourses(data: { teacher_id: number; subject_ids: number[] }): Promise<TeacherCourseAssignment[]> {
    return this.request('/academics/assign-teacher-courses', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getTeacherCourses(teacherId?: number, subjectId?: number): Promise<TeacherCourseAssignment[]> {
    const sp = new URLSearchParams();
    if (teacherId) sp.append('teacher_id', teacherId.toString());
    if (subjectId) sp.append('subject_id', subjectId.toString());
    const query = sp.toString() ? `?${sp.toString()}` : '';
    return this.request(`/academics/teacher-courses${query}`);
  }

  async removeTeacherCourse(assignmentId: number): Promise<{ message: string }> {
    return this.request(`/academics/teacher-courses/${assignmentId}`, {
      method: 'DELETE',
    });
  }

  // Classes & Live Sessions
  async getClasses(params?: {
    batch_id?: number;
    subject_id?: number;
    teacher_id?: number;
    session_status?: SessionStatus;
    session_date?: string;
  }): Promise<ClassSession[]> {
    const sp = new URLSearchParams();
    if (params?.batch_id) sp.append('batch_id', params.batch_id.toString());
    if (params?.subject_id) sp.append('subject_id', params.subject_id.toString());
    if (params?.teacher_id) sp.append('teacher_id', params.teacher_id.toString());
    if (params?.session_status) sp.append('session_status', params.session_status);
    if (params?.session_date) sp.append('session_date', params.session_date);
    return this.request(`/classes?${sp.toString()}`);
  }

  async createClass(data: any): Promise<ClassSession> {
    return this.request('/classes', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async startClass(sessionId: number): Promise<ClassSession> {
    return this.request(`/classes/${sessionId}/start`, {
      method: 'POST',
    });
  }

  async refreshQrToken(sessionId: number): Promise<{ token: string; expires_at: string; pin: string }> {
    return this.request(`/classes/${sessionId}/qr-token`, {
      method: 'POST',
    });
  }

  async closeSession(sessionId: number): Promise<ClassSession> {
    return this.request(`/classes/${sessionId}/close`, {
      method: 'POST',
    });
  }

  async getSessionAttendees(sessionId: number): Promise<AttendanceRecord[]> {
    return this.request(`/classes/${sessionId}/attendees`);
  }

  // Attendance Engine
  async studentMarkPresent(data: {
    session_id: number;
    token?: string;
    pin?: string;
    latitude?: number;
    longitude?: number;
    device_info?: string;
  }): Promise<AttendanceRecord> {
    return this.request('/attendance/mark-present', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async teacherConfirmStudents(
    sessionId: number,
    recordIds: number[],
    status: AttendanceStatus = 'PRESENT'
  ): Promise<AttendanceRecord[]> {
    return this.request(`/attendance/confirm?session_id=${sessionId}`, {
      method: 'POST',
      body: JSON.stringify({ record_ids: recordIds, status }),
    });
  }

  async teacherRejectStudent(sessionId: number, recordId: number, reason: string): Promise<AttendanceRecord> {
    return this.request(`/attendance/reject?session_id=${sessionId}`, {
      method: 'POST',
      body: JSON.stringify({ record_id: recordId, reason }),
    });
  }

  async manualAttendanceCorrection(recordId: number, status: AttendanceStatus, reason: string): Promise<AttendanceRecord> {
    return this.request('/attendance/manual-correction', {
      method: 'POST',
      body: JSON.stringify({ record_id: recordId, status, reason }),
    });
  }

  async getMyAttendanceHistory(subjectId?: number): Promise<AttendanceRecord[]> {
    const q = subjectId ? `?subject_id=${subjectId}` : '';
    return this.request(`/attendance/my-history${q}`);
  }

  async getAllRecords(params?: {
    session_id?: number;
    student_id?: number;
    status_filter?: AttendanceStatus;
  }): Promise<AttendanceRecord[]> {
    const sp = new URLSearchParams();
    if (params?.session_id) sp.append('session_id', params.session_id.toString());
    if (params?.student_id) sp.append('student_id', params.student_id.toString());
    if (params?.status_filter) sp.append('status_filter', params.status_filter);
    return this.request(`/attendance/records?${sp.toString()}`);
  }

  // Analytics & Dashboards
  async getAdminDashboard(): Promise<AdminDashboardStats> {
    return this.request('/analytics/admin');
  }

  async getTeacherDashboard(): Promise<TeacherDashboardStats> {
    return this.request('/analytics/teacher');
  }

  async getStudentDashboard(studentId?: number): Promise<StudentDashboardStats> {
    const q = studentId ? `?student_id=${studentId}` : '';
    return this.request(`/analytics/student${q}`);
  }

  // Export functions
  async downloadExcelReport(batchId?: number, subjectId?: number): Promise<void> {
    const token = this.getToken();
    const sp = new URLSearchParams();
    if (batchId) sp.append('batch_id', batchId.toString());
    if (subjectId) sp.append('subject_id', subjectId.toString());

    const response = await fetch(`${BASE_URL}/analytics/export/excel?${sp.toString()}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });

    if (!response.ok) throw new Error('Failed to download Excel report');
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `attendance_report_${new Date().toISOString().split('T')[0]}.xlsx`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  }

  async downloadPdfReport(batchId?: number, subjectId?: number): Promise<void> {
    const token = this.getToken();
    const sp = new URLSearchParams();
    if (batchId) sp.append('batch_id', batchId.toString());
    if (subjectId) sp.append('subject_id', subjectId.toString());

    const response = await fetch(`${BASE_URL}/analytics/export/pdf?${sp.toString()}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });

    if (!response.ok) throw new Error('Failed to download PDF report');
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `attendance_report_${new Date().toISOString().split('T')[0]}.pdf`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  }

  // Leaves
  async getLeaves(status?: string): Promise<LeaveRequest[]> {
    const q = status ? `?status_filter=${status}` : '';
    return this.request(`/leaves${q}`);
  }

  async submitLeave(data: { start_date: string; end_date: string; reason: string }): Promise<LeaveRequest> {
    return this.request('/leaves', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async reviewLeave(leaveId: number, status: 'APPROVED' | 'REJECTED', reviewNotes?: string): Promise<LeaveRequest> {
    return this.request(`/leaves/${leaveId}/review`, {
      method: 'PUT',
      body: JSON.stringify({ status, review_notes: reviewNotes }),
    });
  }

  // Disputes
  async getDisputes(status?: string): Promise<AttendanceDispute[]> {
    const q = status ? `?status_filter=${status}` : '';
    return this.request(`/disputes${q}`);
  }

  async submitDispute(attendanceRecordId: number, reason: string): Promise<AttendanceDispute> {
    return this.request('/disputes', {
      method: 'POST',
      body: JSON.stringify({ attendance_record_id: attendanceRecordId, reason }),
    });
  }

  async resolveDispute(
    disputeId: number,
    status: 'RESOLVED' | 'REJECTED',
    notes: string,
    applyChange: boolean = true
  ): Promise<AttendanceDispute> {
    return this.request(`/disputes/${disputeId}/resolve`, {
      method: 'PUT',
      body: JSON.stringify({
        status,
        resolution_notes: notes,
        apply_status_change: applyChange,
        new_attendance_status: 'PRESENT',
      }),
    });
  }

  // Notifications
  async getNotifications(): Promise<AppNotification[]> {
    return this.request('/notifications');
  }

  async markNotificationRead(id: number): Promise<void> {
    return this.request(`/notifications/${id}/read`, { method: 'PUT' });
  }

  async markAllNotificationsRead(): Promise<void> {
    return this.request('/notifications/mark-all-read', { method: 'PUT' });
  }

  // Audit Logs
  async getAuditLogs(): Promise<AuditLog[]> {
    return this.request('/audit-logs');
  }

  // Settings
  async getSettings(): Promise<SystemSettings> {
    return this.request('/settings');
  }

  async updateSettings(data: Partial<SystemSettings>): Promise<SystemSettings> {
    return this.request('/settings', {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }
}

export const api = new ApiClient();

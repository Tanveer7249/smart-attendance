---
title: Smart Attendance
emoji: 🎯
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
---

# Smart Attendance Management System
### Enterprise Full-Stack Zero-Trust Attendance Architecture with Dual Confirmation

---

## 1. Core Objective & Dual-Confirmation Workflow

A common vulnerability in traditional attendance systems is that attendance is marked automatically when a student scans a QR code, permitting proxy attendance, screenshot sharing, or scanning from outside the classroom.

This system implements a **Zero-Trust Dual-Confirmation Engine**:
> **Attendance is officially recorded as `PRESENT` ONLY when BOTH the student and the authorized teacher physically confirm.**

```
[Student Logs In]                                 [Teacher Logs In]
       │                                                 │
       │                                        [Creates Class Session]
       │                                                 │
       │                                        [Starts Live Attendance]
       │                                                 │
       │                                    [Dynamic QR Code + Expiring Token]
       │                                                 │
       ├─────────────────────────────────────────────────┤
       │                                                 │
[Student Scans QR / Enters PIN]                          │
       │                                                 │
 [Backend: student_confirmation = true]                  │
 [Status: STUDENT_MARKED (Pending)]                      │
       │                                                 │
       └─────────────────────────────► [Teacher Sees Live Submission Feed]
                                                         │
                                               [Teacher Verifies Presence]
                                                         │
                                        [Backend: teacher_confirmation = true]
                                                         │
                                                         ▼
                                 ┌──────────────────────────────────────────────┐
                                 │ IF student_confirmation AND teacher_confirmation │
                                 │             STATUS = PRESENT                 │
                                 └──────────────────────────────────────────────┘
                                                         │
                                             [Session Finalize / End]
                                                         ▼
                                   [Unconfirmed Records Finalized as ABSENT]
```

### Attendance Engine States
- `NOT_MARKED`: Initial default state for enrolled students.
- `STUDENT_MARKED`: Student has submitted QR scan / PIN (awaiting faculty confirmation).
- `TEACHER_CONFIRMED`: Teacher confirmed presence before student completed scan.
- `PRESENT`: Dual confirmation satisfied (`student_confirmation == true` AND `teacher_confirmation == true`).
- `LATE`: Dual confirmation satisfied after class late threshold.
- `ABSENT`: Unresolved or unconfirmed at session closure.
- `REJECTED`: Teacher rejected a proxy attempt with recorded reason.
- `LEAVE_PENDING`: Leave application pending faculty/admin review.
- `ON_LEAVE`: Approved leave excuses student from being marked absent.

---

## 2. Pre-configured Demo Accounts

Use the **1-Click Role Switcher** in the top navigation bar or log in with these credentials:

| Portal | Full Name | Email | Password | Primary Capabilities |
| :--- | :--- | :--- | :--- | :--- |
| **Admin** | Dr. Arthur Vance | `admin@smartattendance.edu` | `Admin@123` | System analytics, user accounts, cohorts, audit trails, Excel/PDF exports |
| **Teacher** | Dr. Sarah Jenkins | `sarah.teacher@smartattendance.edu` | `Teacher@123` | Live attendance room, dynamic QR generator, dual verification, manual adjustments |
| **Student** | Alex Rivera | `alex.student@smartattendance.edu` | `Student@123` | Dynamic QR scanner, PIN entry, subject attendance %, leaves & disputes |
| **Parent** | Eleanor Rivera | `parent.alex@smartattendance.edu` | `Parent@123` | Ward monitoring, absence logs, official statement download |

---

## 3. Technology Stack

### Backend
- **Python FastAPI**: High performance asynchronous REST API & WebSocket server.
- **SQLAlchemy 2.0**: Normalized ORM models with database constraints and foreign keys.
- **SQLite / PostgreSQL**: Zero-dependency SQLite default out-of-the-box, PostgreSQL ready via `DATABASE_URL`.
- **WebSockets**: Real-time live classroom attendee feed and live event broadcast.
- **OpenPyXL**: Styled institutional Excel (`.xlsx`) export generation.
- **ReportLab**: PDF landscape formal attendance report compilation.
- **PyTest**: Automated test suite verifying all 13 core operational scenarios.

### Frontend
- **React 19 & TypeScript**: Enterprise component architecture.
- **Tailwind CSS v3**: Clean Navy Blue (`#0F172A`), Indigo (`#4F46E5`), Emerald, and White palette.
- **Recharts**: Weekly distribution and monthly trend analytics charts.
- **QRCode.react**: SVG dynamic QR code renderer with real-time countdown timer.
- **Lucide React**: Crisp iconography for accessible status indicators.

---

## 4. Quick Start & Execution Guide

### Option A: Run the Unified Full-Stack Application (Recommended)

1. **Activate Virtual Environment & Run**:
   ```bash
   backend\venv\Scripts\python run.py
   ```
2. **Access the Application**:
   - **Web UI & Dashboard**: [http://localhost:8000](http://localhost:8000)
   - **Interactive API Docs (Swagger)**: [http://localhost:8000/api/docs](http://localhost:8000/api/docs)
   - **Alternative ReDoc**: [http://localhost:8000/api/redoc](http://localhost:8000/api/redoc)

---

### Option B: Development Mode (Vite Dev Server + FastAPI)

1. **Start Backend**:
   ```bash
   cd backend
   venv\Scripts\uvicorn app.main:app --reload --port 8000
   ```

2. **Start Frontend (in a separate terminal)**:
   ```bash
   cd frontend
   npm run dev
   ```
   Open [http://localhost:3000](http://localhost:3000) (proxies requests to `:8000`).

---

## 5. Running the Automated Test Suite

The test suite in `backend/tests/test_attendance_system.py` validates all 13 core scenarios:

```bash
cd backend
venv\Scripts\pytest -v tests/
```

### Verified Test Cases:
1. `test_scenario_1_teacher_creates_class`: Teacher successfully schedules a class with duration, room, and PIN.
2. `test_scenario_2_and_5_student_marks_attendance_dual_confirmation`: Student submits attendance; state transitions to `STUDENT_MARKED` (NOT `PRESENT` until teacher confirms).
3. `test_scenario_3_student_cannot_mark_twice`: Duplicate submission rejection.
4. `test_scenario_4_and_5_teacher_confirms_dual_attendance`: Teacher verifies student; state transitions to `PRESENT` only after both confirmations.
5. `test_scenario_6_teacher_rejects_student`: Teacher rejects proxy submission with audit reason.
6. `test_scenario_7_qr_token_expires`: Dynamic QR tokens expire automatically after countdown.
7. `test_scenario_8_unenrolled_student_rejected`: Students outside subject or batch are denied access.
8. `test_scenario_9_student_cannot_access_admin_dashboard`: RBAC forbidden verification (403).
9. `test_scenario_10_teacher_cannot_modify_other_teachers_class`: Class authority check.
10. `test_scenario_11_admin_exports_reports`: Excel and PDF streaming export generation.
11. `test_scenario_12_unconfirmed_finalized_as_absent`: Session closure finalizes unconfirmed students as `ABSENT`.
12. `test_scenario_13_manual_correction_creates_audit_log`: Manual adjustments record immutable audit logs.

---

## 6. Database Schema Overview

```
users (id, email, hashed_password, full_name, role, phone, avatar_url, is_active, created_at)
  ├── teachers (id, user_id, employee_id, department, designation)
  ├── students (id, user_id, roll_number, batch_id, parent_id)
  └── parents (id, user_id, relationship_type, emergency_contact)

batches (id, name, code, department, academic_year, is_active)
subjects (id, name, code, department, credits, semester, is_active)
student_enrollments (id, student_id, batch_id, subject_id, enrolled_at)
teacher_assignments (id, teacher_id, subject_id, batch_id, assigned_at)

class_sessions (id, teacher_id, subject_id, batch_id, title, session_date, start_time,
                duration_minutes, room_number, status, attendance_pin, current_qr_token,
                qr_token_expires_at, late_threshold_minutes, require_gps)

attendance_records (id, class_session_id, student_id,
                    student_confirmation, student_confirmed_at, student_lat, student_lng,
                    teacher_confirmation, teacher_confirmed_at, confirmed_by_teacher_id,
                    status, rejection_reason, is_manual_correction, manual_correction_reason)
  * UniqueConstraint: (class_session_id, student_id)

attendance_tokens (id, class_session_id, token, expires_at, created_at)
leave_requests (id, student_id, start_date, end_date, reason, status, review_notes)
attendance_disputes (id, attendance_record_id, student_id, reason, requested_status, status)
timetable (id, batch_id, subject_id, teacher_id, day_of_week, start_time, end_time, room_number)
notifications (id, user_id, title, message, type, is_read, link_url)
audit_logs (id, user_id, user_email, action, entity_type, entity_id, details, created_at)
system_settings (id, min_attendance_threshold, default_late_threshold_minutes, gps_verification_enabled)
```


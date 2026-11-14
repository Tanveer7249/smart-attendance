import io
from datetime import datetime, timedelta, timezone, date
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from app.models.models import (
    User, Student, Teacher, Batch, Subject, ClassSession,
    AttendanceRecord, AttendanceStatus, SessionStatus,
    TeacherStudentAssignment, SystemSettings
)

class AnalyticsService:

    @staticmethod
    def get_admin_dashboard_stats(db: Session) -> Dict[str, Any]:
        today_str = date.today().isoformat()

        total_students = db.query(Student).count()
        total_teachers = db.query(Teacher).count()
        total_batches = db.query(Batch).count()
        total_subjects = db.query(Subject).count()

        today_sessions = db.query(ClassSession).filter(ClassSession.session_date == today_str).all()
        classes_conducted_today = len(today_sessions)
        today_session_ids = [s.id for s in today_sessions]

        present_students_today = 0
        absent_students_today = 0
        late_students_today = 0

        if today_session_ids:
            present_students_today = db.query(AttendanceRecord).filter(
                AttendanceRecord.class_session_id.in_(today_session_ids),
                AttendanceRecord.status == AttendanceStatus.PRESENT
            ).count()

            absent_students_today = db.query(AttendanceRecord).filter(
                AttendanceRecord.class_session_id.in_(today_session_ids),
                AttendanceRecord.status == AttendanceStatus.ABSENT
            ).count()

            late_students_today = db.query(AttendanceRecord).filter(
                AttendanceRecord.class_session_id.in_(today_session_ids),
                AttendanceRecord.status == AttendanceStatus.LATE
            ).count()

        total_records = db.query(AttendanceRecord).filter(
            AttendanceRecord.status.in_([AttendanceStatus.PRESENT, AttendanceStatus.LATE, AttendanceStatus.ABSENT])
        ).count()
        
        positive_records = db.query(AttendanceRecord).filter(
            AttendanceRecord.status.in_([AttendanceStatus.PRESENT, AttendanceStatus.LATE])
        ).count()

        average_attendance_percentage = round((positive_records / total_records * 100.0), 1) if total_records > 0 else 0.0

        settings = db.query(SystemSettings).first()
        threshold = settings.min_attendance_threshold if settings else 75.0

        all_students = db.query(Student).all()
        at_risk_list = []

        for st in all_students:
            st_records = db.query(AttendanceRecord).filter(
                AttendanceRecord.student_id == st.id,
                AttendanceRecord.status.in_([AttendanceStatus.PRESENT, AttendanceStatus.LATE, AttendanceStatus.ABSENT])
            ).all()

            if len(st_records) >= 1:
                pos = sum(1 for r in st_records if r.status in [AttendanceStatus.PRESENT, AttendanceStatus.LATE])
                pct = round((pos / len(st_records)) * 100.0, 1)
                if pct < threshold:
                    at_risk_list.append({
                        "student_id": st.id,
                        "name": st.user.full_name,
                        "roll_number": st.roll_number,
                        "batch_name": st.batch.name if st.batch else "General",
                        "total_classes": len(st_records),
                        "attended_classes": pos,
                        "percentage": pct
                    })

        at_risk_list.sort(key=lambda x: x["percentage"])

        weekly_trends = []
        for i in range(6, -1, -1):
            d = (date.today() - timedelta(days=i)).isoformat()
            day_name = (date.today() - timedelta(days=i)).strftime("%a")
            d_sessions = db.query(ClassSession).filter(ClassSession.session_date == d).all()
            d_session_ids = [s.id for s in d_sessions]

            p_count = 0
            a_count = 0
            l_count = 0

            if d_session_ids:
                p_count = db.query(AttendanceRecord).filter(
                    AttendanceRecord.class_session_id.in_(d_session_ids),
                    AttendanceRecord.status == AttendanceStatus.PRESENT
                ).count()
                a_count = db.query(AttendanceRecord).filter(
                    AttendanceRecord.class_session_id.in_(d_session_ids),
                    AttendanceRecord.status == AttendanceStatus.ABSENT
                ).count()
                l_count = db.query(AttendanceRecord).filter(
                    AttendanceRecord.class_session_id.in_(d_session_ids),
                    AttendanceRecord.status == AttendanceStatus.LATE
                ).count()

            weekly_trends.append({
                "date": d,
                "day": day_name,
                "present": p_count,
                "absent": a_count,
                "late": l_count
            })

        monthly_trends = [
            {"month": "Cur", "attendance_rate": average_attendance_percentage}
        ]

        active_sessions = db.query(ClassSession).filter(ClassSession.status == SessionStatus.ACTIVE).all()

        return {
            "total_students": total_students,
            "total_teachers": total_teachers,
            "total_batches": total_batches,
            "total_subjects": total_subjects,
            "classes_conducted_today": classes_conducted_today,
            "present_students_today": present_students_today,
            "absent_students_today": absent_students_today,
            "late_students_today": late_students_today,
            "average_attendance_percentage": average_attendance_percentage,
            "students_below_threshold": len(at_risk_list),
            "threshold_percentage": threshold,
            "at_risk_students": at_risk_list,
            "weekly_trends": weekly_trends,
            "monthly_trends": monthly_trends,
            "active_sessions_count": len(active_sessions)
        }

    @staticmethod
    def get_student_analytics(db: Session, student_id: int) -> Dict[str, Any]:
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return {}

        settings = db.query(SystemSettings).first()
        threshold = settings.min_attendance_threshold if settings else 75.0

        records = db.query(AttendanceRecord).filter(
            AttendanceRecord.student_id == student_id,
            AttendanceRecord.status.in_([AttendanceStatus.PRESENT, AttendanceStatus.LATE, AttendanceStatus.ABSENT, AttendanceStatus.ON_LEAVE])
        ).all()

        total_classes = len(records)
        present_count = sum(1 for r in records if r.status == AttendanceStatus.PRESENT)
        late_count = sum(1 for r in records if r.status == AttendanceStatus.LATE)
        absent_count = sum(1 for r in records if r.status == AttendanceStatus.ABSENT)
        leave_count = sum(1 for r in records if r.status == AttendanceStatus.ON_LEAVE)

        effective_attended = present_count + late_count
        overall_percentage = round((effective_attended / total_classes * 100.0), 1) if total_classes > 0 else 0.0

        # Assigned teachers
        assignments = db.query(TeacherStudentAssignment).filter(
            TeacherStudentAssignment.student_id == student_id
        ).all()
        assigned_teachers = [a.teacher.user.full_name for a in assignments if a.teacher and a.teacher.user]

        # Subject breakdown
        subject_ids = list(set([r.class_session.subject_id for r in records if r.class_session]))
        subject_breakdown = []
        for sid in subject_ids:
            subj = db.query(Subject).filter(Subject.id == sid).first()
            if not subj:
                continue
            s_records = [r for r in records if r.class_session and r.class_session.subject_id == sid]
            s_total = len(s_records)
            s_pres = sum(1 for r in s_records if r.status == AttendanceStatus.PRESENT)
            s_late = sum(1 for r in s_records if r.status == AttendanceStatus.LATE)
            s_abs = sum(1 for r in s_records if r.status == AttendanceStatus.ABSENT)
            s_pct = round(((s_pres + s_late) / s_total * 100.0), 1) if s_total > 0 else 0.0

            subject_breakdown.append({
                "subject_id": subj.id,
                "subject_name": subj.name,
                "subject_code": subj.code,
                "total_classes": s_total,
                "attended_classes": s_pres + s_late,
                "late_classes": s_late,
                "absent_classes": s_abs,
                "percentage": s_pct,
                "is_at_risk": s_pct < threshold
            })

        return {
            "student_id": student.id,
            "student_name": student.user.full_name,
            "roll_number": student.roll_number,
            "batch_name": student.batch.name if student.batch else "General",
            "assigned_teachers": assigned_teachers,
            "total_classes": total_classes,
            "present_count": present_count,
            "late_count": late_count,
            "absent_count": absent_count,
            "leave_count": leave_count,
            "overall_percentage": overall_percentage,
            "is_at_risk": overall_percentage < threshold and total_classes > 0,
            "subject_breakdown": subject_breakdown
        }

    @staticmethod
    def export_attendance_excel(db: Session, batch_id: Optional[int] = None, subject_id: Optional[int] = None) -> io.BytesIO:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Attendance Report"

        title_font = Font(name="Segoe UI", size=16, bold=True, color="FFFFFF")
        header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        regular_font = Font(name="Segoe UI", size=10)
        
        navy_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        header_fill = PatternFill(start_color="4F46E5", end_color="4F46E5", fill_type="solid")

        present_fill = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")
        absent_fill = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
        late_fill = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")

        thin_border = Border(
            left=Side(style='thin', color='E2E8F0'),
            right=Side(style='thin', color='E2E8F0'),
            top=Side(style='thin', color='E2E8F0'),
            bottom=Side(style='thin', color='E2E8F0')
        )

        ws.merge_cells("A1:I1")
        title_cell = ws["A1"]
        title_cell.value = "Smart Attendance Management System - Official Report"
        title_cell.font = title_font
        title_cell.fill = navy_fill
        title_cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 40

        ws.merge_cells("A2:I2")
        sub_cell = ws["A2"]
        sub_cell.value = f"Generated on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')} | Strict Dual-Confirmation Records"
        sub_cell.font = Font(name="Segoe UI", size=9, italic=True, color="64748B")
        sub_cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[2].height = 20

        headers = [
            "Record ID", "Date", "Subject", "Batch", "Student Roll",
            "Student Name", "Student Confirmed", "Teacher Confirmed", "Final Status"
        ]
        
        ws.append([])
        ws.append(headers)
        ws.row_dimensions[4].height = 28

        for col_num in range(1, len(headers) + 1):
            cell = ws.cell(row=4, column=col_num)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")

        query = db.query(AttendanceRecord).join(ClassSession)
        if batch_id:
            query = query.filter(ClassSession.batch_id == batch_id)
        if subject_id:
            query = query.filter(ClassSession.subject_id == subject_id)

        records = query.order_by(ClassSession.session_date.desc(), AttendanceRecord.id.desc()).all()

        current_row = 5
        for r in records:
            status_val = r.status.value
            row_data = [
                r.id,
                r.class_session.session_date if r.class_session else "-",
                r.class_session.subject.name if r.class_session and r.class_session.subject else "-",
                r.class_session.batch.name if r.class_session and r.class_session.batch else "-",
                r.student.roll_number if r.student else "-",
                r.student.user.full_name if r.student and r.student.user else "-",
                "YES" if r.student_confirmation else "NO",
                "YES" if r.teacher_confirmation else "NO",
                status_val
            ]
            ws.append(row_data)
            ws.row_dimensions[current_row].height = 22

            for c_idx in range(1, len(row_data) + 1):
                cell = ws.cell(row=current_row, column=c_idx)
                cell.font = regular_font
                cell.border = thin_border
                cell.alignment = Alignment(horizontal="center", vertical="center")

                if c_idx == 9:
                    if status_val == "PRESENT":
                        cell.fill = present_fill
                    elif status_val == "ABSENT":
                        cell.fill = absent_fill
                    elif status_val == "LATE":
                        cell.fill = late_fill

            current_row += 1

        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = openpyxl.utils.get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output

    @staticmethod
    def export_attendance_pdf(db: Session, batch_id: Optional[int] = None, subject_id: Optional[int] = None) -> io.BytesIO:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(letter),
            rightMargin=30,
            leftMargin=30,
            topMargin=30,
            bottomMargin=30
        )

        elements = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            'ReportTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#0F172A'),
            spaceAfter=6,
            alignment=1
        )
        sub_style = ParagraphStyle(
            'ReportSub',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#64748B'),
            spaceAfter=15,
            alignment=1
        )

        elements.append(Paragraph("Smart Attendance Management System", title_style))
        elements.append(Paragraph(f"Official Verified Attendance Report | Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", sub_style))

        query = db.query(AttendanceRecord).join(ClassSession)
        if batch_id:
            query = query.filter(ClassSession.batch_id == batch_id)
        if subject_id:
            query = query.filter(ClassSession.subject_id == subject_id)

        records = query.order_by(ClassSession.session_date.desc(), AttendanceRecord.id.desc()).limit(150).all()

        data = [["Date", "Subject", "Batch", "Roll No", "Student Name", "Student Conf.", "Teacher Conf.", "Status"]]

        for r in records:
            data.append([
                r.class_session.session_date if r.class_session else "-",
                r.class_session.subject.code if r.class_session and r.class_session.subject else "-",
                r.class_session.batch.code if r.class_session and r.class_session.batch else "-",
                r.student.roll_number if r.student else "-",
                (r.student.user.full_name[:18] + '..') if (r.student and r.student.user and len(r.student.user.full_name) > 18) else (r.student.user.full_name if r.student and r.student.user else "-"),
                "YES" if r.student_confirmation else "NO",
                "YES" if r.teacher_confirmation else "NO",
                r.status.value
            ])

        t = Table(data, colWidths=[70, 75, 75, 70, 150, 75, 75, 80])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4F46E5')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('TOPPADDING', (0, 0), (-1, 0), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')])
        ]))

        elements.append(t)
        doc.build(elements)
        buffer.seek(0)
        return buffer

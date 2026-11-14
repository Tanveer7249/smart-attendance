from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_password_hash
from app.models.models import User, UserRole, Teacher, Student, Batch, TeacherStudentAssignment, AuditLog
from app.schemas.schemas import (
    UserCreate, UserUpdate, UserResponse,
    TeacherStudentAssignmentCreate, TeacherStudentAssignmentResponse
)
from app.api.deps import get_current_user, require_role
from app.api.routes.auth import format_user_response

router = APIRouter(prefix="/users", tags=["Users & Staff Management"])

@router.get("", response_model=List[UserResponse])
def get_users(
    role: Optional[UserRole] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN]))
):
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    users = query.order_by(User.id.desc()).all()
    return [format_user_response(u) for u in users]

@router.post("", response_model=UserResponse)
def create_user_account(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN]))
):
    """
    Administrator provisions Teacher or Student account with credentials.
    Admin can then give the email and password to the teacher or student to login.
    """
    existing = db.query(User).filter(User.email == user_in.email.strip().lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists")

    new_user = User(
        email=user_in.email.strip().lower(),
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        role=user_in.role,
        phone=user_in.phone,
        avatar_url=user_in.avatar_url,
        is_active=user_in.is_active
    )
    db.add(new_user)
    db.flush()

    if user_in.role == UserRole.TEACHER:
        emp_id = user_in.employee_id or f"EMP-{new_user.id:04d}"
        teacher = Teacher(
            user_id=new_user.id,
            employee_id=emp_id,
            department=user_in.department or "General Department",
            designation=user_in.designation or "Lecturer"
        )
        db.add(teacher)

    elif user_in.role == UserRole.STUDENT:
        student = Student(
            user_id=new_user.id,
            roll_number=user_in.roll_number or None,
            batch_id=user_in.batch_id
        )
        db.add(student)
        db.flush()

        # If admin specified a teacher to assign to immediately
        if user_in.assigned_teacher_id:
            assignment = TeacherStudentAssignment(
                teacher_id=user_in.assigned_teacher_id,
                student_id=student.id
            )
            db.add(assignment)

    audit = AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        action="USER_CREATED",
        entity_type="User",
        entity_id=new_user.id,
        details=f"Admin created {user_in.role.value} account for {user_in.full_name} ({user_in.email})"
    )
    db.add(audit)
    db.commit()
    db.refresh(new_user)

    return format_user_response(new_user)

@router.post("/assign-students", response_model=List[TeacherStudentAssignmentResponse])
def assign_students_to_teacher(
    data: TeacherStudentAssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN]))
):
    """
    Admin explicitly assigns one or multiple students to a specific Teacher.
    """
    teacher = db.query(Teacher).filter(Teacher.id == data.teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    created_assignments = []
    for s_id in data.student_ids:
        existing = db.query(TeacherStudentAssignment).filter(
            TeacherStudentAssignment.teacher_id == data.teacher_id,
            TeacherStudentAssignment.student_id == s_id,
            TeacherStudentAssignment.subject_id == data.subject_id
        ).first()

        if not existing:
            assignment = TeacherStudentAssignment(
                teacher_id=data.teacher_id,
                student_id=s_id,
                subject_id=data.subject_id
            )
            db.add(assignment)
            created_assignments.append(assignment)

    audit = AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        action="STUDENTS_ASSIGNED_TO_TEACHER",
        entity_type="Teacher",
        entity_id=teacher.id,
        details=f"Admin assigned {len(data.student_ids)} students to {teacher.user.full_name}"
    )
    db.add(audit)
    db.commit()

    all_assignments = db.query(TeacherStudentAssignment).filter(
        TeacherStudentAssignment.teacher_id == data.teacher_id
    ).all()

    results = []
    for a in all_assignments:
        results.append(TeacherStudentAssignmentResponse(
            id=a.id,
            teacher_id=a.teacher_id,
            teacher_name=a.teacher.user.full_name if a.teacher and a.teacher.user else None,
            student_id=a.student_id,
            student_name=a.student.user.full_name if a.student and a.student.user else None,
            student_roll=a.student.roll_number if a.student else None,
            subject_id=a.subject_id,
            subject_name=a.subject.name if a.subject else None,
            assigned_at=a.assigned_at
        ))
    return results

@router.delete("/assignments/{assignment_id}")
def remove_student_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN]))
):
    a = db.query(TeacherStudentAssignment).filter(TeacherStudentAssignment.id == assignment_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Assignment not found")
    db.delete(a)
    db.commit()
    return {"message": "Student unassigned from teacher successfully"}

@router.get("/assignments", response_model=List[TeacherStudentAssignmentResponse])
def get_all_assignments(
    teacher_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(TeacherStudentAssignment)
    if teacher_id:
        query = query.filter(TeacherStudentAssignment.teacher_id == teacher_id)
    assignments = query.all()

    results = []
    for a in assignments:
        results.append(TeacherStudentAssignmentResponse(
            id=a.id,
            teacher_id=a.teacher_id,
            teacher_name=a.teacher.user.full_name if a.teacher and a.teacher.user else None,
            student_id=a.student_id,
            student_name=a.student.user.full_name if a.student and a.student.user else None,
            student_roll=a.student.roll_number if a.student else None,
            subject_id=a.subject_id,
            subject_name=a.subject.name if a.subject else None,
            assigned_at=a.assigned_at
        ))
    return results

@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN]))
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own administrator account")
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    target.is_active = False
    db.commit()
    return {"message": "Account deactivated"}

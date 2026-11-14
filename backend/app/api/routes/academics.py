from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import (
    Batch, Subject, Student, Teacher, User, UserRole,
    TeacherCourseAssignment, AuditLog
)
from app.schemas.schemas import (
    BatchCreate, BatchResponse, SubjectCreate, SubjectResponse,
    TeacherCourseAssignmentCreate, TeacherCourseAssignmentResponse
)
from app.api.deps import get_current_user, require_role

router = APIRouter(prefix="/academics", tags=["Curriculum Management"])

# Batches
@router.get("/batches", response_model=List[BatchResponse])
def get_batches(db: Session = Depends(get_db)):
    batches = db.query(Batch).filter(Batch.is_active == True).all()
    results = []
    for b in batches:
        results.append(BatchResponse(
            id=b.id,
            name=b.name,
            code=b.code,
            department=b.department,
            academic_year=b.academic_year,
            is_active=b.is_active,
            student_count=len(b.students),
            created_at=b.created_at
        ))
    return results

@router.post("/batches", response_model=BatchResponse)
def create_batch(
    data: BatchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN]))
):
    batch = Batch(**data.model_dump())
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return BatchResponse(
        id=batch.id,
        name=batch.name,
        code=batch.code,
        department=batch.department,
        academic_year=batch.academic_year,
        is_active=batch.is_active,
        student_count=0,
        created_at=batch.created_at
    )

# Courses / Subjects
@router.get("/subjects", response_model=List[SubjectResponse])
def get_subjects(
    teacher_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Get courses/subjects. If teacher_id is provided, returns subjects assigned to that teacher.
    If teacher has no specific course assignments, returns all active courses.
    """
    if teacher_id:
        assigned = db.query(Subject).join(TeacherCourseAssignment).filter(
            TeacherCourseAssignment.teacher_id == teacher_id,
            Subject.is_active == True
        ).all()
        if assigned:
            return assigned

    return db.query(Subject).filter(Subject.is_active == True).all()

@router.post("/subjects", response_model=SubjectResponse)
def create_subject(
    data: SubjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN]))
):
    existing = db.query(Subject).filter(Subject.code == data.code.strip()).first()
    if existing:
        raise HTTPException(status_code=400, detail="A course with this code already exists")

    subject = Subject(**data.model_dump())
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return subject

# Teacher-Course Assignments
@router.post("/assign-teacher-courses", response_model=List[TeacherCourseAssignmentResponse])
def assign_courses_to_teacher(
    data: TeacherCourseAssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN]))
):
    teacher = db.query(Teacher).filter(Teacher.id == data.teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    created = []
    for s_id in data.subject_ids:
        subject = db.query(Subject).filter(Subject.id == s_id).first()
        if not subject:
            continue

        existing = db.query(TeacherCourseAssignment).filter(
            TeacherCourseAssignment.teacher_id == data.teacher_id,
            TeacherCourseAssignment.subject_id == s_id
        ).first()

        if not existing:
            assignment = TeacherCourseAssignment(
                teacher_id=data.teacher_id,
                subject_id=s_id
            )
            db.add(assignment)
            created.append(assignment)

    db.commit()

    all_assignments = db.query(TeacherCourseAssignment).filter(
        TeacherCourseAssignment.teacher_id == data.teacher_id
    ).all()

    return [
        TeacherCourseAssignmentResponse(
            id=a.id,
            teacher_id=a.teacher_id,
            teacher_name=a.teacher.user.full_name if a.teacher and a.teacher.user else None,
            subject_id=a.subject_id,
            subject_name=a.subject.name if a.subject else None,
            subject_code=a.subject.code if a.subject else None,
            assigned_at=a.assigned_at
        )
        for a in all_assignments
    ]

@router.get("/teacher-courses", response_model=List[TeacherCourseAssignmentResponse])
def get_teacher_course_assignments(
    teacher_id: Optional[int] = None,
    subject_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    query = db.query(TeacherCourseAssignment)
    if teacher_id:
        query = query.filter(TeacherCourseAssignment.teacher_id == teacher_id)
    if subject_id:
        query = query.filter(TeacherCourseAssignment.subject_id == subject_id)

    assignments = query.all()
    return [
        TeacherCourseAssignmentResponse(
            id=a.id,
            teacher_id=a.teacher_id,
            teacher_name=a.teacher.user.full_name if a.teacher and a.teacher.user else None,
            subject_id=a.subject_id,
            subject_name=a.subject.name if a.subject else None,
            subject_code=a.subject.code if a.subject else None,
            assigned_at=a.assigned_at
        )
        for a in assignments
    ]

@router.delete("/teacher-courses/{assignment_id}")
def remove_teacher_course_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN]))
):
    a = db.query(TeacherCourseAssignment).filter(TeacherCourseAssignment.id == assignment_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Course assignment not found")
    db.delete(a)
    db.commit()
    return {"message": "Teacher unassigned from course successfully"}

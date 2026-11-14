from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta

from app.core.database import get_db
from app.core.security import verify_password, create_access_token
from app.core.config import settings
from app.models.models import User, UserRole, Teacher, Student
from app.schemas.schemas import Token, LoginRequest, UserResponse, TeacherProfileResponse, StudentProfileResponse
from app.api.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])

def format_user_response(user: User) -> UserResponse:
    t_profile = None
    s_profile = None

    if user.teacher_profile:
        t_profile = TeacherProfileResponse(
            id=user.teacher_profile.id,
            employee_id=user.teacher_profile.employee_id,
            department=user.teacher_profile.department,
            designation=user.teacher_profile.designation,
            assigned_student_count=len(user.teacher_profile.student_assignments)
        )
    if user.student_profile:
        # Check assigned teachers
        assigned_teachers = [a.teacher.user.full_name for a in user.student_profile.teacher_assignments if a.teacher and a.teacher.user]
        s_profile = StudentProfileResponse(
            id=user.student_profile.id,
            roll_number=user.student_profile.roll_number,
            batch_id=user.student_profile.batch_id,
            batch_name=user.student_profile.batch.name if user.student_profile.batch else None,
            assigned_teacher_name=", ".join(assigned_teachers) if assigned_teachers else "None Assigned"
        )

    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        phone=user.phone,
        avatar_url=user.avatar_url,
        is_active=user.is_active,
        created_at=user.created_at,
        teacher_profile=t_profile,
        student_profile=s_profile
    )

@router.post("/login", response_model=Token)
def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    # Ensure system admin exists in database
    try:
        from app.seed import ensure_admin_exists
        ensure_admin_exists(db)
    except Exception as e:
        print("ensure_admin_exists during login note:", e)

    user = db.query(User).filter(User.email == login_data.email.strip().lower()).first()
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account is deactivated")

    access_token = create_access_token(
        data={"sub": user.email, "role": user.role.value, "user_id": user.id}
    )
    return Token(
        access_token=access_token,
        token_type="bearer",
        user=format_user_response(user)
    )

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return format_user_response(current_user)

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import SystemSettings, User, UserRole, AuditLog
from app.schemas.schemas import SystemSettingsResponse, SystemSettingsUpdate
from app.api.deps import require_role

router = APIRouter(prefix="/settings", tags=["System Settings"])

def get_or_create_settings(db: Session) -> SystemSettings:
    s = db.query(SystemSettings).first()
    if not s:
        s = SystemSettings(
            min_attendance_threshold=75.0,
            default_late_threshold_minutes=15,
            default_qr_refresh_seconds=15,
            allow_pin_fallback=True,
            gps_verification_enabled=False,
            campus_latitude=37.7749,
            campus_longitude=-122.4194,
            campus_radius_meters=200.0
        )
        db.add(s)
        db.commit()
        db.refresh(s)
    return s

@router.get("", response_model=SystemSettingsResponse)
def get_settings(db: Session = Depends(get_db)):
    return get_or_create_settings(db)

@router.put("", response_model=SystemSettingsResponse)
def update_settings(
    update_data: SystemSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN]))
):
    s = get_or_create_settings(db)
    for field, val in update_data.model_dump(exclude_unset=True).items():
        setattr(s, field, val)

    audit = AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        action="SETTINGS_UPDATED",
        entity_type="SystemSettings",
        entity_id=s.id,
        details=f"Admin updated system settings: {update_data.model_dump(exclude_unset=True)}"
    )
    db.add(audit)
    db.commit()
    db.refresh(s)
    return s


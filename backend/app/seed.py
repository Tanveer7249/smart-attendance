from datetime import datetime, timezone
import os
from sqlalchemy.orm import Session
from app.core.database import SessionLocal, engine, Base
from app.core.security import get_password_hash
from app.models.models import (
    User, UserRole, SystemSettings, AuditLog
)

def reset_and_seed():
    """
    Cleans database and initializes:
    1. System Settings
    2. Master Administrator account (admin@smartattendance.edu / Admin@123)
    Zero predefined courses (Admin creates courses fresh).
    Zero fake/demo users.
    """
    print("Re-creating clean database tables...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db: Session = SessionLocal()

    try:
        # 1. System Settings
        settings = SystemSettings(
            min_attendance_threshold=75.0,
            default_late_threshold_minutes=15,
            default_qr_refresh_seconds=30,
            allow_pin_fallback=True,
            gps_verification_enabled=False
        )
        db.add(settings)

        # 2. Master System Administrator
        admin = User(
            email="admin@smartattendance.edu",
            hashed_password=get_password_hash("Admin@123"),
            full_name="System Administrator",
            role=UserRole.ADMIN,
            phone="+1 (555) 000-1000",
            avatar_url=None
        )
        db.add(admin)
        db.flush()

        # 3. System Initialized Audit Log
        audit = AuditLog(
            user_id=admin.id,
            user_email=admin.email,
            action="SYSTEM_INITIALIZED",
            entity_type="System",
            entity_id=1,
            details="System initialized in production mode. Administrator account ready for provisioning courses, faculty, and students."
        )
        db.add(audit)

        db.commit()
        print("\nClean production database initialized successfully!")
        print("Master Administrator:")
        print("  Email:    admin@smartattendance.edu")
        print("  Password: Admin@123")
        print("Role:       ADMIN (Creates Courses, Teachers, Students & manages Assignments)\n")

    except Exception as e:
        db.rollback()
        print(f"Error during clean initialization: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    reset_and_seed()

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

def ensure_admin_exists(db: Session = None):
    """
    Safely ensures SystemSettings and the Master Admin account exist,
    WITHOUT dropping any tables or deleting existing data.
    Safe for production serverless / Supabase startup.
    """
    # 1. Ensure all schema tables exist in the target database
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print("Schema create_all note:", e)

    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        # Check if settings exist
        if not db.query(SystemSettings).first():
            settings = SystemSettings(
                min_attendance_threshold=75.0,
                default_late_threshold_minutes=15,
                default_qr_refresh_seconds=30,
                allow_pin_fallback=True,
                gps_verification_enabled=False
            )
            db.add(settings)
            db.commit()

        # Check if admin user exists
        admin = db.query(User).filter(User.role == UserRole.ADMIN).first()
        if not admin:
            admin = User(
                email="admin@smartattendance.edu",
                hashed_password=get_password_hash("Admin@123"),
                full_name="System Administrator",
                role=UserRole.ADMIN,
                phone="+1 (555) 000-1000",
                avatar_url=None
            )
            db.add(admin)
            db.commit()
            print("Master Administrator created: admin@smartattendance.edu / Admin@123")
    except Exception as e:
        db.rollback()
        print(f"ensure_admin_exists note: {e}")
    finally:
        if close_db:
            db.close()

if __name__ == "__main__":
    reset_and_seed()

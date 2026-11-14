import os
import tempfile
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings

def get_fallback_db_url():
    temp_dir = tempfile.gettempdir()
    db_path = os.path.join(temp_dir, "smart_attendance.db").replace("\\", "/")
    return f"sqlite:///{db_path}"

db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

engine = None
active_db_type = "sqlite"

if db_url.startswith("sqlite"):
    if os.getenv("VERCEL") or not os.access(".", os.W_OK):
        db_url = get_fallback_db_url()
    connect_args = {"check_same_thread": False}
    engine = create_engine(db_url, connect_args=connect_args, echo=False)
    active_db_type = "sqlite"
else:
    # Try PostgreSQL / Supabase
    if "pooler.supabase.com:6543" in db_url:
        db_url = db_url.replace(":6543", ":5432")

    connect_args = {}
    if "supabase" in db_url:
        connect_args["sslmode"] = "require"

    try:
        candidate_engine = create_engine(
            db_url,
            connect_args=connect_args,
            pool_pre_ping=True,
            pool_recycle=300,
            echo=False
        )
        # Test connection with a quick ping
        with candidate_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine = candidate_engine
        active_db_type = "postgresql"
    except Exception as e:
        print(f"PostgreSQL connection note: {e}. Gracefully activating local database.")
        fallback_url = get_fallback_db_url()
        engine = create_engine(fallback_url, connect_args={"check_same_thread": False}, echo=False)
        active_db_type = "sqlite_fallback"

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

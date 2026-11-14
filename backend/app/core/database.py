from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings

db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

if db_url.startswith("sqlite"):
    # On serverless (Vercel / AWS Lambda), root directory is read-only.
    if os.getenv("VERCEL") or not os.access(".", os.W_OK):
        db_url = "sqlite:////tmp/smart_attendance.db"

    connect_args = {"check_same_thread": False}
    engine = create_engine(
        db_url,
        connect_args=connect_args,
        echo=False
    )
else:
    # If Supabase transaction pooler port 6543 is used, use session pooler port 5432 for full SQLAlchemy compatibility
    if "pooler.supabase.com:6543" in db_url:
        db_url = db_url.replace(":6543", ":5432")

    connect_args = {}
    if "supabase" in db_url:
        connect_args["sslmode"] = "require"

    # PostgreSQL / Supabase connection with automatic reconnection and pooling
    engine = create_engine(
        db_url,
        connect_args=connect_args,
        pool_pre_ping=True,
        pool_recycle=300,
        echo=False
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


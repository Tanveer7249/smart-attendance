import os
import tempfile
import urllib.parse
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings

def sanitize_db_url(url_str: str) -> str:
    if not url_str:
        return url_str
    url_str = url_str.strip()
    if url_str.startswith("postgres://"):
        url_str = "postgresql://" + url_str[len("postgres://"):]
    if not url_str.startswith("postgresql://"):
        return url_str
    try:
        scheme_and_auth, host_and_path = url_str.rsplit("@", 1)
        scheme, auth = scheme_and_auth.split("://", 1)
        if ":" in auth:
            user, password = auth.split(":", 1)
            raw_pass = urllib.parse.unquote(password)
            safe_pass = urllib.parse.quote_plus(raw_pass)
            return f"{scheme}://{user}:{safe_pass}@{host_and_path}"
    except Exception:
        pass
    return url_str

def mask_db_url(url_str: str) -> str:
    if not url_str:
        return "None"
    try:
        if "@" in url_str:
            scheme_and_auth, host_part = url_str.rsplit("@", 1)
            scheme, auth = scheme_and_auth.split("://", 1)
            if ":" in auth:
                user, _ = auth.split(":", 1)
                return f"{scheme}://{user}:****@{host_part}"
            return f"{scheme}://****@{host_part}"
    except Exception:
        pass
    return "sqlite" if "sqlite" in url_str else "masked"

def get_fallback_db_url():
    temp_dir = tempfile.gettempdir()
    db_path = os.path.join(temp_dir, "smart_attendance.db").replace("\\", "/")
    return f"sqlite:///{db_path}"

raw_db_url = settings.DATABASE_URL
sanitized_db_url = sanitize_db_url(raw_db_url)
configured_db_url_masked = mask_db_url(sanitized_db_url)

engine = None
active_db_type = "sqlite"
postgres_connection_error = None

if not sanitized_db_url or sanitized_db_url.startswith("sqlite"):
    sqlite_url = sanitized_db_url or get_fallback_db_url()
    if os.getenv("VERCEL") or not os.access(".", os.W_OK):
        sqlite_url = get_fallback_db_url()
    connect_args = {"check_same_thread": False}
    engine = create_engine(sqlite_url, connect_args=connect_args, echo=False)
    active_db_type = "sqlite"
else:
    # Try connecting to PostgreSQL / Supabase
    candidates = [sanitized_db_url]

    # If Supabase pooler is used, generate alternate candidate (6543 <-> 5432)
    if "pooler.supabase.com" in sanitized_db_url:
        if ":6543" in sanitized_db_url:
            candidates.append(sanitized_db_url.replace(":6543", ":5432"))
        elif ":5432" in sanitized_db_url:
            candidates.append(sanitized_db_url.replace(":5432", ":6543"))

    connected = False
    last_err = None

    for target_url in candidates:
        connect_args = {"connect_timeout": 7}
        if "supabase" in target_url or "sslmode" not in target_url:
            connect_args["sslmode"] = "require"

        try:
            candidate_engine = create_engine(
                target_url,
                connect_args=connect_args,
                pool_pre_ping=True,
                pool_recycle=300,
                echo=False
            )
            with candidate_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            engine = candidate_engine
            active_db_type = "postgresql"
            postgres_connection_error = None
            connected = True
            break
        except Exception as e:
            last_err = e
            continue

    if not connected:
        postgres_connection_error = str(last_err)
        print(f"PostgreSQL connection note: {last_err}. Gracefully activating local database.")
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

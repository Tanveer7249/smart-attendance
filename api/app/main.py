import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.database import Base, engine
from app.models import models
from app.websockets.manager import ws_manager

from app.api.routes import (
    auth, users, academics, classes, attendance,
    analytics, leaves, disputes, notifications,
    audit_logs, settings as app_settings
)

# Initialize database schema safely
def init_db():
    try:
        Base.metadata.create_all(bind=engine)
        from app.seed import ensure_admin_exists
        ensure_admin_exists()
    except Exception as e:
        print("Database schema init warning:", e)

init_db()

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc"
)

# CORS config
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes (both with and without /api prefix for serverless compatibility)
routers_list = [auth, users, academics, classes, attendance, analytics, leaves, disputes, notifications, audit_logs, app_settings]
for r in routers_list:
    app.include_router(r.router, prefix=settings.API_V1_STR)
    app.include_router(r.router, prefix="")

# Real-time live attendance WebSocket route
@app.websocket("/ws/attendance/{session_id}")
async def attendance_live_ws(websocket: WebSocket, session_id: int):
    await ws_manager.connect(session_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(session_id, websocket)

@app.get("/api/health")
@app.get("/health")
def health_check():
    db_status = "connected"
    db_err = None
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        db_status = "error"
        db_err = str(e)

    return {
        "status": "healthy" if db_status == "connected" else "database_error",
        "database": db_status,
        "database_error": db_err,
        "system": settings.PROJECT_NAME,
        "dual_confirmation_engine": "ACTIVE"
    }

# Mount static frontend production build if available
frontend_dist = os.getenv(
    "FRONTEND_DIST_DIR",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))
)
if os.path.exists(frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        file_path = os.path.join(frontend_dist, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(frontend_dist, "index.html"))

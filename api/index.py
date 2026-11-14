import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
backend_dir = os.path.join(root_dir, "backend")

# Ensure both local api/ directory and backend/ directory are on python path
for p in [current_dir, backend_dir]:
    if os.path.exists(p) and p not in sys.path:
        sys.path.insert(0, p)

try:
    from app.main import app
except Exception as e:
    import traceback
    tb = traceback.format_exc()
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    app = FastAPI()

    @app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE"])
    def error_handler(full_path: str):
        return JSONResponse(
            status_code=500,
            content={
                "error": "Serverless Function Startup Error",
                "detail": str(e),
                "traceback": tb
            }
        )



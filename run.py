import os
import sys
import subprocess
import uvicorn

def main():
    print("=" * 70)
    print("🚀 SMART ATTENDANCE MANAGEMENT SYSTEM")
    print("   Zero-Trust Dual-Confirmation Engine (Student + Teacher)")
    print("=" * 70)

    # 1. Ensure backend is in python path
    backend_dir = os.path.join(os.path.dirname(__file__), "backend")
    sys.path.insert(0, backend_dir)

    # 2. Run seed script to ensure sample data is populated
    print("\n[1/2] Verifying database schema & seed data...")
    try:
        from app.seed import seed
        seed()
    except Exception as e:
        print(f"Seed note: {e}")

    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")

    print("\n[2/2] Launching Full-Stack Application Server...")
    print(f"  👉 Web Application: http://{host}:{port}")
    print(f"  👉 API Documentation: http://{host}:{port}/api/docs")
    print(f"  👉 WebSocket Endpoint: ws://{host}:{port}/ws/attendance/{{session_id}}")
    print("\nInitial Admin Account:")
    print("  • Admin: admin@smartattendance.edu / Admin@123")
    print("  • Teacher accounts: Created by Admin")
    print("  • Student accounts: Created by Admin")
    print("=" * 70)

    from app.main import app
    uvicorn.run(app, host=host, port=port, log_level="info")

if __name__ == "__main__":
    main()


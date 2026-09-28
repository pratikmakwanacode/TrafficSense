import sys
import os
import subprocess
import time

def main():
    print("=" * 60)
    print("  Smart City Systems Launcher — Background Mode")
    print("=" * 60)

    # 1. Resolve paths
    project_dir = os.path.abspath("smart_city_project")
    backend_dir = os.path.join(project_dir, "backend")
    dashboard_dir = os.path.join(project_dir, "dashboard")
    edge_dir = os.path.join(project_dir, "edge_processor")
    
    # Ensure backend uploads dir exists
    os.makedirs(os.path.join(backend_dir, "uploads"), exist_ok=True)
    
    # Ensure backend is on python path
    sys.path.append(backend_dir)
    os.environ["PYTHONPATH"] = backend_dir

    # 2. Start FastAPI Server
    print("[SERVICE 1] Booting FastAPI Backend server on http://localhost:8000...")
    backend_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
        cwd=backend_dir
    )
    
    # Wait for backend to fully initialize
    time.sleep(4)

    # 3. Start React Operator Dashboard Dev Server (Vite) on port 3000
    print("[SERVICE 2] Booting React Dashboard Dev Server on http://localhost:3000...")
    dashboard_process = subprocess.Popen(
        ["node", "node_modules/vite/bin/vite.js", "--port", "3000", "--host"],
        cwd=dashboard_dir
    )
    time.sleep(2)

    # 4. Start YOLOv8 Edge Analyzer
    print("[SERVICE 3] Spawning YOLO Edge Analyzer...")
    edge_process = subprocess.Popen(
        [sys.executable, "processor.py"],
        cwd=edge_dir
    )

    print("\n" + "=" * 60)
    print("  ALL SERVICES RUNNING CONCURRENTLY!")
    print("  - React Operator Dashboard : http://localhost:3000")
    print("  - Unified Backend/Server   : http://localhost:8000")
    print("  - Embedded Citizen Portal   : http://localhost:8000/app")
    print("  - Live YOLOv8 Stream Feed  : http://localhost:8000/api/video/feed")
    print("=" * 60 + "\n")
    print("  Launcher monitoring processes...")

    try:
        while True:
            # Check if any process has exited
            if backend_process.poll() is not None:
                print("[WARNING] Backend server exited unexpectedly!")
                break
            if dashboard_process.poll() is not None:
                print("[WARNING] React Dev Server exited unexpectedly!")
                break
            if edge_process.poll() is not None:
                print("[WARNING] Edge Analyzer exited unexpectedly!")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Terminating system services...")
    finally:
        backend_process.terminate()
        dashboard_process.terminate()
        edge_process.terminate()
        try:
            backend_process.wait(timeout=3)
            dashboard_process.wait(timeout=3)
            edge_process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            backend_process.kill()
            dashboard_process.kill()
            edge_process.kill()
        print("[SHUTDOWN] All services terminated gracefully.")

if __name__ == "__main__":
    main()

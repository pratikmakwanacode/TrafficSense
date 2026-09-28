import sys
import os
import subprocess
import time

def main():
    print("=" * 60)
    print("  Smart City Traffic & Emission Reduction System Launcher")
    print("=" * 60)

    # 1. Resolve paths
    project_dir = os.path.abspath("smart_city_project")
    backend_dir = os.path.join(project_dir, "backend")
    edge_dir = os.path.join(project_dir, "edge_processor")
    
    # Ensure backend is on python path
    sys.path.append(backend_dir)
    os.environ["PYTHONPATH"] = backend_dir

    # 2. Start FastAPI Server in a separate background subprocess
    # This allows it to boot up so the Edge Processor can authenticate against it!
    print("[SERVICE 1] Booting FastAPI Backend server on http://localhost:8000...")
    backend_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
        cwd=backend_dir
    )
    
    # Wait for backend to fully initialize
    time.sleep(5)

    # 3. Start YOLOv8 Edge Analyzer
    print("[SERVICE 2] Spawning YOLO Edge Analyzer...")
    edge_process = subprocess.Popen(
        [sys.executable, "processor.py"],
        cwd=edge_dir
    )

    print("\n" + "=" * 60)
    print("  ALL SERVICES RUNNING ON PORT 8000!")
    print("  - Unified Master Control Dashboard: http://localhost:8000")
    print("  - Embedded Citizen Portal         : http://localhost:8000/app")
    print("  - Live YOLOv8 Stream Feed         : http://localhost:8000/api/video/feed")
    print("  - API Documentation (Swagger)     : http://localhost:8000/docs")
    print("=" * 60 + "\n")
    print("  Press Ctrl+C to terminate all services.")

    try:
        # Keep launcher alive, monitor child processes
        while True:
            if backend_process.poll() is not None:
                print("[WARNING] Backend server exited unexpectedly!")
                break
            if edge_process.poll() is not None:
                print("[WARNING] Edge Analyzer exited unexpectedly!")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Terminating system services...")
    finally:
        backend_process.terminate()
        edge_process.terminate()
        try:
            backend_process.wait(timeout=3)
            edge_process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            backend_process.kill()
            edge_process.kill()
        print("[SHUTDOWN] All services terminated gracefully.")

if __name__ == "__main__":
    main()

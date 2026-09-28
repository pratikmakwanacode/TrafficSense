import os
import sys
import shutil
import subprocess
import asyncio
import time
from datetime import datetime

import cv2
import numpy as np

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.db_models import VideoFeed, TrafficDetection

router = APIRouter()

# Global state
latest_frame: bytes | None = None
active_video_version: int = 0
_active_processor: subprocess.Popen | None = None

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EDGE_DIR = os.path.join(BASE_DIR, "edge_processor")
ACTIVE_FEED_PATH = os.path.join(EDGE_DIR, "active_feed.mp4")
FALLBACK_FEED_PATH = os.path.join(EDGE_DIR, "master_cctv_2min.mp4")

# Ensure edge directory exists
os.makedirs(EDGE_DIR, exist_ok=True)

def _mjpeg_boundary(jpeg_bytes: bytes) -> bytes:
    return (
        b"--frame\r\n"
        b"Content-Type: image/jpeg\r\n\r\n"
        + jpeg_bytes
        + b"\r\n"
    )

@router.post("/upload")
async def upload_video_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Accept video file, save directly to edge_processor/active_feed.mp4,
    register in DB, and restart the edge processor.
    """
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in {".mp4", ".avi", ".mov", ".mkv"}:
        raise HTTPException(
            status_code=400,
            detail="Invalid video format. Supported: .mp4, .avi, .mov, .mkv",
        )

    # 1. Save directly to edge_processor/active_feed.mp4
    try:
        with open(ACTIVE_FEED_PATH, "wb") as buf:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                buf.write(chunk)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"File save failed: {str(exc)}")
    finally:
        await file.close()

    # 2. Add database log
    db_video = VideoFeed(
        video_name=file.filename,
        file_path=ACTIVE_FEED_PATH,
        status="PROCESSING",
    )
    db.add(db_video)
    db.commit()
    db.refresh(db_video)

    # 3. Increment version to signal active streams to restart OpenCV reader
    global latest_frame, active_video_version, _active_processor
    latest_frame = None
    active_video_version += 1

    # 4. Terminate old edge processor
    if _active_processor is not None and _active_processor.poll() is None:
        print("[VIDEO API] Terminating previous edge processor...")
        _active_processor.terminate()
        try:
            _active_processor.wait(timeout=2)
        except Exception:
            _active_processor.kill()

    # 5. Spawn new edge processor
    try:
        cmd = [
            sys.executable, "processor.py",
            "--video_id", str(db_video.id),
            "--video_path", ACTIVE_FEED_PATH,
        ]
        print(f"[VIDEO API] Spawning processor: {' '.join(cmd)}")
        _active_processor = subprocess.Popen(cmd, cwd=EDGE_DIR)
    except Exception as exc:
        print(f"[VIDEO API] WARNING: Failed to start processor: {exc}")

    return {
        "status": "success",
        "message": "Video uploaded successfully. YOLO Analysis restarted.",
        "video_id": db_video.id,
        "video_name": db_video.video_name,
        "timestamp": time.time(),
    }

@router.post("/upload-frame")
async def upload_frame(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    global latest_frame
    latest_frame = await file.read()
    return {"status": "ok"}

@router.get("/feed")
async def video_feed():
    """
    Stream MJPEG frames.
    Priority:
      1. latest_frame (YOLOv8 processed frames from edge processor)
      2. Direct OpenCV decode of active_feed.mp4
      3. Direct OpenCV decode of fallback master_cctv_2min.mp4
    """
    async def _generator():
        global latest_frame, active_video_version
        tracked_version = active_video_version
        cap: cv2.VideoCapture | None = None

        try:
            while True:
                # If new video is uploaded, restart capture
                if tracked_version != active_video_version:
                    if cap is not None:
                        cap.release()
                        cap = None
                    tracked_version = active_video_version
                    latest_frame = None

                # Priority 1: Edge processor processed frames
                if latest_frame is not None:
                    yield _mjpeg_boundary(latest_frame)
                    await asyncio.sleep(0.033)
                    continue

                # Priority 2 & 3: Raw video stream fallback
                video_source = ACTIVE_FEED_PATH if os.path.exists(ACTIVE_FEED_PATH) else FALLBACK_FEED_PATH
                if os.path.exists(video_source):
                    if cap is None or not cap.isOpened():
                        cap = cv2.VideoCapture(video_source)

                    ret, frame = cap.read()
                    if not ret:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ret, frame = cap.read()

                    if ret:
                        frame = cv2.resize(frame, (640, 360))
                        _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
                        yield _mjpeg_boundary(jpeg.tobytes())
                        await asyncio.sleep(0.033)
                        continue

                # If no video exists at all, yield a black frame
                black_frame = np.zeros((360, 640, 3), dtype=np.uint8)
                cv2.putText(black_frame, "CCTV Stream Offline", (180, 190), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                _, jpeg = cv2.imencode(".jpg", black_frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
                yield _mjpeg_boundary(jpeg.tobytes())
                await asyncio.sleep(0.5)

        finally:
            if cap is not None:
                cap.release()

    return StreamingResponse(
        _generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )

@router.post("/complete")
def complete_video_feed(
    video_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    video = db.query(VideoFeed).filter(VideoFeed.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video feed not found")
    video.status = "COMPLETED"
    db.commit()
    return {"status": "success", "message": f"Video feed {video_id} marked as completed"}

@router.get("/list")
def list_video_feeds(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    videos = db.query(VideoFeed).order_by(VideoFeed.upload_time.desc()).all()
    result = []
    for video in videos:
        latest_det = (
            db.query(TrafficDetection)
            .filter(TrafficDetection.video_id == video.id)
            .order_by(TrafficDetection.timestamp.desc())
            .first()
        )
        metrics = None
        if latest_det:
            metrics = {
                "vehicle_count": latest_det.vehicle_count,
                "queue_length": latest_det.queue_length,
                "density_percent": latest_det.density_percent,
                "co2_emission_kg": latest_det.co2_emission_kg,
                "timestamp": latest_det.timestamp.isoformat() if latest_det.timestamp else None,
            }
        result.append({
            "id": video.id,
            "video_name": video.video_name,
            "file_path": video.file_path,
            "upload_time": video.upload_time.isoformat() if video.upload_time else None,
            "status": video.status,
            "latest_metrics": metrics,
        })
    return result

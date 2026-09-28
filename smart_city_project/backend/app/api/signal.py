from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Dict, Any
from sqlalchemy.orm import Session
from app.core.config import traffic_store, settings
from app.core.dependencies import get_operator
from app.core.database import get_db
from app.models.db_models import TrafficDetection

router = APIRouter()

class SignalOptimizeRequest(BaseModel):
    node_id: str = Field(..., description="Intersection ID (A, B, C...)")
    queue_lengths: Dict[str, int] = Field(..., description="Queues mapping for N, S, E, W directions")

@router.post("/optimize")
def optimize_intersection_timing(
    payload: SignalOptimizeRequest, 
    video_id: int = Query(None, description="Dynamic video ID link"),
    user: dict = Depends(get_operator),
    db: Session = Depends(get_db)
):
    if payload.node_id not in settings.INTERSECTIONS:
        raise HTTPException(status_code=400, detail="Invalid node intersection ID")
        
    required_dirs = {"N", "S", "E", "W"}
    if not required_dirs.issubset(payload.queue_lengths.keys()):
        raise HTTPException(status_code=400, detail="Lanes must specify N, S, E, W directions")
        
    q_ns = payload.queue_lengths.get("N", 0) + payload.queue_lengths.get("S", 0)
    q_ew = payload.queue_lengths.get("E", 0) + payload.queue_lengths.get("W", 0)
    
    # DB Overrides: If video_id is passed, fetch queue from latest detections
    if video_id is not None:
        latest_det = db.query(TrafficDetection)\
            .filter(TrafficDetection.video_id == video_id)\
            .order_by(TrafficDetection.timestamp.desc())\
            .first()
        if latest_det:
            # Dynamically apportion the database queue length
            q_ns = latest_det.queue_length
            q_ew = max(2, int(latest_det.queue_length * 0.4))
            print(f"[SIGNAL OPTIMIZE] DB query override: video_id={video_id}, dynamic queues: NS={q_ns}, EW={q_ew}")

    total_q = q_ns + q_ew
    
    min_g = settings.MIN_GREEN_TIME
    max_g = settings.MAX_GREEN_TIME
    
    if total_q == 0:
        ns_green = min_g
        ew_green = min_g
    else:
        budget = min_g * 2 + min(max_g * 2 - min_g * 2, total_q * 2.0)
        ns_green = int((q_ns / total_q) * budget)
        ew_green = int((q_ew / total_q) * budget)
        
        ns_green = max(min_g, min(max_g, ns_green))
        ew_green = max(min_g, min(max_g, ew_green))
        
    phase = "GREEN_NS" if q_ns >= q_ew else "GREEN_EW"
    duration = ns_green if phase == "GREEN_NS" else ew_green
    
    # Update local database store
    traffic_store.update_intersection_signal(
        node_id=payload.node_id,
        phase=phase,
        duration=duration,
        queue_lengths=payload.queue_lengths
    )
    
    # Calculate savings metrics
    delay_saved = total_q * 1.5
    co2_saved_g = delay_saved * settings.CO2_EMISSION_FACTOR_IDLE_G_PER_S
    
    return {
        "node_id": payload.node_id,
        "recommended_phase": phase,
        "recommended_duration": duration,
        "ns_green_duration": ns_green,
        "ew_green_duration": ew_green,
        "estimated_delay_saved_seconds": round(delay_saved, 1),
        "estimated_co2_reduction_g": round(co2_saved_g, 2)
    }

@router.get("/status")
def get_signal_statuses(node_id: str = None):
    if node_id:
        if node_id not in settings.INTERSECTIONS:
            raise HTTPException(status_code=400, detail="Invalid node intersection ID")
        return traffic_store.get_intersection(node_id)
    return traffic_store.get_all_intersections()

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.core.config import traffic_store, settings
from app.services.congestion_service import CongestionService
from app.core.dependencies import get_current_user
from app.core.database import get_db
from app.models.db_models import TrafficDetection, VideoFeed, EmergencyClearance, Incident

router = APIRouter()

class IncidentCreateRequest(BaseModel):
    video_id: int
    type: str
    location: str
    timestamp: str

class TrafficUpdateRequest(BaseModel):
    video_id: int = Field(..., description="Foreign key link to VideoFeed ID")
    source: str = Field(..., description="Source intersection ID")
    target: str = Field(..., description="Target intersection ID")
    vehicle_count: int = Field(..., ge=0, description="Monitored vehicle count")
    average_speed_kmh: float = Field(..., ge=0.0, description="Average vehicles speed")
    queue_length: int = Field(..., ge=0, description="Queue length in vehicles")
    is_emergency: bool = Field(False, description="Emergency vehicle priority trigger")

class TrafficUpdateResponse(BaseModel):
    message: str
    road_key: str
    data: Dict[str, Any]

class LiveTrafficSummary(BaseModel):
    total_vehicles: int
    average_density: float
    total_queue_length: int
    estimated_hourly_co2_kg: float
    road_states: List[Dict[str, Any]]
    emergency_active: bool = False
    emergency_junction: str | None = None

@router.post("/update", response_model=TrafficUpdateResponse)
def update_traffic(
    payload: TrafficUpdateRequest, 
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if payload.source not in settings.INTERSECTIONS or payload.target not in settings.INTERSECTIONS:
        raise HTTPException(status_code=400, detail="Invalid source or target intersection ID")
        
    # Verify video_id exists in database
    video = db.query(VideoFeed).filter(VideoFeed.id == payload.video_id).first()
    if not video:
        video = VideoFeed(
            id=payload.video_id,
            video_name=f"Live CCTV Feed #{payload.video_id}",
            file_path="edge_processor/master_cctv_2min.mp4",
            status="PROCESSING"
        )
        db.add(video)
        db.commit()
        db.refresh(video)
        
    road = traffic_store.update_road_traffic(
        source=payload.source,
        target=payload.target,
        count=payload.vehicle_count,
        speed=payload.average_speed_kmh,
        queue=payload.queue_length
    )
    
    # Trigger congestion calculations on updates
    congestion_data = CongestionService.calculate_congestion_and_emissions(
        payload.source, 
        payload.target, 
        payload.vehicle_count, 
        payload.queue_length
    )
    
    # Write detection to MySQL/SQLite database
    db_detection = TrafficDetection(
        video_id=payload.video_id,
        source=payload.source,
        target=payload.target,
        vehicle_count=payload.vehicle_count,
        queue_length=payload.queue_length,
        density_percent=congestion_data["density_percent"],
        co2_emission_kg=congestion_data["hourly_co2_emission_kg"]
    )
    db.add(db_detection)
    
    # Dynamic Emergency Overrides
    if payload.is_emergency:
        traffic_store.set_emergency_override(junction_id=payload.source, active=True)
        db_clearance = EmergencyClearance(
            video_id=payload.video_id,
            junction_id=payload.source,
            status="ACTIVE"
        )
        db.add(db_clearance)
    else:
        # Clear emergency override if the priority state has passed
        if traffic_store.emergency_active and traffic_store.emergency_junction == payload.source:
            traffic_store.set_emergency_override(junction_id=payload.source, active=False)
            latest_clearance = db.query(EmergencyClearance)\
                .filter(EmergencyClearance.video_id == payload.video_id, EmergencyClearance.status == "ACTIVE")\
                .order_by(EmergencyClearance.timestamp.desc())\
                .first()
            if latest_clearance:
                latest_clearance.status = "CLEARED"
                
    # ── Automated Notification Triggers ──────────────────────
    from app.services.notification_service import NotificationService
    
    # 1. Congestion Alert (>80% Density)
    if congestion_data["density_percent"] > 80.0:
        NotificationService.create_and_broadcast_notification(
            db=db,
            video_id=payload.video_id,
            notif_type="CONGESTION",
            message=f"Heavy traffic density of {congestion_data['density_percent']}% detected on corridor {payload.source}->{payload.target}",
            junction=payload.source
        )

    # 2. Emergency Vehicle Alert
    if payload.is_emergency:
        NotificationService.create_and_broadcast_notification(
            db=db,
            video_id=payload.video_id,
            notif_type="EMERGENCY",
            message=f"Emergency vehicle detected at junction {payload.source}! Priority clearance active.",
            junction=payload.source
        )
                
    # Update status of video feed processing
    video.status = "PROCESSING"
    
    db.commit()
    
    # Merge calculations locally for runtime HUD response
    road.update({
        "congestion_status": congestion_data["congestion_status"],
        "hourly_co2_emission_kg": congestion_data["hourly_co2_emission_kg"]
    })
    
    return {
        "message": "Edge telemetry update received and persisted successfully",
        "road_key": f"{payload.source}->{payload.target}",
        "data": road
    }

@router.get("/current", response_model=LiveTrafficSummary)
def get_current_traffic_summary(
    video_id: int = Query(None, description="Filter summary by Video ID"),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # If no video_id specified, pick the latest video uploaded
    if video_id is None:
        latest_video = db.query(VideoFeed).order_by(VideoFeed.upload_time.desc()).first()
        if latest_video:
            video_id = latest_video.id
            
    if video_id is not None:
        # Fetch the latest telemetry records for this video feed from DB
        detections = db.query(TrafficDetection)\
            .filter(TrafficDetection.video_id == video_id)\
            .order_by(TrafficDetection.timestamp.desc())\
            .limit(10).all()
            
        if detections:
            road_states = []
            seen_links = set()
            total_vehicles = 0
            total_queue = 0
            density_sum = 0.0
            co2_sum = 0.0
            
            for det in detections:
                link_key = f"{det.source}->{det.target}"
                if link_key in seen_links:
                    continue
                seen_links.add(link_key)
                
                road_states.append({
                    "source": det.source,
                    "target": det.target,
                    "vehicle_count": det.vehicle_count,
                    "queue_length": det.queue_length,
                    "density_percent": det.density_percent,
                    "co2_emission_kg": det.co2_emission_kg,
                })
                total_vehicles += det.vehicle_count
                total_queue += det.queue_length
                density_sum += det.density_percent
                co2_sum += det.co2_emission_kg
                
            avg_density = density_sum / len(road_states) if road_states else 0.0
            
            return {
                "total_vehicles": total_vehicles,
                "average_density": round(avg_density, 2),
                "total_queue_length": total_queue,
                "estimated_hourly_co2_kg": round(co2_sum, 2),
                "road_states": road_states,
                "emergency_active": traffic_store.emergency_active,
                "emergency_junction": traffic_store.emergency_junction
            }

    # Fallback to local memory mock state
    roads = traffic_store.get_all_roads()
    total_count = sum(r.get("vehicle_count", 0) for r in roads)
    total_queue = sum(r.get("queue_length", 0) for r in roads)
    
    avg_density = 0.0
    if roads:
        avg_density = sum(r.get("density_percent", 0.0) for r in roads) / len(roads)
        
    total_co2 = sum(r.get("co2_emission_kg", 0.0) for r in roads)
    
    return {
        "total_vehicles": total_count,
        "average_density": round(avg_density, 2),
        "total_queue_length": total_queue,
        "estimated_hourly_co2_kg": round(total_co2, 2),
        "road_states": roads,
        "emergency_active": traffic_store.emergency_active,
        "emergency_junction": traffic_store.emergency_junction
    }

@router.get("/emissions-heatmap")
def get_emissions_heatmap(
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    roads = traffic_store.get_all_roads()
    heatmap = []
    
    for node in settings.INTERSECTIONS:
        node_roads = [r for r in roads if r.get("source") == node]
        total_co2 = sum(r.get("co2_emission_kg", 0.0) for r in node_roads)
        
        if total_co2 > 50.0:
            intensity = "HIGH"
        elif total_co2 > 15.0:
            intensity = "MEDIUM"
        else:
            intensity = "LOW"
            
        heatmap.append({
            "junction": node,
            "total_co2_kg_hr": round(total_co2, 2),
            "intensity": intensity
        })
        
    return heatmap

@router.get("/history")
def get_traffic_history(
    video_id: int = Query(..., description="Filter by Video ID"),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns time-series historical records for charting.
    """
    detections = db.query(TrafficDetection)\
        .filter(TrafficDetection.video_id == video_id)\
        .order_by(TrafficDetection.timestamp.asc())\
        .all()
        
    return [
        {
            "timestamp": d.timestamp.isoformat() if d.timestamp else None,
            "vehicle_count": d.vehicle_count,
            "queue_length": d.queue_length,
            "density_percent": d.density_percent,
            "co2_emission_kg": d.co2_emission_kg
        }
        for d in detections
    ]
@router.get("/forecast")
def get_traffic_forecast(
    video_id: int = Query(None, description="Filter forecast by Video ID"),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if video_id is None:
        latest_video = db.query(VideoFeed).order_by(VideoFeed.upload_time.desc()).first()
        if latest_video:
            video_id = latest_video.id
            
    if video_id is None:
        raise HTTPException(status_code=404, detail="No video feed found for forecasting")
        
    from app.services.prediction_service import PredictionService
    return PredictionService.get_forecast(db, video_id)


@router.get("/predict")
def predict_traffic_congestion(
    source: str = Query(None, description="Source node"),
    target: str = Query(None, description="Destination node"),
    horizon: int = Query(15, description="Prediction horizon minutes")
):
    if source and target:
        if source not in settings.INTERSECTIONS or target not in settings.INTERSECTIONS:
            raise HTTPException(status_code=400, detail="Invalid node parameters")
        pred = CongestionService.predict_future_congestion(source, target, horizon)
        return [pred]
        
    return CongestionService.get_predictions_for_all(horizon)

@router.post("/incident")
def record_incident(
    payload: IncidentCreateRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    video = db.query(VideoFeed).filter(VideoFeed.id == payload.video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video feed not found")
        
    # Parse timestamp
    from datetime import datetime
    try:
        ts = datetime.fromisoformat(payload.timestamp.replace("Z", "+00:00"))
    except Exception:
        ts = datetime.utcnow()
        
    db_incident = Incident(
        video_id=payload.video_id,
        type=payload.type,
        location=payload.location,
        timestamp=ts
    )
    db.add(db_incident)
    db.commit()
    db.refresh(db_incident)

    from app.services.notification_service import NotificationService
    notif_msg = f"Hazard detected: {payload.type} at junction {payload.location}."
    NotificationService.create_and_broadcast_notification(
        db=db,
        video_id=payload.video_id,
        notif_type="ACCIDENT" if payload.type == "ACCIDENT" else "HAZARD",
        message=notif_msg,
        junction=payload.location
    )
    
    print(f"[INCIDENT RECEIVED] Type: {payload.type} at Junction: {payload.location}")
    return {"message": "Incident logged successfully", "id": db_incident.id}

@router.get("/incidents")
def get_incidents(
    video_id: int = Query(None, description="Optional video ID filter"),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Incident)
    if video_id:
        query = query.filter(Incident.video_id == video_id)
    incidents = query.order_by(Incident.timestamp.desc()).limit(50).all()
    
    return [
        {
            "id": inc.id,
            "video_id": inc.video_id,
            "type": inc.type,
            "location": inc.location,
            "timestamp": inc.timestamp.isoformat()
        }
        for inc in incidents
    ]

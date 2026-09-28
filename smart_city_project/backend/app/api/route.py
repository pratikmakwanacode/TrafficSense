from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.core.config import settings
from app.services.routing_service import RoutingService

router = APIRouter()

class RouteOptimalRequest(BaseModel):
    start: str = Field(..., description="Start node intersection ID")
    end: str = Field(..., description="End node intersection ID")

@router.post("/optimal")
def calculate_optimal_route(payload: RouteOptimalRequest):
    if payload.start not in settings.INTERSECTIONS:
        raise HTTPException(status_code=400, detail=f"Invalid start node ID: {payload.start}")
    if payload.end not in settings.INTERSECTIONS:
        raise HTTPException(status_code=400, detail=f"Invalid destination node ID: {payload.end}")
        
    result = RoutingService.calculate_optimal_path(payload.start, payload.end)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
        
    return result

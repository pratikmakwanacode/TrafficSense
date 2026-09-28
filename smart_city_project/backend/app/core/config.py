import time
from typing import Dict, List, Any, Tuple
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Smart City Traffic Management System"
    API_V1_STR: str = "/api"
    
    # Constants
    CO2_EMISSION_FACTOR_IDLE_G_PER_S: float = 2.4
    CO2_EMISSION_FACTOR_MOVE_G_PER_M: float = 120.0
    
    MIN_GREEN_TIME: int = 15
    MAX_GREEN_TIME: int = 75
    
    # Core Intersections
    INTERSECTIONS: List[str] = ["A", "B", "C", "D", "E", "F"]
    
    # Road network definitions
    # (Source, Target, Distance m, Speed limit km/h, Capacity)
    ROAD_NETWORK: List[Tuple[str, str, float, float, int]] = [
        ("A", "B", 800.0, 50.0, 100),
        ("B", "C", 500.0, 40.0, 80),
        ("C", "D", 1200.0, 60.0, 150),
        ("D", "E", 1000.0, 50.0, 120),
        ("A", "F", 1500.0, 60.0, 140),
        ("F", "C", 900.0, 45.0, 90),
        ("F", "E", 1800.0, 70.0, 200),
        ("B", "D", 700.0, 40.0, 75),
    ]

    class Config:
        case_sensitive = True

settings = Settings()

class RealTimeTrafficStore:
    def __init__(self):
        # Maps "source->target" to traffic details
        self.roads: Dict[str, Dict[str, Any]] = {}
        # Maps "node_id" to signal status details
        self.intersections: Dict[str, Dict[str, Any]] = {}
        # History list for trend calculations
        self.history: List[Dict[str, Any]] = []
        
        # Emergency vehicle priority state
        self.emergency_active: bool = False
        self.emergency_junction: str = None
        
        self._initialize_store()

    def _initialize_store(self):
        # Initialize default road metrics
        for source, target, distance, speed_limit, capacity in settings.ROAD_NETWORK:
            road_key = f"{source}->{target}"
            self.roads[road_key] = {
                "source": source,
                "target": target,
                "distance_m": distance,
                "speed_limit_kmh": speed_limit,
                "capacity": capacity,
                "vehicle_count": 0,
                "queue_length": 0,
                "density_percent": 0.0,
                "co2_emission_kg": 0.0,
                "average_speed_kmh": speed_limit,
                "last_updated": time.time()
            }
            
        # Initialize default intersection states
        for node in settings.INTERSECTIONS:
            self.intersections[node] = {
                "id": node,
                "signal_phase": "GREEN_NS",
                "green_light_time": 30,
                "time_remaining": 30,
                "queue_lengths": {"N": 0, "S": 0, "E": 0, "W": 0},
                "last_updated": time.time()
            }

    def update_road_traffic(self, source: str, target: str, count: int, speed: float, queue: int) -> Dict[str, Any]:
        road_key = f"{source}->{target}"
        if road_key not in self.roads:
            self.roads[road_key] = {
                "source": source,
                "target": target,
                "distance_m": 1000.0,
                "speed_limit_kmh": 50.0,
                "capacity": 100,
            }
            
        road = self.roads[road_key]
        capacity = road.get("capacity", 100)
        density_percent = min(100.0, (count / capacity) * 100.0)
        
        # Calculate dynamic hourly CO2 rate for this corridor based on speeds & queues
        # CO2 = idle emissions + moving emissions
        idle_co2_kg = (queue * settings.CO2_EMISSION_FACTOR_IDLE_G_PER_S * 3600.0) / 1000.0
        moving_co2_kg = (max(0, count - queue) * (road.get("distance_m", 1000.0) * settings.CO2_EMISSION_FACTOR_MOVE_G_PER_M / 1000.0)) / 1000.0
        total_co2_kg = round(idle_co2_kg + moving_co2_kg, 2)
        
        road.update({
            "vehicle_count": count,
            "average_speed_kmh": max(1.0, speed),
            "density_percent": round(density_percent, 2),
            "queue_length": queue,
            "co2_emission_kg": total_co2_kg,
            "last_updated": time.time()
        })
        
        # Record update history
        history_record = {
            "timestamp": time.time(),
            "road_key": road_key,
            "source": source,
            "target": target,
            "vehicle_count": count,
            "average_speed_kmh": speed,
            "density_percent": density_percent,
            "queue_length": queue,
            "co2_emission_kg": total_co2_kg
        }
        self.history.append(history_record)
        if len(self.history) > 5000:
            self.history.pop(0)
            
        return road

    def update_intersection_signal(self, node_id: str, phase: str, duration: int, queue_lengths: Dict[str, int]) -> Dict[str, Any]:
        if node_id in self.intersections:
            self.intersections[node_id].update({
                "signal_phase": phase,
                "green_light_time": duration,
                "time_remaining": duration,
                "queue_lengths": queue_lengths,
                "last_updated": time.time()
            })
            return self.intersections[node_id]
        return {}

    def set_emergency_override(self, junction_id: str, active: bool):
        self.emergency_active = active
        self.emergency_junction = junction_id if active else None
        
        if active and junction_id in self.intersections:
            self.intersections[junction_id].update({
                "signal_phase": "GREEN_NS",
                "green_light_time": 90,
                "time_remaining": 90,
                "last_updated": time.time()
            })
            print(f"[STORE OVERRIDE] Siren alert triggered! Forced Green Wave at Junction {junction_id}.")

    def get_all_roads(self) -> List[Dict[str, Any]]:
        return list(self.roads.values())

    def get_road(self, source: str, target: str) -> Dict[str, Any]:
        return self.roads.get(f"{source}->{target}", {})

    def get_all_intersections(self) -> List[Dict[str, Any]]:
        return list(self.intersections.values())

    def get_intersection(self, node_id: str) -> Dict[str, Any]:
        return self.intersections.get(node_id, {})

    def get_history(self, road_key: str = None) -> List[Dict[str, Any]]:
        if road_key:
            return [h for h in self.history if h["road_key"] == road_key]
        return self.history

# Create singleton store instance
traffic_store = RealTimeTrafficStore()

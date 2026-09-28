import networkx as nx
from typing import Dict, List, Any
from app.core.config import traffic_store, settings
from app.core.database import SessionLocal
from app.models.db_models import TrafficDetection

class RoutingService:
    @staticmethod
    def get_dynamic_weight(u: str, v: str, edge_data: Dict[str, Any]) -> float:
        """
        Bureau of Public Roads link function weight calculation.
        Queries the database for live telemetry from active cameras.
        If a route link has density > 75%, applies a 5x congestion penalty.
        """
        distance = edge_data.get("distance_m", 1000.0)
        speed_limit = edge_data.get("speed_limit_kmh", 50.0)
        
        # Free-flow time in seconds
        t_0 = distance / (speed_limit / 3.6)
        
        # Attempt to read live density from DB
        density = 0.0
        db = SessionLocal()
        try:
            latest_det = db.query(TrafficDetection)\
                .filter(TrafficDetection.source == u, TrafficDetection.target == v)\
                .order_by(TrafficDetection.timestamp.desc())\
                .first()
            if latest_det:
                density = latest_det.density_percent
            else:
                # Fallback to local memory store
                live_road = traffic_store.get_road(u, v)
                density = live_road.get("density_percent", 0.0) if live_road else 0.0
        except Exception:
            # Safe fallback on query failure
            live_road = traffic_store.get_road(u, v)
            density = live_road.get("density_percent", 0.0) if live_road else 0.0
        finally:
            db.close()
            
        alpha = 0.15
        beta = 4.0
        
        # BPR calculation
        travel_time_sec = t_0 * (1.0 + alpha * ((density / 100.0) ** beta))
        
        # High Congestion Penalty: If road saturation exceeds 75%, multiply weight by 5x
        if density > 75.0:
            travel_time_sec *= 5.0
            
        return travel_time_sec

    @classmethod
    def calculate_optimal_path(cls, start: str, end: str) -> Dict[str, Any]:
        """
        Runs A* search to calculate the optimal eco-path avoiding congested intersections.
        """
        if start not in settings.INTERSECTIONS or end not in settings.INTERSECTIONS:
            return {"error": "Invalid start or destination node ID"}
            
        G = nx.DiGraph()
        
        # Build network topology
        for source, target, distance, speed_limit, capacity in settings.ROAD_NETWORK:
            G.add_edge(
                source, 
                target, 
                distance_m=distance, 
                speed_limit_kmh=speed_limit,
                capacity=capacity
            )
            # Bidirectional paths
            G.add_edge(
                target,
                source,
                distance_m=distance,
                speed_limit_kmh=speed_limit,
                capacity=capacity
            )
            
        def weight_func(u: str, v: str, data: dict) -> float:
            return cls.get_dynamic_weight(u, v, data)
            
        # Euclidean-like consistent heuristic
        def h_func(u: str, v: str) -> float:
            return 1.0

        try:
            optimal_path = nx.astar_path(G, start, end, heuristic=h_func, weight=weight_func)
            shortest_path = nx.shortest_path(G, start, end, weight="distance_m")
            
            opt_metrics = cls._get_path_metrics(G, optimal_path)
            base_metrics = cls._get_path_metrics(G, shortest_path)
            
            time_saved = max(0.0, base_metrics["time_sec"] - opt_metrics["time_sec"])
            co2_saved = max(0.0, base_metrics["co2_kg"] - opt_metrics["co2_kg"])
            
            return {
                "start": start,
                "end": end,
                "optimal_path": optimal_path,
                "optimal_distance_m": opt_metrics["distance_m"],
                "optimal_travel_time_sec": round(opt_metrics["time_sec"], 1),
                "optimal_co2_kg": round(opt_metrics["co2_kg"], 3),
                
                "baseline_path": shortest_path,
                "baseline_distance_m": base_metrics["distance_m"],
                "baseline_travel_time_sec": round(base_metrics["time_sec"], 1),
                "baseline_co2_kg": round(base_metrics["co2_kg"], 3),
                
                "time_saved_seconds": round(time_saved, 1),
                "co2_saved_kg": round(co2_saved, 3),
                "co2_saved_percent": round((co2_saved / max(0.001, base_metrics["co2_kg"])) * 100, 1)
            }
        except nx.NetworkXNoPath:
            return {"error": f"No network route connecting {start} and {end}."}

    @classmethod
    def _get_path_metrics(cls, G: nx.DiGraph, path: List[str]) -> Dict[str, float]:
        dist = 0.0
        time_sec = 0.0
        co2_kg = 0.0
        
        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            edge = G[u][v]
            
            d = edge["distance_m"]
            speed_limit = edge["speed_limit_kmh"]
            
            # Dynamic travel time weight
            t = cls.get_dynamic_weight(u, v, edge)
            
            # Estimate CO2 emissions using precise mixed vehicle weights:
            # Car (70% @ 120g/km), Bus/Truck (10% @ 800g/km), Motorbike (20% @ 40g/km) -> avg 172g/km = 0.172g/m.
            # Idle factors: Car (2.4g/s), Bus (12g/s), Motorbike (0.8g/s) -> avg 3.04g/s.
            free_flow_t = d / (speed_limit / 3.6)
            delay = max(0.0, t - free_flow_t)
            
            co2_g = (d * 0.172) + (delay * 3.04)
            
            dist += d
            time_sec += t
            co2_kg += co2_g / 1000.0
            
        return {
            "distance_m": dist,
            "time_sec": time_sec,
            "co2_kg": co2_kg
        }

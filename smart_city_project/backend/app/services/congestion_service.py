import time
import math
import numpy as np
from typing import Dict, Any, List
from app.core.config import traffic_store, settings

class CongestionService:
    @staticmethod
    def calculate_congestion_and_emissions(source: str, target: str, count: int, queue: int) -> Dict[str, Any]:
        """
        Heuristic calculation of instant congestion level and emissions rate.
        """
        road_key = f"{source}->{target}"
        road = traffic_store.get_road(source, target)
        if not road:
            return {"error": f"Road {road_key} not found"}
            
        capacity = road.get("capacity", 100)
        density = min(100.0, (count / capacity) * 100.0)
        
        # Classify congestion
        if density < 30.0:
            status = "Low Congestion"
        elif density < 65.0:
            status = "Moderate Congestion"
        elif density < 85.0:
            status = "Heavy Congestion"
        else:
            status = "Gridlock Warning"
            
        # Calculate instant CO2 rate (in kg/hour)
        idle_co2 = (queue * settings.CO2_EMISSION_FACTOR_IDLE_G_PER_S * 3600.0) / 1000.0
        moving_co2 = (max(0, count - queue) * (road.get("distance_m", 1000.0) * settings.CO2_EMISSION_FACTOR_MOVE_G_PER_M / 1000.0)) / 1000.0
        total_co2_kg_hr = round(idle_co2 + moving_co2, 2)
        
        return {
            "road_key": road_key,
            "density_percent": round(density, 2),
            "congestion_status": status,
            "hourly_co2_emission_kg": total_co2_kg_hr,
            "timestamp": time.time()
        }

    @staticmethod
    def predict_future_congestion(source: str, target: str, horizon_minutes: int = 15) -> Dict[str, Any]:
        """
        Predicts traffic density and congestion levels for a future time step.
        Uses time-of-day rush hour models blended with current trend vectors.
        """
        road_key = f"{source}->{target}"
        road = traffic_store.get_road(source, target)
        if not road:
            return {"error": f"Road {road_key} not found"}
            
        current_density = road.get("density_percent", 0.0)
        speed_limit = road.get("speed_limit_kmh", 50.0)
        
        # Extrapolate trend from store history
        history = traffic_store.get_history(road_key)
        rate_of_change = 0.0
        if len(history) >= 3:
            recent_times = [h["timestamp"] for h in history[-5:]]
            recent_densities = [h["density_percent"] for h in history[-5:]]
            t_norm = np.array(recent_times) - recent_times[0]
            if len(t_norm) > 1 and np.max(t_norm) > 0:
                coeffs = np.polyfit(t_norm, recent_densities, 1)
                rate_of_change = coeffs[0]  # change in % density per second
                
        # sinusoidal daily peak trend
        now = time.localtime()
        current_hour = now.tm_hour + now.tm_min / 60.0
        future_hour = (current_hour + horizon_minutes / 60.0) % 24.0
        
        def peak_profile(h: float) -> float:
            p1 = math.exp(-((h - 8.5) / 1.5) ** 2)
            p2 = math.exp(-((h - 17.5) / 1.8) ** 2)
            return 0.15 + 0.65 * max(p1, p2)
            
        current_cycle = peak_profile(current_hour)
        future_cycle = peak_profile(future_hour)
        
        # Extrapolated density change
        extrapolated_change = rate_of_change * (horizon_minutes * 60)
        
        # Blend factor based on prediction horizon
        blend = min(1.0, horizon_minutes / 60.0)
        predicted_density = (1 - blend) * (current_density + extrapolated_change) + blend * (future_cycle * 100)
        predicted_density = max(0.0, min(100.0, predicted_density))
        
        # Dynamic speed calculation
        predicted_speed = speed_limit * (1.0 - (predicted_density / 100.0))
        predicted_speed = max(5.0, predicted_speed)
        
        # Determine status
        if predicted_density < 30.0:
            status = "Low Congestion"
        elif predicted_density < 65.0:
            status = "Moderate Congestion"
        elif predicted_density < 85.0:
            status = "Heavy Congestion"
        else:
            status = "Gridlock Warning"
            
        return {
            "road_key": road_key,
            "horizon_minutes": horizon_minutes,
            "predicted_density_percent": round(predicted_density, 2),
            "predicted_speed_kmh": round(predicted_speed, 2),
            "predicted_status": status,
            "timestamp": time.time() + (horizon_minutes * 60)
        }

    @classmethod
    def get_predictions_for_all(cls, horizon_minutes: int = 15) -> List[Dict[str, Any]]:
        roads = traffic_store.get_all_roads()
        results = []
        for r in roads:
            pred = cls.predict_future_congestion(r["source"], r["target"], horizon_minutes)
            results.append(pred)
        return results

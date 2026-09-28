import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.models.db_models import TrafficDetection, VideoFeed

class PredictionService:
    @staticmethod
    def get_forecast(db: Session, video_id: int) -> Dict[str, Any]:
        """
        Queries historical TrafficDetection records for a specific video_id.
        Builds a linear trend model on recent window points to project future counts and densities.
        Predicts vehicle counts and congestion probabilities at 15-min, 30-min, and 60-min horizons.
        """
        detections = db.query(TrafficDetection)\
            .filter(TrafficDetection.video_id == video_id)\
            .order_by(TrafficDetection.timestamp.asc())\
            .all()
            
        if not detections:
            # Fallback values if no historical data is present
            return {
                "video_id": video_id,
                "forecasts": [
                    {"horizon_minutes": 15, "predicted_vehicle_count": 10, "congestion_probability": 0.25},
                    {"horizon_minutes": 30, "predicted_vehicle_count": 12, "congestion_probability": 0.30},
                    {"horizon_minutes": 60, "predicted_vehicle_count": 15, "congestion_probability": 0.40}
                ],
                "historical_forecasts": []
            }
            
        timestamps = [d.timestamp for d in detections]
        counts = [d.vehicle_count for d in detections]
        densities = [d.density_percent for d in detections]
        
        n = len(counts)
        last_count = counts[-1]
        last_density = densities[-1]
        
        # Fit linear model on recent points (up to 30 points) to detect trend
        window = min(30, n)
        recent_counts = counts[-window:]
        recent_densities = densities[-window:]
        recent_indices = list(range(window))
        
        if window >= 2:
            x_mean = sum(recent_indices) / window
            y_mean_count = sum(recent_counts) / window
            y_mean_density = sum(recent_densities) / window
            
            num_c = sum((recent_indices[i] - x_mean) * (recent_counts[i] - y_mean_count) for i in range(window))
            num_d = sum((recent_indices[i] - x_mean) * (recent_densities[i] - y_mean_density) for i in range(window))
            den = sum((recent_indices[i] - x_mean) ** 2 for i in range(window))
            
            slope_count = num_c / den if den != 0 else 0.0
            slope_density = num_d / den if den != 0 else 0.0
        else:
            slope_count = 0.0
            slope_density = 0.0

        # Forecast horizons: 15, 30, 60 steps ahead
        forecasts = []
        for horizon in [15, 30, 60]:
            pred_count = last_count + slope_count * horizon
            pred_count = max(0, min(120, int(round(pred_count))))
            
            pred_density = last_density + slope_density * horizon
            pred_density = max(0.0, min(100.0, pred_density))
            congestion_prob = round(pred_density / 100.0, 2)
            
            forecasts.append({
                "horizon_minutes": horizon,
                "predicted_vehicle_count": pred_count,
                "congestion_probability": congestion_prob
            })
            
        # Generate historical forecasts for plotting (60-minute forecasted congestion vs actual)
        # For each point i in history, compute what the 60-step ahead predicted congestion was/is.
        historical_forecasts = []
        for i in range(n):
            if i < 2:
                historical_forecasts.append({
                    "timestamp": timestamps[i].isoformat(),
                    "actual_vehicle_count": counts[i],
                    "predicted_congestion_percent": round(densities[i], 2)
                })
                continue
            
            sub_window = min(15, i + 1)
            sub_counts = counts[i - sub_window + 1 : i + 1]
            sub_densities = densities[i - sub_window + 1 : i + 1]
            sub_indices = list(range(sub_window))
            
            sub_x_mean = sum(sub_indices) / sub_window
            sub_y_density_mean = sum(sub_densities) / sub_window
            
            num_d = sum((sub_indices[j] - sub_x_mean) * (sub_densities[j] - sub_y_density_mean) for j in range(sub_window))
            den_d = sum((sub_indices[j] - sub_x_mean) ** 2 for j in range(sub_window))
            sub_slope_density = num_d / den_d if den_d != 0 else 0.0
            
            pred_density_60 = sub_densities[-1] + sub_slope_density * 60
            pred_density_60 = max(0.0, min(100.0, pred_density_60))
            
            historical_forecasts.append({
                "timestamp": timestamps[i].isoformat(),
                "actual_vehicle_count": counts[i],
                "predicted_congestion_percent": round(pred_density_60, 2)
            })
            
        return {
            "video_id": video_id,
            "forecasts": forecasts,
            "historical_forecasts": historical_forecasts
        }

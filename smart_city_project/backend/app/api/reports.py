import io
import pandas as pd
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.db_models import TrafficDetection, VideoFeed
from fpdf import FPDF

router = APIRouter()

class PDFReport(FPDF):
    def header(self):
        # Top banner background
        self.set_fill_color(15, 20, 32) # Dark slate
        self.rect(0, 0, 210, 32, "F")
        
        # Banner Title
        self.set_y(6)
        self.set_font("helvetica", "B", 16)
        self.set_text_color(6, 182, 212) # Cyan
        self.cell(0, 8, "AHMEDABAD SMART CITY TRAFFIC REPORT", align="C")
        self.ln(8)
        self.set_font("helvetica", "", 9)
        self.set_text_color(180, 180, 180)
        self.cell(0, 6, "Live Telemetry Analytics & Environmental Impact Assessment", align="C")
        self.ln(18)
        
    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Page {self.page_no()}  |  Ahmedabad Traffic Control & Optimization Portal", align="C")

@router.get("/download")
def download_traffic_report(
    video_id: int = Query(..., description="Video Feed ID"),
    format: str = Query("pdf", description="Report format: pdf or csv"),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 1. Fetch Video Feed Info
    video = db.query(VideoFeed).filter(VideoFeed.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video feed not found")
        
    # 2. Fetch all telemetry records
    detections = db.query(TrafficDetection)\
        .filter(TrafficDetection.video_id == video_id)\
        .order_by(TrafficDetection.timestamp.asc())\
        .all()
        
    if not detections:
        raise HTTPException(status_code=400, detail="No traffic analytics data logged for this video feed")

    # 3. Calculate key statistics
    num_records = len(detections)
    total_vehicles = sum(d.vehicle_count for d in detections)
    avg_vehicles = round(total_vehicles / num_records, 2)
    max_vehicles = max(d.vehicle_count for d in detections)
    
    total_queue = sum(d.queue_length for d in detections)
    avg_queue = round(total_queue / num_records, 2)
    max_queue = max(d.queue_length for d in detections)
    
    avg_density = round(sum(d.density_percent for d in detections) / num_records, 2)
    max_density = round(max(d.density_percent for d in detections), 2)
    
    # Total CO2 emissions integration (rate is in kg/hr, records generated approx every 1 second)
    total_co2_kg = round(sum(d.co2_emission_kg for d in detections) / 3600.0, 3)
    
    # Group metrics by corridor (source -> target)
    corridor_data = {}
    for d in detections:
        key = f"{d.source}->{d.target}"
        if key not in corridor_data:
            corridor_data[key] = {
                "counts": [], "queues": [], "densities": [], "co2": []
            }
        corridor_data[key]["counts"].append(d.vehicle_count)
        corridor_data[key]["queues"].append(d.queue_length)
        corridor_data[key]["densities"].append(d.density_percent)
        corridor_data[key]["co2"].append(d.co2_emission_kg)
        
    corridor_summary = []
    for key, val in corridor_data.items():
        corridor_summary.append({
            "corridor": key,
            "avg_vehicles": round(sum(val["counts"]) / len(val["counts"]), 1),
            "max_vehicles": max(val["counts"]),
            "avg_queue": round(sum(val["queues"]) / len(val["queues"]), 1),
            "avg_density": round(sum(val["densities"]) / len(val["densities"]), 1),
            "total_co2_kg": round(sum(val["co2"]) / 3600.0, 3)
        })

    # Peak congestion hours extraction
    hours = [d.timestamp.hour for d in detections]
    peak_hour = max(set(hours), key=hours.count)
    peak_hour_str = f"{peak_hour:02d}:00 - {peak_hour+1:02d}:00"

    # 4. Generate CSV
    if format.lower() == "csv":
        csv_data = []
        for d in detections:
            csv_data.append({
                "Timestamp": d.timestamp.isoformat(),
                "Corridor": f"{d.source}->{d.target}",
                "Vehicle Count": d.vehicle_count,
                "Queue Length": d.queue_length,
                "Density Percent": d.density_percent,
                "CO2 Emission Rate (kg/hr)": d.co2_emission_kg
            })
        df = pd.DataFrame(csv_data)
        stream = io.StringIO()
        df.to_csv(stream, index=False)
        response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
        response.headers["Content-Disposition"] = f"attachment; filename=traffic_report_{video_id}.csv"
        return response

    # 5. Generate PDF
    elif format.lower() == "pdf":
        pdf = PDFReport()
        pdf.add_page()
        pdf.set_font("helvetica", "", 10)
        
        # Meta info
        pdf.set_text_color(50, 50, 50)
        pdf.cell(100, 6, f"Video Source: {video.video_name} (ID: #{video.id})")
        pdf.cell(0, 6, f"Date Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", align="R")
        pdf.ln(6)
        pdf.cell(100, 6, f"Status: {video.status}")
        pdf.cell(0, 6, f"Total Data Points: {num_records}", align="R")
        pdf.ln(12)
        
        # Draw a beautiful section header
        pdf.set_fill_color(240, 243, 246)
        pdf.set_font("helvetica", "B", 11)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 8, "  SYSTEM-WIDE TRAFFIC METRICS", fill=True, ln=True)
        pdf.set_font("helvetica", "", 10)
        pdf.ln(3)
        
        # Grid layout for summary stats
        pdf.cell(95, 7, f"Average Vehicle Count: {avg_vehicles} (Peak: {max_vehicles})")
        pdf.cell(0, 7, f"Average Queue Length: {avg_queue} vehicles (Peak: {max_queue})")
        pdf.ln(7)
        pdf.cell(95, 7, f"Average Traffic Density: {avg_density}% (Peak: {max_density}%)")
        pdf.cell(0, 7, f"Peak Congestion Hour: {peak_hour_str}")
        pdf.ln(7)
        pdf.cell(0, 7, f"Total Carbon Emitted: {total_co2_kg} kg CO2")
        pdf.ln(14)
        
        # Corridor breakdown section header
        pdf.set_font("helvetica", "B", 11)
        pdf.cell(0, 8, "  CORRIDOR-WISE ANALYTICS BREAKDOWN", fill=True, ln=True)
        pdf.set_font("helvetica", "", 9)
        pdf.ln(4)
        
        # Table Header
        pdf.set_fill_color(6, 182, 212) # Cyan header
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("helvetica", "B", 9)
        pdf.cell(35, 7, "Corridor", border=1, fill=True, align="C")
        pdf.cell(30, 7, "Avg Vehicles", border=1, fill=True, align="C")
        pdf.cell(30, 7, "Max Vehicles", border=1, fill=True, align="C")
        pdf.cell(30, 7, "Avg Queue", border=1, fill=True, align="C")
        pdf.cell(30, 7, "Avg Density", border=1, fill=True, align="C")
        pdf.cell(35, 7, "Total CO2 (kg)", border=1, fill=True, align="C")
        pdf.ln(7)
        
        # Table Body
        pdf.set_text_color(50, 50, 50)
        pdf.set_font("helvetica", "", 9)
        for s in corridor_summary:
            pdf.cell(35, 7, s["corridor"], border=1, align="C")
            pdf.cell(30, 7, str(s["avg_vehicles"]), border=1, align="C")
            pdf.cell(30, 7, str(s["max_vehicles"]), border=1, align="C")
            pdf.cell(30, 7, str(s["avg_queue"]), border=1, align="C")
            pdf.cell(30, 7, f"{s['avg_density']}%", border=1, align="C")
            pdf.cell(35, 7, str(s["total_co2_kg"]), border=1, align="C")
            pdf.ln(7)
            
        pdf.ln(10)
        pdf.set_font("helvetica", "I", 9)
        pdf.set_text_color(100, 100, 100)
        pdf.multi_cell(0, 5, "Note: Carbon emission calculations use the CityTransit Eco-Impact Model blending vehicle speed and idling queue delays. Delay values represent queues monitored directly by YOLOv8 edge analyzers.")
        
        # Export PDF bytes
        pdf_bytes = pdf.output()
        response = StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf")
        response.headers["Content-Disposition"] = f"attachment; filename=traffic_report_{video_id}.pdf"
        return response
        
    else:
        raise HTTPException(status_code=400, detail="Invalid format parameter. Supported: pdf, csv")

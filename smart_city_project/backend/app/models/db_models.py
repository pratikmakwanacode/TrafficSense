from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class VideoFeed(Base):
    __tablename__ = "video_feeds"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    video_name = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    upload_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    status = Column(String(50), default="PROCESSING", nullable=False) # PROCESSING, COMPLETED, PENDING
    
    # Relationship to telemetry data
    detections = relationship("TrafficDetection", back_populates="video_feed", cascade="all, delete-orphan")

class TrafficDetection(Base):
    __tablename__ = "traffic_detections"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    video_id = Column(Integer, ForeignKey("video_feeds.id", ondelete="CASCADE"), nullable=False)
    source = Column(String(50), nullable=True)
    target = Column(String(50), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    vehicle_count = Column(Integer, default=0, nullable=False)
    queue_length = Column(Integer, default=0, nullable=False)
    density_percent = Column(Float, default=0.0, nullable=False)
    co2_emission_kg = Column(Float, default=0.0, nullable=False)
    
    # Back relation to video feed
    video_feed = relationship("VideoFeed", back_populates="detections")

class EmergencyClearance(Base):
    __tablename__ = "emergency_clearances"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    video_id = Column(Integer, ForeignKey("video_feeds.id", ondelete="CASCADE"), nullable=False)
    junction_id = Column(String(50), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    status = Column(String(50), default="ACTIVE", nullable=False) # ACTIVE, CLEARED

class Incident(Base):
    __tablename__ = "incidents"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    video_id = Column(Integer, ForeignKey("video_feeds.id", ondelete="CASCADE"), nullable=False)
    type = Column(String(50), nullable=False) # WRONG_SIDE, ACCIDENT
    location = Column(String(100), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)


class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    video_id = Column(Integer, ForeignKey("video_feeds.id", ondelete="CASCADE"), nullable=False)
    type = Column(String(50), nullable=False) # CONGESTION, ACCIDENT, EMERGENCY
    message = Column(String(255), nullable=False)
    junction = Column(String(50), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

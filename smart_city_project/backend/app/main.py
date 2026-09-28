import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.api import traffic, signal, route, auth, video, notifications, reports
from app.core.database import Base, engine, SessionLocal, seed_database
import app.models.db_models # Load schemas for creation

# Initialize database tables
print("[DB INIT] Synchronizing database tables...")
Base.metadata.create_all(bind=engine)

# Seed database
print("[DB INIT] Seeding default metadata...")
seed_database(SessionLocal)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="Smart City Traffic Control, Dynamic Signal Optimizer & Eco-Routing Engine"
)

# CORS Policy Config — allow local origins and dynamic local network IP addresses
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_origin_regex=r"https?://.*",  # Support any local/network client origin dynamically
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Include Routers
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["Authentication API"])
app.include_router(video.router, prefix=f"{settings.API_V1_STR}/video", tags=["Video API"])
app.include_router(traffic.router, prefix=f"{settings.API_V1_STR}/traffic", tags=["Traffic API"])
app.include_router(signal.router, prefix=f"{settings.API_V1_STR}/signal", tags=["Signal Control API"])
app.include_router(route.router, prefix=f"{settings.API_V1_STR}/route", tags=["Routing Engine API"])
app.include_router(notifications.router, prefix=f"{settings.API_V1_STR}/notifications", tags=["Notifications API"])
app.include_router(reports.router, prefix=f"{settings.API_V1_STR}/reports", tags=["Reports API"])

# Mount uploads directory to serve uploaded video files
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Mount citizen app at /app
import os
os.makedirs("static/app", exist_ok=True)
app.mount("/app", StaticFiles(directory="static/app", html=True), name="citizen_app")

# Mount React dashboard at root /
dashboard_dist = os.path.abspath("../dashboard/dist")
if os.path.exists(dashboard_dist):
    app.mount("/", StaticFiles(directory=dashboard_dist, html=True), name="dashboard")
else:
    print(f"[BACKEND WARNING] React Dashboard build directory not found at: {dashboard_dist}")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

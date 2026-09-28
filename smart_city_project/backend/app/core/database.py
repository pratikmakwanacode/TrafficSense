from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import OperationalError
from typing import Generator

# Primary MySQL connection string
MYSQL_DATABASE_URL = "mysql+pymysql://root:password@localhost:3306/smart_city_db"
# Fallback local SQLite database path
SQLITE_DATABASE_URL = "sqlite:///./smart_city.db"

Base = declarative_base()

try:
    print("[DB CONNECT] Attempting connection to MySQL server...")
    # Attempting MySQL connection with a short connection timeout
    engine = create_engine(
        MYSQL_DATABASE_URL,
        connect_args={"connect_timeout": 3}
    )
    # Test connection immediately
    with engine.connect() as conn:
        print("[DB CONNECT] MySQL connection established successfully.")
except (OperationalError, Exception) as e:
    print(f"[DB WARNING] Failed to connect to MySQL database: {e}")
    print("[DB CONNECT] Falling back to local SQLite database: smart_city.db")
    # Set up SQLite engine
    # connect_args={"check_same_thread": False} is required for SQLite in multithreaded FastAPI runs
    engine = create_engine(
        SQLITE_DATABASE_URL,
        connect_args={"check_same_thread": False}
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator:
    """
    FastAPI Dependency yielding thread-local database sessions.
    Automatically closes session after processing.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def seed_database(SessionLocal):
    """Clean the tables on startup without inserting any pre-loaded feeds."""
    from app.models.db_models import VideoFeed, TrafficDetection, EmergencyClearance, Incident, Notification
    db = SessionLocal()
    try:
        print("[DB SEED] Wiping old telemetry and video entries...")
        db.query(Notification).delete()
        db.query(Incident).delete()
        db.query(EmergencyClearance).delete()
        db.query(TrafficDetection).delete()
        db.query(VideoFeed).delete()
        db.commit()
        print("[DB SEED] Wiped successfully. No pre-loaded feeds created.")
    except Exception as e:
        print(f"[DB SEED WARNING] Could not clear tables: {e}")
    finally:
        db.close()

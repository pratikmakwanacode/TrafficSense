"""
db_check.py — Smart City Database Health Check Script
Run this standalone to verify DB connectivity and table creation.

Usage:
    cd smart_city_project/backend
    python db_check.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

print("=" * 55)
print("  Smart City — Database Health Check")
print("=" * 55)

# ── 1. Probe MySQL ────────────────────────────────────────────
import socket
mysql_available = False
try:
    sock = socket.create_connection(("localhost", 3306), timeout=2)
    sock.close()
    mysql_available = True
    print("[DB] ✅  MySQL server is REACHABLE on localhost:3306")
except OSError:
    print("[DB] ⚠️  MySQL NOT reachable on localhost:3306")
    print("[DB]     → Backend will automatically use SQLite fallback.")

# ── 2. Trigger ORM engine + table creation ────────────────────
print()
print("[DB] Initialising SQLAlchemy engine...")
try:
    from app.core.database import engine, Base
    import app.models.db_models  # registers all models with Base

    Base.metadata.create_all(bind=engine)

    dialect = engine.dialect.name
    if dialect == "mysql":
        db_url = "MySQL  →  smart_city_db @ localhost:3306"
    else:
        db_url = "SQLite →  smart_city_db.db  (local file)"

    print(f"[DB] ✅  Connected using: {db_url}")

    # ── 3. List tables ────────────────────────────────────────
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    print()
    print(f"[DB] Tables present ({len(tables)}):")
    REQUIRED = {"video_feed", "traffic_detection", "incidents"}
    for t in tables:
        flag = "✅" if t in REQUIRED else "  "
        print(f"       {flag}  {t}")

    missing = REQUIRED - set(tables)
    if missing:
        print()
        print(f"[DB] ⚠️  Missing tables: {missing}")
        print("[DB]     Running create_all again to fix...")
        Base.metadata.create_all(bind=engine)
        print("[DB] ✅  Tables created successfully.")
    else:
        print()
        print("[DB] ✅  All required tables exist. Database is ready.")

except Exception as exc:
    print(f"[DB] ❌  Error during DB initialisation: {exc}")
    sys.exit(1)

print()
print("=" * 55)
print("  Database check COMPLETE. You can now run the backend.")
print("=" * 55)

import os
import sys

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

print("--- TESTING LOGIN ---")
login_response = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
print("Login status:", login_response.status_code)
token = login_response.json().get("access_token")
print("Access token acquired:", bool(token))

if token:
    print("\n--- TESTING FORECAST API ---")
    headers = {"Authorization": f"Bearer {token}"}
    forecast_response = client.get("/api/traffic/forecast", headers=headers)
    print("Forecast status:", forecast_response.status_code)
    import pprint
    pprint.pprint(forecast_response.json())

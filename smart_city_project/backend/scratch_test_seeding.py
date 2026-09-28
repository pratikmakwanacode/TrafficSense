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
    headers = {"Authorization": f"Bearer {token}"}
    
    print("\n--- TESTING VIDEO LIST (CHECK SEEDING) ---")
    list_response = client.get("/api/video/list", headers=headers)
    print("Video list status:", list_response.status_code)
    
    import pprint
    pprint.pprint(list_response.json())

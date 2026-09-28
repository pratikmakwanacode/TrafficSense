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
    
    print("\n--- TESTING PDF REPORT DOWNLOAD ---")
    pdf_response = client.get("/api/reports/download?video_id=1&format=pdf", headers=headers)
    print("PDF status:", pdf_response.status_code)
    print("Content-Disposition:", pdf_response.headers.get("content-disposition"))
    print("Content-Type:", pdf_response.headers.get("content-type"))
    print("PDF bytes size:", len(pdf_response.content))
    
    print("\n--- TESTING CSV REPORT DOWNLOAD ---")
    csv_response = client.get("/api/reports/download?video_id=1&format=csv", headers=headers)
    print("CSV status:", csv_response.status_code)
    print("Content-Disposition:", csv_response.headers.get("content-disposition"))
    print("Content-Type:", csv_response.headers.get("content-type"))
    print("CSV content snippet:\n", csv_response.text[:250])

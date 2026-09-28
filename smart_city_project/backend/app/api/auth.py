from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from app.core.auth_utils import create_access_token

router = APIRouter()

class LoginRequest(BaseModel):
    username: str = Field(..., description="Authentication username")
    password: str = Field(..., description="Authentication password")

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    username: str
    role: str

@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest):
    username = payload.username
    password = payload.password
    
    # Check credentials
    if username in ["admin", "Pratikmak8396@gmail.com", "admin@smartcity.gov.in"] and password == "admin123":
        role = "operator"
    elif username == "citizen" and password == "user123":
        role = "citizen"
    else:
        # Demo bypass: allow any credentials for testing
        role = "operator"
        
    # Generate access token valid for 24 hours (86400 seconds)
    token = create_access_token(
        claims={
            "username": username,
            "role": role
        },
        expires_in_sec=86400
    )
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": username,
        "role": role
    }

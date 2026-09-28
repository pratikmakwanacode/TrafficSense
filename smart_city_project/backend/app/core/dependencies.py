from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.auth_utils import verify_token

# auto_error=False is critical: with True, FastAPI raises a 403 BEFORE the CORS
# middleware can attach Access-Control-Allow-Origin, causing browsers to report
# the error as "Failed to fetch" (network error) instead of an HTTP 401/403.
security = HTTPBearer(auto_error=False)

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Authorization header missing. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    claims = verify_token(credentials.credentials)
    if not claims:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return claims

def get_operator(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "operator":
        raise HTTPException(
            status_code=403, 
            detail="Forbidden: This action requires the operator role."
        )
    return user

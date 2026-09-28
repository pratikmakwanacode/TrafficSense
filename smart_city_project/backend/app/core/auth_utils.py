import base64
import json
import hmac
import hashlib
import time
from typing import Dict, Any, Optional

SECRET_KEY = "smart-city-super-secret-key-12345"

def base64url_encode(data: bytes) -> str:
    # Standard base64 encoding
    encoded = base64.b64encode(data)
    # Convert to string and apply base64url translations
    s = encoded.decode('utf-8')
    s = s.replace('+', '-').replace('/', '_').rstrip('=')
    return s

def base64url_decode(s: str) -> bytes:
    # Add back padding if missing
    padding = len(s) % 4
    if padding:
        s += '=' * (4 - padding)
    # Base64url reverse translations
    s = s.replace('-', '+').replace('_', '/')
    return base64.b64decode(s.encode('utf-8'))

def create_access_token(claims: Dict[str, Any], expires_in_sec: int = 3600) -> str:
    """
    Creates a signed JWT-like token containing the provided claims.
    """
    header = {"alg": "HS256", "typ": "JWT"}
    
    # Set expiration
    payload = claims.copy()
    payload["exp"] = int(time.time()) + expires_in_sec
    
    # Encode header and payload to JSON
    header_json = json.dumps(header, separators=(',', ':')).encode('utf-8')
    payload_json = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    
    # Base64url encode segments
    header_b64 = base64url_encode(header_json)
    payload_b64 = base64url_encode(payload_json)
    
    # Create signature input
    sig_input = f"{header_b64}.{payload_b64}".encode('utf-8')
    
    # Calculate HMAC SHA256 signature
    sig_bytes = hmac.new(SECRET_KEY.encode('utf-8'), sig_input, hashlib.sha256).digest()
    sig_b64 = base64url_encode(sig_bytes)
    
    # Assemble token
    return f"{header_b64}.{payload_b64}.{sig_b64}"

def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verifies the signature and expiration of a JWT token.
    Returns the decoded claims if valid, else None.
    """
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
            
        header_b64, payload_b64, signature_b64 = parts
        
        # Verify signature
        sig_input = f"{header_b64}.{payload_b64}".encode('utf-8')
        expected_sig_bytes = hmac.new(SECRET_KEY.encode('utf-8'), sig_input, hashlib.sha256).digest()
        expected_sig_b64 = base64url_encode(expected_sig_bytes)
        
        # Constant-time comparison to prevent timing attacks
        if not hmac.compare_digest(signature_b64, expected_sig_b64):
            return None
            
        # Decode and load claims
        payload_bytes = base64url_decode(payload_b64)
        claims = json.loads(payload_bytes.decode('utf-8'))
        
        # Verify expiration
        exp = claims.get("exp")
        if not exp or int(time.time()) > exp:
            return None  # Token expired
            
        return claims
    except Exception:
        return None

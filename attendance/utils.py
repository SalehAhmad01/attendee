import hmac
import hashlib
import time
import secrets
from math import radians, sin, cos, asin, sqrt

def generate_code_secret() -> str:
    """Generate a cryptographically secure 64-char hex secret."""
    return secrets.token_hex(32)

def current_window(rotation_seconds: int, at: float | None = None) -> int:
    """Return the time window counter based on rotation period."""
    timestamp = time.time() if at is None else at
    return int(timestamp // rotation_seconds)

def code_for_window(secret: str, window: int) -> str:
    """Compute an 8-character hex HMAC for the given secret and window."""
    digest = hmac.new(secret.encode(), str(window).encode(), hashlib.sha256).hexdigest()
    return digest[:8]

def is_code_valid(secret: str, rotation_seconds: int, code: str, at: float | None = None) -> bool:
    """
    Check if the submitted code matches the current or immediate previous time window.
    Tolerates minor network latency or clock skew.
    """
    if not code:
        return False
    now = current_window(rotation_seconds, at=at)
    valid_codes = {
        code_for_window(secret, now).lower(),
        code_for_window(secret, now - 1).lower()
    }
    return code.strip().lower() in valid_codes

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points on the Earth
    in metres using the Haversine formula.
    """
    R = 6371000.0  # Earth radius in metres
    dlat = radians(float(lat2) - float(lat1))
    dlon = radians(float(lon2) - float(lon1))
    a = sin(dlat / 2)**2 + cos(radians(float(lat1))) * cos(radians(float(lat2))) * sin(dlon / 2)**2
    return 2 * R * asin(sqrt(a))

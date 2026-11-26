import base64
import hashlib
import hmac
import json
import time
from typing import Any, Dict, Optional
from src.config import settings


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64decode(s: str) -> bytes:
    padding = "=" * (4 - (len(s) % 4)) if len(s) % 4 != 0 else ""
    return base64.urlsafe_b64decode(s + padding)


def create_access_token(user_id: int, username: str, expires_in_seconds: int = 86400) -> str:
    """Crea un token de acceso seguro y firmado digitalmente mediante HMAC-SHA256."""
    payload = {
        "sub": user_id,
        "username": username,
        "exp": int(time.time()) + expires_in_seconds,
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_b64 = _b64encode(payload_bytes)

    secret = settings.SECRET_KEY.encode("utf-8")
    signature = hmac.new(secret, payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Valida la firma criptográfica y la expiración de un token de acceso."""
    try:
        parts = token.strip().split(".")
        if len(parts) != 2:
            return None
        payload_b64, signature = parts

        secret = settings.SECRET_KEY.encode("utf-8")
        expected_sig = hmac.new(secret, payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(signature, expected_sig):
            return None

        payload_bytes = _b64decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))

        # Validar expiración
        if payload.get("exp", 0) < time.time():
            return None

        return payload
    except Exception:
        return None

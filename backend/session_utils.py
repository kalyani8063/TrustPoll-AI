import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _session_secret() -> bytes:
    secret = os.getenv("SESSION_SECRET")
    if not secret:
        raise RuntimeError("SESSION_SECRET is required")
    return secret.encode("utf-8")


def create_session_token(email: str, ttl_seconds: int = 3600) -> str:
    payload = {
        "email": email.strip().lower(),
        "exp": int(time.time()) + int(ttl_seconds),
    }
    payload_bytes = _canonical_json(payload).encode("utf-8")
    payload_part = _b64url_encode(payload_bytes)
    signature = hmac.new(_session_secret(), payload_part.encode("ascii"), hashlib.sha256).digest()
    return f"{payload_part}.{_b64url_encode(signature)}"


def verify_session_token(token: str) -> dict[str, Any]:
    try:
        payload_part, signature_part = token.split(".", 1)
    except ValueError as exc:
        raise ValueError("Invalid session token format") from exc

    expected = hmac.new(_session_secret(), payload_part.encode("ascii"), hashlib.sha256).digest()
    provided = _b64url_decode(signature_part)
    if not hmac.compare_digest(expected, provided):
        raise ValueError("Invalid session token signature")

    payload = json.loads(_b64url_decode(payload_part).decode("utf-8"))
    if int(payload.get("exp", 0)) < int(time.time()):
        raise ValueError("Session token expired")
    return payload

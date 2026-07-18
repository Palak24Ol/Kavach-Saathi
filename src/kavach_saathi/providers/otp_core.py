from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from typing import Any

from kavach_saathi.config import Settings


def otp_key(purpose: str, reference_id: str) -> str:
    return f"otp:{purpose}:{reference_id}"


def _otp_digest(jwt_secret: str, purpose: str, reference_id: str, contact: str, code: str) -> str:
    message = f"{purpose}:{reference_id}:{contact}:{code}".encode()
    return hmac.new(jwt_secret.encode(), message, hashlib.sha256).hexdigest()


def generate_otp_code() -> str:
    return f"{secrets.randbelow(900000) + 100000:06d}"


def store_otp(redis: Any, settings: Settings, *, purpose: str, reference_id: str, contact: str) -> str:
    """Generates a code and stores its digest, keyed by purpose+reference_id --
    channel-agnostic: the caller is responsible for actually delivering `code` to
    `contact` (WhatsApp, email, ...). Returns the plaintext code to send."""
    code = generate_otp_code()
    key = otp_key(purpose, reference_id)
    payload = {
        "contact": contact,
        "digest": _otp_digest(settings.jwt_secret, purpose, reference_id, contact, code),
        "attempts": 0,
    }
    redis.setex(key, settings.otp_expiry_seconds, json.dumps(payload))
    return code


def verify_otp(redis: Any, settings: Settings, *, purpose: str, reference_id: str, code: str) -> bool:
    """Channel-agnostic verification -- reads the contact stored at send time
    rather than requiring the caller to supply one, so a delivery boy (or any
    caller) can check a code without knowing whether it went out via WhatsApp or
    email."""
    if settings.allow_demo_otp and settings.otp_demo_code and code == settings.otp_demo_code:
        return True
    key = otp_key(purpose, reference_id)
    try:
        raw = redis.get(key)
        if not raw:
            return False
        payload = json.loads(raw.decode() if isinstance(raw, bytes) else raw)
        if int(payload.get("attempts", 0)) >= 5:
            return False
        contact = str(payload.get("contact", ""))
        expected = _otp_digest(settings.jwt_secret, purpose, reference_id, contact, code.strip())
        if hmac.compare_digest(str(payload.get("digest", "")), expected):
            redis.delete(key)
            return True
        payload["attempts"] = int(payload.get("attempts", 0)) + 1
        ttl = redis.ttl(key)
        if ttl and ttl > 0:
            redis.setex(key, ttl, json.dumps(payload))
        return False
    except Exception:
        return False

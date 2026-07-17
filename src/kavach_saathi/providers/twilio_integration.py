from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime
from typing import Any

from kavach_saathi.config import Settings


def normalize_phone_number(phone: str, country_code: str = "IN") -> str:
    cleaned = "".join([c for c in phone if c.isdigit() or c == "+"])
    if cleaned.startswith("+"):
        return cleaned
    calling_codes = {
        "IN": "91",
        "US": "1",
        "GB": "44",
    }
    code = calling_codes.get(country_code.upper(), "91")
    if cleaned.startswith(code) and len(cleaned) > len(code) + 5:
        return f"+{cleaned}"
    if cleaned.startswith("0"):
        cleaned = cleaned[1:]
    return f"+{code}{cleaned}"


class TwilioIntegrationClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.twilio_account_sid and self.settings.twilio_auth_token)

    def _client(self):
        from twilio.rest import Client

        return Client(self.settings.twilio_account_sid, self.settings.twilio_auth_token)

    def lookup_phone(self, phone: str, country_code: str) -> dict[str, Any]:
        normalized = normalize_phone_number(phone, country_code)

        from kavach_saathi.redis_client import get_redis

        redis_client = get_redis()
        cache_key = f"phone_lookup:{normalized}"
        try:
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

        if not self.is_configured:
            raise RuntimeError("Twilio Lookup is not configured")

        client = self._client()
        try:
            lookup = client.lookups.v2.phone_numbers(normalized).fetch(fields="line_type_intelligence")
            carrier = None
            line_type = None
            if lookup.line_type_intelligence:
                carrier = lookup.line_type_intelligence.get("carrier_name")
                line_type = lookup.line_type_intelligence.get("type")

            result = {
                "valid": lookup.valid,
                "normalized_number": lookup.phone_number,
                "country_code": lookup.country_code,
                "carrier_name": carrier,
                "line_type": line_type,
                # Lookup v2 phone-number responses have a URL but no resource SID.
                # Reading ``lookup.sid`` raised AttributeError after successful
                # validation and was previously misreported as an invalid number.
                "provider_ref": getattr(lookup, "url", None),
                "error_code": None,
                "timestamp": datetime.now(UTC).isoformat(),
            }

            if lookup.valid:
                try:
                    redis_client.setex(cache_key, 86400, json.dumps(result))
                except Exception:
                    pass
            return result
        except Exception as exc:
            # Lookup v2 represents a genuinely invalid number with a successful
            # response containing valid=false. Transport, credential, billing, and
            # programming failures must remain provider errors rather than blaming
            # the buyer's phone number.
            raise RuntimeError("Twilio Lookup is temporarily unavailable") from exc

    def start_whatsapp_verification(self, phone: str) -> str:
        if not self.is_configured or not self.settings.twilio_verify_service_sid:
            raise RuntimeError("Twilio Verify with WhatsApp is not configured")

        client = self._client()
        service_sid = self.settings.twilio_verify_service_sid
        verification = client.verify.v2.services(service_sid).verifications.create(to=phone, channel="whatsapp")
        return verification.sid

    def _otp_key(self, purpose: str, reference_id: str) -> str:
        return f"otp:{purpose}:{reference_id}"

    def _otp_digest(self, purpose: str, reference_id: str, phone: str, code: str) -> str:
        message = f"{purpose}:{reference_id}:{normalize_phone_number(phone)}:{code}".encode()
        return hmac.new(self.settings.jwt_secret.encode(), message, hashlib.sha256).hexdigest()

    def send_programmable_whatsapp_otp(self, phone: str, *, purpose: str, reference_id: str) -> str:
        """Send a test OTP through the configured WhatsApp Sandbox sender.

        Twilio Verify's WhatsApp channel requires a separately connected WhatsApp
        sender. The Sandbox is a Programmable Messaging sender, so its OTP must be
        generated and verified by this application instead of the Verify API.
        """
        if not self.is_configured or not self.settings.twilio_whatsapp_from:
            raise RuntimeError("Twilio WhatsApp Sandbox is not configured")
        from kavach_saathi.redis_client import get_redis

        normalized = normalize_phone_number(phone)
        code = f"{secrets.randbelow(900000) + 100000:06d}"
        key = self._otp_key(purpose, reference_id)
        payload = {
            "phone": normalized,
            "digest": self._otp_digest(purpose, reference_id, normalized, code),
            "attempts": 0,
        }
        redis = get_redis()
        try:
            redis.setex(key, self.settings.otp_expiry_seconds, json.dumps(payload))
            message = self._client().messages.create(
                from_=self.settings.twilio_whatsapp_from,
                to=f"whatsapp:{normalized}",
                body=f"Your Kavach Saathi {purpose} code is {code}. It expires in 5 minutes.",
            )
            return message.sid
        except Exception:
            try:
                redis.delete(key)
            except Exception:
                pass
            raise

    def check_programmable_whatsapp_otp(
        self,
        phone: str,
        code: str,
        *,
        purpose: str,
        reference_id: str,
    ) -> bool:
        if self.settings.allow_demo_otp and self.settings.otp_demo_code and code == self.settings.otp_demo_code:
            return True
        from kavach_saathi.redis_client import get_redis

        redis = get_redis()
        key = self._otp_key(purpose, reference_id)
        try:
            raw = redis.get(key)
            if not raw:
                return False
            payload = json.loads(raw.decode() if isinstance(raw, bytes) else raw)
            if payload.get("phone") != normalize_phone_number(phone) or int(payload.get("attempts", 0)) >= 5:
                return False
            expected = self._otp_digest(purpose, reference_id, phone, code.strip())
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

    def send_whatsapp_content(self, phone: str, content_sid: str, variables: dict[str, str]) -> str:
        if not self.is_configured or not self.settings.twilio_whatsapp_from:
            raise RuntimeError("Twilio WhatsApp is not configured")
        if not content_sid:
            raise RuntimeError("An approved Twilio Content template SID is required")
        message = self._client().messages.create(
            from_=self.settings.twilio_whatsapp_from,
            to=f"whatsapp:{phone}",
            content_sid=content_sid,
            content_variables=json.dumps(variables),
        )
        return message.sid

    def check_whatsapp_verification(self, phone: str, code: str) -> bool:
        # In automated tests or mock configuration, allow demo code check
        if self.settings.allow_demo_otp and self.settings.otp_demo_code and code == self.settings.otp_demo_code:
            return True

        if not self.is_configured or not self.settings.twilio_verify_service_sid:
            return False

        client = self._client()
        service_sid = self.settings.twilio_verify_service_sid
        try:
            verification_check = client.verify.v2.services(service_sid).verification_checks.create(to=phone, code=code)
            return verification_check.status == "approved"
        except Exception:
            return False

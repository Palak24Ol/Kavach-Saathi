from __future__ import annotations

import secrets
from dataclasses import dataclass

import httpx

from kavach_saathi.config import Settings

AUTHORIZE_URL = "https://digilocker.meripehchaan.gov.in/public/oauth2/1/authorize"
TOKEN_URL = "https://digilocker.meripehchaan.gov.in/public/oauth2/1/token"


class DigiLockerNotConfigured(RuntimeError):
    pass


@dataclass(slots=True)
class DigiLockerTokens:
    access_token: str
    refresh_token: str | None
    digilocker_id: str | None


def build_authorize_url(settings: Settings, *, redirect_uri: str, state: str | None = None) -> str:
    """Build the real DigiLocker OAuth2 authorization-code URL (Partner API contract).

    Requires DIGILOCKER_CLIENT_ID to be configured. This is real integration code, not a
    stub — but it needs a live client id/secret from a DigiLocker partner registration to
    actually complete a login, which is out of this project's control to provision.
    """
    if not settings.digilocker_client_id:
        raise DigiLockerNotConfigured("DIGILOCKER_CLIENT_ID is not configured")
    state = state or secrets.token_urlsafe(16)
    params = {
        "response_type": "code",
        "client_id": settings.digilocker_client_id,
        "redirect_uri": redirect_uri,
        "state": state,
    }
    query = "&".join(f"{key}={value}" for key, value in params.items())
    return f"{AUTHORIZE_URL}?{query}"


async def exchange_code(settings: Settings, *, code: str, redirect_uri: str) -> DigiLockerTokens:
    """Exchange an authorization code for tokens via the real DigiLocker token endpoint."""
    if not settings.digilocker_client_id or not settings.digilocker_client_secret:
        raise DigiLockerNotConfigured("DigiLocker client credentials are not configured")
    async with httpx.AsyncClient(timeout=settings.provider_timeout_seconds) as client:
        response = await client.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": settings.digilocker_client_id,
                "client_secret": settings.digilocker_client_secret,
                "redirect_uri": redirect_uri,
            },
        )
        response.raise_for_status()
        payload = response.json()
    return DigiLockerTokens(
        access_token=payload["access_token"],
        refresh_token=payload.get("refresh_token"),
        digilocker_id=payload.get("digilocker_id"),
    )

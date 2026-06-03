"""
WHO ICD-11 Disease Lookup — MCP Server for disease classification.

Source: icd.who.int/icdapi (free, requires OAuth2 client credentials)
Fallback: ICD-10 static data from Qdrant if API is unavailable.

Returns: disease code, title, definition, inclusions, exclusions.
"""
import logging
import httpx
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)

ICD11_API_BASE = "https://id.who.int/icd"
ICD11_SEARCH_URL = f"{ICD11_API_BASE}/entity/search"
ICD11_TOKEN_URL = "https://icdaccessmanagement.who.int/connect/token"


async def _get_access_token(timeout: float = 3.0) -> str | None:
    """
    Get OAuth2 token from WHO ICD API.

    Requires ICD_CLIENT_ID and ICD_CLIENT_SECRET in env.
    Returns None if credentials are not configured or request fails.
    """
    settings = get_settings()
    client_id = getattr(settings, "ICD_CLIENT_ID", None)
    client_secret = getattr(settings, "ICD_CLIENT_SECRET", None)

    if not client_id or not client_secret:
        return None

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.post(
                ICD11_TOKEN_URL,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "client_credentials",
                    "scope": "icdapi_access",
                },
            )
            resp.raise_for_status()
            return resp.json().get("access_token")
        except (httpx.HTTPError, KeyError) as exc:
            logger.warning("ICD-11 token fetch failed: %s", exc)
            return None


async def search_disease(query: str, lang: str = "fr", timeout: float = 3.0) -> dict[str, Any] | None:
    """
    Search for a disease in the WHO ICD-11 API.

    Falls back to None if the API is unavailable (circuit breaker handles fallback).
    """
    token = await _get_access_token(timeout=timeout)
    if not token:
        return None

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Accept-Language": lang,
        "API-Version": "v2",
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.get(
                ICD11_SEARCH_URL,
                headers=headers,
                params={
                    "q": query,
                    "subtreeFilterUsesFoundationDescendants": False,
                    "includeKeywordResult": True,
                    "flatResults": True,
                    "highlightingEnabled": False,
                },
            )
            resp.raise_for_status()
            data = resp.json()

            entities = data.get("destinationEntities", [])
            if not entities:
                return None

            top = entities[0]
            return _format_disease(top)

        except (httpx.TimeoutException, httpx.HTTPStatusError):
            return None
        except (KeyError, ValueError) as exc:
            logger.warning("ICD-11 search parse error: %s", exc)
            return None


def _format_disease(raw: dict) -> dict[str, Any]:
    """Normalize ICD-11 entity into a consistent schema."""
    return {
        "code": raw.get("theCode", ""),
        "title": raw.get("title", ""),
        "definition": raw.get("definition", ""),
        "source": "WHO ICD-11 (icd.who.int)",
    }

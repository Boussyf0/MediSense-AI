"""
ANSM Drug Lookup — MCP Server for French drug data.

Source: base-donnees-publique.medicaments.gouv.fr (Open Data)
API: REST, no authentication required, rate limit ~100 req/min

Returns: drug name, indications, contre-indications, posologie, effets secondaires.
"""
import httpx
from typing import Any

ANSM_BASE_URL = "https://base-donnees-publique.medicaments.gouv.fr"
ANSM_SEARCH_URL = f"{ANSM_BASE_URL}/extrait.php"

# Fallback to the open API endpoint
OPEN_MEDIC_URL = "https://open-medicaments.fr/api/v1/medicaments"


async def search_drug(name: str, timeout: float = 3.0) -> dict[str, Any] | None:
    """
    Search for a drug by name in the ANSM open database.

    Returns structured drug info or None if not found / timeout.
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            # Try open-medicaments API first (cleaner JSON)
            resp = await client.get(
                OPEN_MEDIC_URL,
                params={"query": name, "limit": 1, "page": 1},
            )
            resp.raise_for_status()
            data = resp.json()

            if not data:
                return None

            drug = data[0] if isinstance(data, list) else data
            return _format_drug(drug)

        except (httpx.TimeoutException, httpx.HTTPStatusError):
            return None
        except Exception:
            return None


def _format_drug(raw: dict) -> dict[str, Any]:
    """Normalize drug data into a consistent schema."""
    return {
        "name": raw.get("denomination", raw.get("nom", "Inconnu")),
        "substance": raw.get("substanceActive", raw.get("substance", "")),
        "indications": raw.get("indicationsTherapeutiques", raw.get("indications", "")),
        "contre_indications": raw.get("contreIndications", ""),
        "posologie": raw.get("posologie", ""),
        "effets_secondaires": raw.get("effetsIndesirables", raw.get("effets", "")),
        "source": "ANSM (base-donnees-publique.medicaments.gouv.fr)",
    }

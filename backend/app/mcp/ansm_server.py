"""
Morocco Drug Lookup — MCP Server for Moroccan drug data.

Primary source: medicament.ma (DMP — Direction du Médicament et de la Pharmacie, Maroc)
Schema mirrors the rramiachraf/medicaments-morocco scraper (github.com/rramiachraf/medicaments-morocco)

Returns: drug name, composition, ppv (DH), prix_hospitalier, famille,
         remboursement, distributor — all Morocco-specific fields.

Why this matters vs ANSM France:
  - Drug names differ (e.g. "Doliprane Cooper" vs "Doliprane" in France)
  - Prices are in MAD (dirhams), not euros
  - Some drugs available in France are not registered in Morocco and vice-versa
  - Reimbursement rules are AMO/CNOPS/CNSS, not CPAM
"""
import httpx
from typing import Any

# medicament.ma — official Moroccan drug registry (DMP/Ministère de la Santé)
MEDICAMENT_MA_URL = "https://medicament.ma/index.php"

# Timeout kept tight — MCP calls are in the hot path (circuit breaker handles failures)
_TIMEOUT = 4.0


async def search_drug(name: str, timeout: float = _TIMEOUT) -> dict[str, Any] | None:
    """
    Search for a drug by name in the Moroccan drug registry (medicament.ma).

    Scrapes the search results page and returns the first match with full detail.
    Returns None if not found, timeout, or site unavailable (circuit breaker handles this).
    """
    async with httpx.AsyncClient(
        timeout=timeout,
        headers={"User-Agent": "MediSense-AI/1.0 (medical information assistant)"},
        follow_redirects=True,
    ) as client:
        try:
            # Step 1: search for the drug
            resp = await client.get(
                MEDICAMENT_MA_URL,
                params={"page": "medicament", "action": "recherche", "quel": name},
            )
            resp.raise_for_status()

            drug = _parse_search_result(resp.text, name)
            return drug

        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.ConnectError):
            return None
        except Exception:
            return None


def _parse_search_result(html: str, query: str) -> dict[str, Any] | None:
    """
    Parse medicament.ma HTML search results.

    The site renders a table with columns:
    Désignation | Présentation | PPV | Prix hospitalier | Distributeur

    Returns the first result that matches the query, or None.
    """
    try:
        from html.parser import HTMLParser

        class TableParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.in_table = False
                self.rows = []
                self.current_row = []
                self.current_cell = ""
                self.in_cell = False

            def handle_starttag(self, tag, attrs):
                if tag == "tr":
                    self.current_row = []
                elif tag in ("td", "th"):
                    self.in_cell = True
                    self.current_cell = ""

            def handle_endtag(self, tag):
                if tag == "tr" and self.current_row:
                    self.rows.append(self.current_row[:])
                elif tag in ("td", "th"):
                    self.current_row.append(self.current_cell.strip())
                    self.in_cell = False

            def handle_data(self, data):
                if self.in_cell:
                    self.current_cell += data

        parser = TableParser()
        parser.feed(html)

        for row in parser.rows:
            if len(row) >= 3 and query.lower() in row[0].lower():
                return _format_drug(row, query)

        # Return first data row if no exact match
        for row in parser.rows[1:]:  # skip header
            if len(row) >= 3 and any(c.strip() for c in row):
                return _format_drug(row, query)

    except Exception:
        pass

    return None


def _format_drug(raw: list[str] | dict[str, Any], query: str | None = None) -> dict[str, Any]:
    """
    Normalize drug payloads into a consistent schema.

    Supports:
      - medicament.ma parsed rows (list[str])
      - legacy/compat dict payloads used by unit tests
    """
    query = query or ""

    if isinstance(raw, dict):
        name = raw.get("denomination") or raw.get("name") or query
        substance = (
            raw.get("substance")
            or raw.get("substanceActive")
            or raw.get("substance_active")
            or ""
        )
        indications = raw.get("indicationsTherapeutiques") or raw.get("indications") or ""
        return {
            "name": name,
            "substance": substance,
            "indications": indications,
            "source": raw.get("source", "ANSM (open-medicaments.fr)"),
        }

    row = raw
    name = row[0] if len(row) > 0 else query
    presentation = row[1] if len(row) > 1 else ""
    ppv = row[2] if len(row) > 2 else ""
    prix_hospitalier = row[3] if len(row) > 3 else ""
    distributeur = row[4] if len(row) > 4 else ""

    return {
        "name": name,
        "presentation": presentation,
        "ppv_dh": ppv,            # Prix Public de Vente en dirhams (MAD)
        "prix_hospitalier_dh": prix_hospitalier,
        "distributeur": distributeur,
        "source": "medicament.ma (DMP — Ministère de la Santé, Maroc)",
        "country": "MA",
        "currency": "MAD",
    }

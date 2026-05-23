#!/usr/bin/env python3
"""
API contract check — verifies every OpenAPI route is either wired in a frontend
or explicitly marked as intentionally unused.

Exit 0 : all routes accounted for
Exit 1 : unlinked routes detected (routes that exist in backend but have no
         frontend caller and are not listed in INTENTIONAL_NO_UI)

Usage:
  python scripts/check_api_contract.py          # checks against live OpenAPI spec
  python scripts/check_api_contract.py --dry    # prints table, never fails
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

# Routes that exist on the backend but are intentionally not called from any
# frontend.  Each entry must have a reason.
INTENTIONAL_NO_UI: dict[str, str] = {
    "POST /api/v1/chat": "superseded by POST /api/v1/chat/stream (SSE); non-streaming kept for backend-to-backend use",
    "POST /api/v1/predict/noshow": "superseded by GET /api/v1/predictions/no-show/batch used in agenda page",
    "POST /api/v1/predict/feedback": "superseded by POST /api/v1/predictions/no-show/{uuid}/feedback in agenda page",
    "POST /api/v1/admin/rerank-eval (admin/system/)": "duplicate wiring — same endpoint as admin/rerank/; minor redundancy, not a bug",
    "GET /api/v1/health": "infrastructure probe — consumed by Docker healthcheck and nginx upstreams, not by any browser UI",
    "GET /api/v1/anomalies/recent/{uuid}": "consumed by IoT monitoring page (Sprint 7) — not yet wired in frontend MVP",
    "POST /api/v1/anomalies/detect": "HTTP fallback for BiLSTM scoring — primary path is Kafka WebSocket; demo/testing use only",
}

# Patterns to search for API calls in frontend source files.
# Each tuple: (glob_pattern, regex_to_extract_path)
FRONTEND_SOURCES: list[tuple[list[str], str]] = [
    # Next.js/Axios web — api.* and refreshApi.* calls
    (["frontend/web/**/*.ts", "frontend/web/**/*.tsx"],
     r"""(?:api|refreshApi|axios)\s*\.\s*(?:get|post|patch|delete|put)\s*\(\s*[`'"](\/[^`'"\s,)]+)"""),
    # Flutter mobile — any Dio instance (dio., _dio., etc.)
    (["frontend/mobile/lib/**/*.dart"],
     r"""(?:\w+)?[Dd]io\s*\.\s*(?:get|post|patch|delete|put)\s*\(\s*'(\/[^']+)"""),
]


def _collect_frontend_calls() -> set[str]:
    """Return the set of normalized paths called by any frontend file."""
    called: set[str] = set()
    for glob_patterns, rx in FRONTEND_SOURCES:
        for glob_pattern in glob_patterns:
            for filepath in ROOT.glob(glob_pattern):
                text = filepath.read_text(encoding="utf-8", errors="ignore")
                for match in re.finditer(rx, text):
                    raw = match.group(1)
                    # Strip query string before normalizing path params
                    raw = raw.split("?")[0]
                    # Strip template-literal variable parts: /chat/${id} → /chat/{uuid}
                    normalized = re.sub(r"\$\{[^}]+\}", "{uuid}", raw)
                    normalized = re.sub(r":\w+", "{uuid}", normalized)
                    called.add(normalized.rstrip("/"))
    return called


def _fetch_openapi_routes() -> list[tuple[str, str]]:
    """Return list of (METHOD, /api/v1/path) from the backend OpenAPI spec."""
    spec_path = ROOT / "backend" / "openapi.json"
    if not spec_path.exists():
        # Try to generate it
        result = subprocess.run(
            [sys.executable, "-c",
             "from app.main import app; import json; "
             "open('openapi.json','w').write(json.dumps(app.openapi()))"],
            cwd=ROOT / "backend",
            capture_output=True, text=True,
        )
        if result.returncode != 0 or not spec_path.exists():
            print("WARNING: could not generate openapi.json — using hardcoded route list")
            return _hardcoded_routes()

    spec = json.loads(spec_path.read_text())
    routes = []
    for path, methods in spec.get("paths", {}).items():
        for method in methods:
            if method.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                routes.append((method.upper(), path))
    return routes


def _hardcoded_routes() -> list[tuple[str, str]]:
    """Fallback list derived from router.py — update when endpoints change."""
    return [
        ("POST", "/api/v1/auth/login"),
        ("POST", "/api/v1/auth/refresh"),
        ("POST", "/api/v1/auth/logout"),
        ("GET",  "/api/v1/auth/me"),
        ("GET",  "/api/v1/patients"),
        ("PATCH","/api/v1/patients/me/consent"),
        ("PATCH","/api/v1/patients/{patient_uuid}/consent"),
        ("GET",  "/api/v1/patients/{patient_uuid}/data/export"),
        ("DELETE","/api/v1/patients/{patient_uuid}"),
        ("GET",  "/api/v1/admin/users"),
        ("POST", "/api/v1/admin/users"),
        ("GET",  "/api/v1/admin/audit-logs"),
        ("POST", "/api/v1/admin/rerank-eval"),
        ("POST", "/api/v1/chat"),
        ("GET",  "/api/v1/chat"),
        ("GET",  "/api/v1/chat/{conversation_id}"),
        ("DELETE","/api/v1/chat/{conversation_id}"),
        ("POST", "/api/v1/chat/stream"),
        ("GET",  "/api/v1/doctor/patient/{patient_uuid}/dpa-summary"),
        ("PATCH","/api/v1/doctor/dpa-summary/{summary_id}/action/{action_id}"),
        ("POST", "/api/v1/doctor/dpa-summary/{summary_id}/approve"),
        ("POST", "/api/v1/doctor/dpa-summary/{summary_id}/reject"),
        ("GET",  "/api/v1/predictions/no-show/batch"),
        ("POST", "/api/v1/predictions/no-show/reminders/dispatch"),
        ("POST", "/api/v1/predictions/no-show/{appointment_uuid}/feedback"),
        ("POST", "/api/v1/predict/noshow"),
        ("POST", "/api/v1/predict/feedback"),
        ("GET",  "/api/v1/crm/tasks"),
        ("PATCH","/api/v1/crm/tasks/{appointment_uuid}"),
        ("POST", "/api/v1/crm/tasks/{appointment_uuid}/retry"),
        ("POST", "/api/v1/crm/sms/send/{appointment_uuid}"),
        ("GET",  "/api/v1/iot/vitals"),
        ("GET",  "/api/v1/iot/devices"),
        ("GET",  "/api/v1/reminders"),
        ("POST", "/api/v1/reminders"),
        ("PATCH","/api/v1/reminders/{reminder_id}"),
        ("DELETE","/api/v1/reminders/{reminder_id}"),
        ("GET",  "/api/v1/appointments"),
        ("POST", "/api/v1/appointments"),
        ("GET",  "/api/v1/doctors"),
        ("GET",  "/api/v1/health"),
        ("GET",  "/api/v1/anomalies/recent/{patient_uuid}"),
        ("POST", "/api/v1/anomalies/detect"),
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry", action="store_true", help="Print table without failing")
    args = parser.parse_args()

    frontend_calls = _collect_frontend_calls()
    backend_routes = _fetch_openapi_routes()

    rows = []
    unlinked = []

    for method, path in backend_routes:
        normalized_path = re.sub(r"\{[^}]+\}", "{uuid}", path).rstrip("/")
        key = f"{method} {path}"
        key_norm = f"{method} {normalized_path}"

        # Frontend uses paths without /api/v1 prefix (the base URL includes it).
        # Strip the prefix for matching.
        stripped = normalized_path.removeprefix("/api/v1")

        # Check if any frontend call matches (prefix or exact, with or without /api/v1)
        wired = any(
            stripped == re.sub(r"\{[^}]+\}", "{uuid}", call).rstrip("/")
            or normalized_path == re.sub(r"\{[^}]+\}", "{uuid}", call).rstrip("/")
            or stripped.startswith(re.sub(r"\{[^}]+\}", "{uuid}", call).rstrip("/"))
            for call in frontend_calls
        )

        # Check intentional N/A
        intentional = any(
            key.startswith(k.split(" (")[0]) or key_norm.startswith(k.split(" (")[0])
            for k in INTENTIONAL_NO_UI
        )

        if wired:
            status = "✅ wired"
        elif intentional:
            reason = next(
                v for k, v in INTENTIONAL_NO_UI.items()
                if key.startswith(k.split(" (")[0]) or key_norm.startswith(k.split(" (")[0])
            )
            status = f"N/A  ({reason[:60]}…)" if len(reason) > 60 else f"N/A  ({reason})"
        else:
            status = "❌ UNLINKED"
            unlinked.append(key_norm)

        rows.append((method, path, status))

    # Print table
    print(f"\n{'METHOD':<8} {'PATH':<55} STATUS")
    print("─" * 110)
    for method, path, status in sorted(rows, key=lambda r: r[2]):
        print(f"{method:<8} {path:<55} {status}")

    print(f"\n{'─'*110}")
    print(f"Total routes: {len(rows)}  |  Unlinked: {len(unlinked)}  |  Intentional N/A: {len(INTENTIONAL_NO_UI)}")

    if unlinked and not args.dry:
        print("\nFAIL — unlinked routes detected. Either:")
        print("  1. Wire them in the frontend, or")
        print("  2. Add them to INTENTIONAL_NO_UI in scripts/check_api_contract.py")
        sys.exit(1)
    elif unlinked:
        print("\n[--dry] would exit 1 in CI")
    else:
        print("\nAll routes accounted for.")


if __name__ == "__main__":
    main()

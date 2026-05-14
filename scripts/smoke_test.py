#!/usr/bin/env python3
"""
End-to-end smoke test — verifies all critical flows before demo/deploy.

Usage:
  python scripts/smoke_test.py                          # against localhost:8000
  python scripts/smoke_test.py --base https://api.medisense.ai/api/v1

Exit 0: all checks passed
Exit 1: one or more checks failed
"""
import argparse
import sys

try:
    import httpx
except ImportError:
    print("pip install httpx")
    sys.exit(1)

GREEN = "\033[92m"
RED   = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD  = "\033[1m"

results: list[tuple[str, bool, str]] = []


def check(name: str, fn):
    try:
        fn()
        results.append((name, True, ""))
        print(f"  {GREEN}✓{RESET} {name}")
    except Exception as e:
        results.append((name, False, str(e)))
        print(f"  {RED}✗{RESET} {name} — {e}")


def run_smoke(base: str, args) -> None:
    # verify=True (default) — enforce TLS cert validation in production.
    # Pass --insecure only when testing against localhost self-signed certs.
    verify = not args.insecure
    client = httpx.Client(base_url=base, timeout=10.0, verify=verify)

    print(f"\n{BOLD}MediSense AI — Smoke Test{RESET}")
    print(f"Target: {base}\n")

    # ── Health ────────────────────────────────────────────────
    print(f"{BOLD}[Health]{RESET}")
    check("GET /health → 200", lambda: client.get("/health").raise_for_status())

    # ── Auth ──────────────────────────────────────────────────
    print(f"\n{BOLD}[Auth]{RESET}")
    token = {}

    def do_login():
        r = client.post("/auth/login", json={"email": "admin@medisense.ma", "password": "Admin1234!"})
        r.raise_for_status()
        token["access"] = r.json()["access_token"]

    check("POST /auth/login → 200", do_login)

    if token:
        auth = {"Authorization": f"Bearer {token['access']}"}
        me_resp = client.get("/auth/me", headers=auth)
        check("GET /auth/me → 200", lambda: me_resp.raise_for_status())
        user_uuid = me_resp.json().get("user_uuid", "") if me_resp.is_success else ""

        # ── Admin endpoints ───────────────────────────────────
        print(f"\n{BOLD}[Admin]{RESET}")
        check("GET /admin/audit-logs → 200", lambda: client.get("/admin/audit-logs?limit=1", headers=auth).raise_for_status())
        check("GET /admin/users → 200", lambda: client.get("/admin/users", headers=auth).raise_for_status())

        # ── CRM ───────────────────────────────────────────────
        print(f"\n{BOLD}[CRM]{RESET}")
        check("GET /crm/tasks → 200", lambda: client.get("/crm/tasks", headers=auth).raise_for_status())

        # ── Predictions ───────────────────────────────────────
        print(f"\n{BOLD}[ML / Predictions]{RESET}")
        check(
            "GET /predictions/no-show/batch → 200",
            lambda: client.get(f"/predictions/no-show/batch?doctor_uuid={user_uuid}", headers=auth).raise_for_status(),
        )

        # ── Logout ────────────────────────────────────────────
        print(f"\n{BOLD}[Auth — cleanup]{RESET}")
        check("POST /auth/logout → 200", lambda: client.post("/auth/logout", headers=auth).raise_for_status())

    # ── Prometheus metrics ────────────────────────────────────
    print(f"\n{BOLD}[Monitoring]{RESET}")
    check("GET /metrics → 200 (Prometheus)", lambda: client.get("/metrics").raise_for_status())

    # ── Summary ───────────────────────────────────────────────
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    failed = [(n, e) for n, ok, e in results if not ok]

    print(f"\n{'─'*50}")
    print(f"{BOLD}Results: {passed}/{total} passed{RESET}")

    if failed:
        print(f"\n{RED}Failed checks:{RESET}")
        for name, err in failed:
            print(f"  • {name}: {err}")
        sys.exit(1)
    else:
        print(f"{GREEN}All checks passed — ready for demo!{RESET}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:8000/api/v1")
    parser.add_argument(
        "--insecure", action="store_true",
        help="Skip TLS cert verification (localhost self-signed certs only — NEVER use against production)",
    )
    args = parser.parse_args()
    run_smoke(args.base, args)


if __name__ == "__main__":
    main()

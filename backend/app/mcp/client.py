"""
MCP Client — async orchestrator with circuit breaker pattern.

Calls ANSM and ICD-11 MCP servers in parallel with Qdrant retrieval.
Implements a circuit breaker: after N consecutive failures, the MCP call
is skipped for a cooldown period. This prevents cascading timeouts from
degrading the chat experience.

Circuit breaker states:
  CLOSED  — normal operation, all calls go through
  OPEN    — too many failures, skip MCP calls for `cooldown_seconds`
  HALF-OPEN — after cooldown, allow one probe request
"""
import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from app.mcp.ansm_server import search_drug
from app.mcp.icd11_server import search_disease


@dataclass
class CircuitBreaker:
    """
    Circuit breaker for external API calls.

    States:
      CLOSED    — normal, all calls pass through
      OPEN      — too many failures, all calls skipped for cooldown_seconds
      HALF-OPEN — after cooldown, exactly ONE probe request is allowed;
                  subsequent calls are blocked until the probe resolves.
                  Success → CLOSED. Failure → OPEN (resets cooldown).
    """
    failure_threshold: int = 5
    cooldown_seconds: float = 60.0
    _failure_count: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _state: str = field(default="closed", init=False)  # closed | open | half-open
    _probe_in_flight: bool = field(default=False, init=False)

    @property
    def is_open(self) -> bool:
        if self._state == "open":
            if time.monotonic() - self._last_failure_time >= self.cooldown_seconds:
                # Transition to half-open and allow exactly one probe
                self._state = "half-open"
                self._probe_in_flight = True
                return False
            return True
        if self._state == "half-open":
            # Block all concurrent callers while the probe is in flight
            return self._probe_in_flight
        return False

    def record_success(self) -> None:
        self._failure_count = 0
        self._state = "closed"
        self._probe_in_flight = False

    def record_failure(self) -> None:
        self._last_failure_time = time.monotonic()
        if self._state == "half-open":
            # Probe failed — re-open immediately and reset cooldown
            self._failure_count = self.failure_threshold
            self._state = "open"
            self._probe_in_flight = False
            return
        self._failure_count += 1
        if self._failure_count >= self.failure_threshold:
            self._state = "open"
            self._probe_in_flight = False


# Global circuit breakers (one per MCP server)
_ansm_breaker = CircuitBreaker()
_icd11_breaker = CircuitBreaker()


async def fetch_mcp_context(
    query_fr: str,
    drug_name: str | None = None,
) -> dict[str, Any]:
    """
    Fetch live data from MCP servers in parallel.

    Returns a dict with optional 'drug' and 'disease' keys.
    If a server is down or circuit is open, that key is simply absent.
    """
    results: dict[str, Any] = {}

    async def _fetch_drug():
        if not drug_name or _ansm_breaker.is_open:
            return
        try:
            data = await search_drug(drug_name)
            if data:
                _ansm_breaker.record_success()
                results["drug"] = data
            else:
                _ansm_breaker.record_failure()
        except Exception:
            _ansm_breaker.record_failure()

    async def _fetch_disease():
        if _icd11_breaker.is_open:
            return
        try:
            data = await search_disease(query_fr)
            if data:
                _icd11_breaker.record_success()
                results["disease"] = data
            else:
                _icd11_breaker.record_failure()
        except Exception:
            _icd11_breaker.record_failure()

    # Run both in parallel — total timeout = max(individual timeouts)
    await asyncio.gather(_fetch_drug(), _fetch_disease(), return_exceptions=True)

    return results


def get_circuit_status() -> dict[str, str]:
    """Return circuit breaker states (for health check / monitoring)."""
    return {
        "ansm": _ansm_breaker._state,
        "icd11": _icd11_breaker._state,
    }

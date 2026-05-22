"""Consultation pricing — static map keyed by duration in minutes.

Kept out of the DB intentionally: prices rarely change, and a config-driven
table avoids a migration every time the clinic adjusts a tariff. If pricing
ever needs to vary per doctor/specialty, lift this into a `consultation_tariff`
table.
"""

CONSULTATION_PRICE_MAD: dict[int, int] = {
    15: 150,
    20: 200,
    30: 300,
    45: 450,
    60: 600,
}

DEFAULT_PRICE_PER_MINUTE: float = 10.0


def price_for_duration(duration_minutes: int) -> int:
    """Return MAD price for a duration; falls back to linear estimate for
    non-standard slots so the UI never shows a missing price."""
    if duration_minutes in CONSULTATION_PRICE_MAD:
        return CONSULTATION_PRICE_MAD[duration_minutes]
    return int(round(duration_minutes * DEFAULT_PRICE_PER_MINUTE))

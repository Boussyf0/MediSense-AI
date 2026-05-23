"""Tests for consultation pricing logic."""
from app.core.pricing import price_for_duration


def test_price_known_duration():
    assert price_for_duration(20) == 200


def test_price_unknown_duration_falls_back():
    assert price_for_duration(25) == 250

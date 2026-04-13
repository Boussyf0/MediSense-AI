"""
Tests for MCP servers (ANSM + ICD-11) with mocked HTTP calls.

These tests verify the MCP client logic without hitting real APIs.
"""
import pytest
from unittest.mock import AsyncMock, patch
from app.mcp.ansm_server import search_drug, _format_drug
from app.mcp.icd11_server import search_disease, _format_disease
from app.mcp.client import fetch_mcp_context, CircuitBreaker


class TestANSMServer:
    @pytest.mark.asyncio
    async def test_search_drug_returns_none_on_timeout(self):
        """ANSM server returns None on timeout."""
        with patch("app.mcp.ansm_server.httpx.AsyncClient") as mock_client:
            import httpx
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_instance.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
            mock_client.return_value = mock_instance

            result = await search_drug("paracetamol")
            assert result is None

    def test_format_drug_normalizes_data(self):
        raw = {
            "denomination": "Doliprane 500mg",
            "substanceActive": "Paracetamol",
            "indicationsTherapeutiques": "Douleurs et fievre",
        }
        result = _format_drug(raw)
        assert result["name"] == "Doliprane 500mg"
        assert result["substance"] == "Paracetamol"
        assert "ANSM" in result["source"]


class TestICD11Server:
    @pytest.mark.asyncio
    async def test_search_disease_returns_none_without_credentials(self):
        """ICD-11 returns None when API credentials are not configured."""
        result = await search_disease("cephalee")
        assert result is None

    def test_format_disease_normalizes_data(self):
        raw = {
            "theCode": "8A80",
            "title": "Migraine",
            "definition": "Recurrent headache disorder",
        }
        result = _format_disease(raw)
        assert result["code"] == "8A80"
        assert result["title"] == "Migraine"
        assert "WHO" in result["source"]


class TestMCPClient:
    @pytest.mark.asyncio
    async def test_fetch_returns_empty_on_all_failures(self):
        """If both MCP servers fail, returns empty dict."""
        with patch("app.mcp.client.search_drug", new=AsyncMock(side_effect=Exception("fail"))), \
             patch("app.mcp.client.search_disease", new=AsyncMock(side_effect=Exception("fail"))):
            result = await fetch_mcp_context("test query", drug_name="test")
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_fetch_without_drug_name_skips_ansm(self):
        """If no drug name provided, ANSM server is not called."""
        with patch("app.mcp.client.search_drug", new=AsyncMock()) as mock_drug, \
             patch("app.mcp.client.search_disease", new=AsyncMock(return_value=None)):
            result = await fetch_mcp_context("test query", drug_name=None)
            mock_drug.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetch_with_drug_calls_ansm(self):
        """If drug name provided, ANSM server is called."""
        mock_data = {"name": "Doliprane", "source": "ANSM"}
        with patch("app.mcp.client.search_drug", new=AsyncMock(return_value=mock_data)) as mock_drug, \
             patch("app.mcp.client.search_disease", new=AsyncMock(return_value=None)):
            # Reset circuit breaker
            from app.mcp.client import _ansm_breaker
            _ansm_breaker._state = "closed"
            _ansm_breaker._failure_count = 0

            result = await fetch_mcp_context("test query", drug_name="doliprane")
            assert "drug" in result

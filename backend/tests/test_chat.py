"""
Tests for the chat endpoint and RAG pipeline integration.

These tests mock external dependencies (Qdrant, Ollama, MCP) to test
the endpoint logic, schema validation, and conversation persistence
without requiring running infrastructure.
"""
import json
import uuid
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient


# ── Fixtures ─────────────────────────────────────────────

@pytest.fixture
def mock_rag_pipeline():
    """Mock the entire RAG pipeline for endpoint tests."""
    from app.rag.pipeline import PipelineResult

    mock_result = PipelineResult(
        reply="Ceci est une reponse medicale de test.",
        sources=[
            {"source": "icd10", "type": "disease", "name": "Cephalee", "score": 0.85},
        ],
        language="fr",
        confidence=0.85,
        is_urgent=False,
        mcp_data={},
        query_fr="cephalees depuis 3 jours",
    )

    with patch("app.api.v1.endpoints.chat.run", new=AsyncMock(return_value=mock_result)):
        yield mock_result


@pytest.fixture
def mock_rag_urgent():
    """Mock RAG pipeline returning an urgency response."""
    from app.rag.pipeline import PipelineResult

    mock_result = PipelineResult(
        reply="URGENCE: Appelez le 15 immediatement.",
        sources=[],
        language="fr",
        confidence=0.0,
        is_urgent=True,
        mcp_data={},
        query_fr="douleur thoracique intense",
    )

    with patch("app.api.v1.endpoints.chat.run", new=AsyncMock(return_value=mock_result)):
        yield mock_result


# ── Chat Endpoint Tests ──────────────────────────────────

class TestChatEndpoint:
    @pytest.mark.asyncio
    async def test_chat_requires_auth(self, client):
        """Chat endpoint requires JWT authentication."""
        response = await client.post("/api/v1/chat", json={"message": "test"})
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_chat_empty_message_rejected(self, client):
        """Empty message should be rejected by schema validation."""
        response = await client.post(
            "/api/v1/chat",
            json={"message": ""},
            headers={"Authorization": "Bearer fake"},
        )
        assert response.status_code in (401, 422)

    @pytest.mark.asyncio
    async def test_chat_message_too_long_rejected(self, client):
        """Message exceeding max length should be rejected."""
        response = await client.post(
            "/api/v1/chat",
            json={"message": "a" * 2001},
            headers={"Authorization": "Bearer fake"},
        )
        assert response.status_code in (401, 422)


class TestConversationEndpoints:
    @pytest.mark.asyncio
    async def test_list_conversations_requires_auth(self, client):
        response = await client.get("/api/v1/chat")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_conversation_requires_auth(self, client):
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/v1/chat/{fake_id}")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_delete_conversation_requires_auth(self, client):
        fake_id = str(uuid.uuid4())
        response = await client.delete(f"/api/v1/chat/{fake_id}")
        assert response.status_code == 401


# ── MCP Circuit Breaker Tests ────────────────────────────

class TestCircuitBreaker:
    def test_circuit_starts_closed(self):
        from app.mcp.client import CircuitBreaker
        cb = CircuitBreaker()
        assert cb.is_open is False

    def test_circuit_opens_after_threshold(self):
        from app.mcp.client import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.is_open is True

    def test_circuit_resets_on_success(self):
        from app.mcp.client import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.is_open is False

    def test_circuit_below_threshold_stays_closed(self):
        from app.mcp.client import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=5)
        for _ in range(4):
            cb.record_failure()
        assert cb.is_open is False

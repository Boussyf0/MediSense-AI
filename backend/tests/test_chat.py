"""
Tests for chat endpoints and integration wiring.
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.core.security import create_access_token
from app.db.models.conversation import Conversation
from app.db.models.patient import Patient


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _seed_patient(test_db, patient_id: str) -> None:
    patient = Patient(
        patient_uuid=uuid.UUID(patient_id),
        consent_iot=False,
        consent_nlp=False,
        consent_sharing=False,
        birth_year=1990,
        sex="F",
        city_code="75000",
    )
    test_db.add(patient)
    await test_db.flush()


def _token_for_patient(patient_id: str) -> str:
    return create_access_token(subject=patient_id, role="patient")


class TestChatEndpoint:
    @pytest.mark.asyncio
    async def test_chat_requires_auth(self, client):
        response = await client.post("/api/v1/chat", json={"message": "test"})
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_chat_empty_message_rejected(self, client):
        response = await client.post(
            "/api/v1/chat",
            json={"message": ""},
            headers={"Authorization": "Bearer fake"},
        )
        assert response.status_code in (401, 422)

    @pytest.mark.asyncio
    async def test_chat_message_too_long_rejected(self, client):
        response = await client.post(
            "/api/v1/chat",
            json={"message": "a" * 2001},
            headers={"Authorization": "Bearer fake"},
        )
        assert response.status_code in (401, 422)

    @pytest.mark.asyncio
    async def test_chat_passes_patient_context_and_merges_orchestrator_reply(self, client, test_db):
        from app.rag.pipeline import PipelineResult
        from app.agents.orchestrator import AgentResult, AgentRoute
        from app.agents.triage_agent import TriageResult, Severity

        patient_id = str(uuid.uuid4())
        await _seed_patient(test_db, patient_id)
        token = _token_for_patient(patient_id)

        pipeline_result = PipelineResult(
            reply="Réponse RAG de base.",
            sources=[{"source": "icd10", "type": "disease", "name": "Cephalee", "score": 0.85}],
            language="fr",
            confidence=0.85,
            is_urgent=False,
            mcp_data={},
            query_fr="cephalee",
        )
        agent_result = AgentResult(
            route=AgentRoute.BOOK,
            triage=TriageResult(
                severity=Severity.ROUTINE,
                reason="Consultation recommandée",
                specialist="médecine générale",
                confidence=0.9,
            ),
            chat_message="Rendez-vous proposé sous 24h.",
        )

        with patch("app.api.v1.endpoints.chat.run", new=AsyncMock(return_value=pipeline_result)) as mock_run, patch(
            "app.api.v1.endpoints.chat.run_agent_flow",
            new=AsyncMock(return_value=agent_result),
        ) as mock_orchestrator, patch(
            "app.api.v1.endpoints.chat.set_conversation_meta",
            new=AsyncMock(),
        ), patch(
            "app.api.v1.endpoints.chat._save_message",
            new=AsyncMock(
                side_effect=[
                    (uuid.uuid4(), datetime.now(timezone.utc).isoformat()),
                    (uuid.uuid4(), datetime.now(timezone.utc).isoformat()),
                ]
            ),
        ), patch(
            "app.api.v1.endpoints.chat.push_turn",
            new=AsyncMock(),
        ):
            response = await client.post(
                "/api/v1/chat",
                json={"message": "j'ai mal à la tête"},
                headers=_auth(token),
            )

        assert response.status_code == 200
        data = response.json()
        assert "Réponse RAG de base." in data["reply"]
        assert "Rendez-vous proposé sous 24h." in data["reply"]
        assert data["language"] == "fr"
        assert data["confidence"] == 0.85

        run_kwargs = mock_run.await_args.kwargs
        assert run_kwargs["patient_id"] == patient_id
        assert run_kwargs["db"] is not None

        orchestrator_kwargs = mock_orchestrator.await_args.kwargs
        assert orchestrator_kwargs["patient_id"] == patient_id
        assert orchestrator_kwargs["db"] is not None

    @pytest.mark.asyncio
    async def test_stream_passes_patient_context_to_pipeline(self, client, test_db):
        from app.agents.orchestrator import AgentResult, AgentRoute
        from app.agents.triage_agent import TriageResult, Severity

        patient_id = str(uuid.uuid4())
        await _seed_patient(test_db, patient_id)
        token = _token_for_patient(patient_id)
        captured_kwargs: dict = {}

        async def fake_run_stream(*args, **kwargs):
            captured_kwargs.update(kwargs)
            yield {"type": "lang", "value": "fr"}
            yield {"type": "sources", "value": []}
            yield {"type": "token", "value": "Bonjour"}
            yield {"type": "done", "confidence": 0.7, "is_urgent": False}

        agent_result = AgentResult(
            route=AgentRoute.INFO,
            triage=TriageResult(
                severity=Severity.INFO,
                reason="information",
                confidence=0.8,
            ),
            chat_message="",
        )

        with patch("app.api.v1.endpoints.chat.run_stream", new=fake_run_stream), patch(
            "app.api.v1.endpoints.chat.run_agent_flow",
            new=AsyncMock(return_value=agent_result),
        ), patch(
            "app.api.v1.endpoints.chat.set_conversation_meta",
            new=AsyncMock(),
        ), patch(
            "app.api.v1.endpoints.chat._save_message",
            new=AsyncMock(
                side_effect=[
                    (uuid.uuid4(), datetime.now(timezone.utc).isoformat()),
                    (uuid.uuid4(), datetime.now(timezone.utc).isoformat()),
                ]
            ),
        ), patch(
            "app.api.v1.endpoints.chat.push_turn",
            new=AsyncMock(),
        ):
            response = await client.post(
                "/api/v1/chat/stream",
                json={"message": "bonjour"},
                headers=_auth(token),
            )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
        assert "\"type\": \"done\"" in response.text
        assert "\"conversation_id\":" in response.text
        assert captured_kwargs["patient_id"] == patient_id
        assert captured_kwargs["db"] is not None


class TestConversationEndpoints:
    @pytest.mark.asyncio
    async def test_list_conversations_requires_auth(self, client):
        response = await client.get("/api/v1/chat")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_conversation_requires_auth(self, client):
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/v1/chat/{fake_id}")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_conversation_requires_auth(self, client):
        fake_id = str(uuid.uuid4())
        response = await client.delete(f"/api/v1/chat/{fake_id}")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_conversation_history_uses_cache_hit(self, client, test_db):
        patient_id = str(uuid.uuid4())
        await _seed_patient(test_db, patient_id)
        token = _token_for_patient(patient_id)

        conv = Conversation(patient_id=uuid.UUID(patient_id), language="fr")
        test_db.add(conv)
        await test_db.flush()

        now_iso = datetime.now(timezone.utc).isoformat()
        cached_turns = [
            {
                "message_id": str(uuid.uuid4()),
                "role": "user",
                "content": "bonjour",
                "context_chunks": [],
                "confidence": None,
                "created_at": now_iso,
            },
            {
                "message_id": str(uuid.uuid4()),
                "role": "assistant",
                "content": "Bonjour !",
                "context_chunks": [{"source": "icd10", "type": "disease", "name": "Cephalee", "score": 0.8}],
                "confidence": 0.8,
                "created_at": now_iso,
            },
        ]

        with patch("app.api.v1.endpoints.chat.get_turns", new=AsyncMock(return_value=cached_turns)):
            response = await client.get(
                f"/api/v1/chat/{conv.id}",
                headers=_auth(token),
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["content"] == "bonjour"
        assert data[1]["confidence"] == 0.8

    @pytest.mark.asyncio
    async def test_delete_conversation_clears_cache(self, client, test_db):
        patient_id = str(uuid.uuid4())
        await _seed_patient(test_db, patient_id)
        token = _token_for_patient(patient_id)

        conv = Conversation(patient_id=uuid.UUID(patient_id), language="fr")
        test_db.add(conv)
        await test_db.flush()

        with patch("app.api.v1.endpoints.chat.clear_conversation", new=AsyncMock()) as mock_clear:
            response = await client.delete(
                f"/api/v1/chat/{conv.id}",
                headers=_auth(token),
            )

        assert response.status_code == 204
        mock_clear.assert_awaited_once_with(str(conv.id))


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

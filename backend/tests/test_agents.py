"""
Tests for Sprint 4 Multi-Agent Orchestrator (US-14) and IoT context (US-13).

TESTING STRATEGY:
  Unit tests — no real DB or network needed.
  We mock the DB session and external calls.

  Focus areas:
    1. Triage agent severity classification (deterministic regex)
    2. IoT context escalation (critical anomaly → URGENT triage)
    3. Orchestrator routing (ESCALATE / BOOK / INFO)
    4. Circuit breaker behavior in CRM agent
    5. Timeout handling — agent timeout returns fallback, not exception
    6. Conversation cache (Redis layer — US-15)

WHY MOCK REDIS AND DB?
  These are unit tests for business logic, not integration tests.
  We verify the LOGIC of triage, routing, circuit breaker without
  needing a running Redis or PostgreSQL.
  Integration tests (real DB) are in test_chat.py which uses conftest.py.
"""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone

# ── Triage Agent ──────────────────────────────────────────────────────────────

class TestTriageAgent:
    """
    Tests for app.agents.triage_agent.

    Key insight: triage is pure regex — no async I/O.
    We test all 3 severity paths + IoT override.
    """

    @pytest.mark.asyncio
    async def test_urgent_chest_pain(self):
        """Classic cardiac emergency should always return URGENT."""
        from app.agents.triage_agent import run, Severity
        result = await run(query_fr="j'ai une douleur thoracique sévère")
        assert result.severity == Severity.URGENT
        assert result.confidence == 1.0

    @pytest.mark.asyncio
    async def test_urgent_loss_of_consciousness(self):
        from app.agents.triage_agent import run, Severity
        result = await run(query_fr="perte de connaissance soudaine")
        assert result.severity == Severity.URGENT

    @pytest.mark.asyncio
    async def test_urgent_stroke(self):
        from app.agents.triage_agent import run, Severity
        result = await run(query_fr="je pense avoir un AVC, paralysie du bras gauche")
        assert result.severity == Severity.URGENT

    @pytest.mark.asyncio
    async def test_routine_appointment_request(self):
        from app.agents.triage_agent import run, Severity
        result = await run(query_fr="je voudrais un rendez-vous pour mon suivi HTA")
        assert result.severity == Severity.ROUTINE
        assert result.specialist is not None

    @pytest.mark.asyncio
    async def test_routine_specialist_suggestion_cardio(self):
        """Cardiology keywords should suggest cardiologie specialist."""
        from app.agents.triage_agent import run, Severity
        result = await run(query_fr="consultation cardiaque pour palpitations chroniques")
        assert result.severity == Severity.ROUTINE
        assert result.specialist == "cardiologie"

    @pytest.mark.asyncio
    async def test_routine_specialist_suggestion_diabete(self):
        from app.agents.triage_agent import run, Severity
        result = await run(query_fr="renouvellement ordonnance pour mon diabète")
        assert result.severity == Severity.ROUTINE
        assert result.specialist == "endocrinologie"

    @pytest.mark.asyncio
    async def test_info_general_question(self):
        """General medical question → INFO, no appointment needed."""
        from app.agents.triage_agent import run, Severity
        result = await run(query_fr="quels sont les effets secondaires du paracetamol?")
        assert result.severity == Severity.INFO

    @pytest.mark.asyncio
    async def test_iot_critical_overrides_info_query(self):
        """
        A critical IoT anomaly should escalate to URGENT even if the patient
        asked a harmless question.

        This is the key safety property: we never ignore a critical biometric
        just because the patient's words seem benign.
        """
        from app.agents.triage_agent import run, Severity
        anomalies = [
            {"metric": "SpO2", "value": 88.0, "unit": "%", "severity": "critical"}
        ]
        result = await run(
            query_fr="je me sens un peu fatigué",
            iot_anomalies=anomalies,
        )
        assert result.severity == Severity.URGENT
        assert result.iot_triggered is True

    @pytest.mark.asyncio
    async def test_iot_moderate_does_not_override(self):
        """Moderate IoT anomaly alone should not escalate to URGENT."""
        from app.agents.triage_agent import run, Severity
        anomalies = [
            {"metric": "HR", "value": 105.0, "severity": "moderate"}
        ]
        result = await run(
            query_fr="question sur mes médicaments",
            iot_anomalies=anomalies,
        )
        # moderate → stays INFO (no urgency keywords either)
        assert result.severity == Severity.INFO
        assert result.iot_triggered is False

    @pytest.mark.asyncio
    async def test_rag_urgency_flag_respected(self):
        """is_urgent_from_rag=True should always produce URGENT."""
        from app.agents.triage_agent import run, Severity
        result = await run(
            query_fr="question anodine",
            is_urgent_from_rag=True,
        )
        assert result.severity == Severity.URGENT


# ── Orchestrator Routing ──────────────────────────────────────────────────────

class TestOrchestrator:
    """
    Tests for app.agents.orchestrator.run_agent_flow().

    We mock triage/booking/CRM agents to test the routing logic independently.
    Each test verifies:
      1. Correct AgentRoute enum value
      2. Correct chat message composition
      3. Agent outputs properly attached to AgentResult
    """

    @pytest.mark.asyncio
    async def test_urgent_route_skips_booking(self):
        """
        E2E flow: urgent triage → ESCALATE route.
        Booking agent must NOT be called (timeout would be wasted).
        """
        from app.agents.orchestrator import run_agent_flow, AgentRoute
        from app.agents.triage_agent import TriageResult, Severity
        from app.agents.crm_agent import CRMResult

        urgent_triage = TriageResult(
            severity=Severity.URGENT,
            reason="Douleur thoracique",
            confidence=1.0,
        )

        with patch("app.agents.orchestrator._triage_run", AsyncMock(return_value=urgent_triage)), \
             patch("app.agents.orchestrator._booking_run") as mock_booking, \
             patch("app.agents.orchestrator._crm_run", AsyncMock(return_value=CRMResult(sent=False, skipped=True))):

            result = await run_agent_flow(
                query_fr="douleur thoracique intense",
                patient_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                conversation_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                iot_anomalies=[],
                is_urgent_from_rag=True,
                db=None,
            )

            assert result.route == AgentRoute.ESCALATE
            assert "141" in result.chat_message
            mock_booking.assert_not_called()

    @pytest.mark.asyncio
    async def test_routine_route_calls_booking(self):
        """
        E2E flow: routine triage → BOOK route.
        Booking agent must be called with correct specialist.
        """
        from app.agents.orchestrator import run_agent_flow, AgentRoute
        from app.agents.triage_agent import TriageResult, Severity
        from app.agents.booking_agent import BookingResult
        from app.agents.crm_agent import CRMResult

        routine_triage = TriageResult(
            severity=Severity.ROUTINE,
            reason="Suivi cardiologie",
            specialist="cardiologie",
            confidence=0.9,
        )
        booking_ok = BookingResult(
            success=True,
            appointment_id="cccccccc-cccc-cccc-cccc-cccccccccccc",
            proposed_slot="2026-05-15T10:00:00+01:00",
            doctor_id="dddddddd-dddd-dddd-dddd-dddddddddddd",
            specialist_type="cardiologie",
            message="Rendez-vous proposé en cardiologie: vendredi 15 mai 2026 à 10:00.",
        )

        mock_db = AsyncMock()
        with patch("app.agents.orchestrator._triage_run", AsyncMock(return_value=routine_triage)), \
             patch("app.agents.orchestrator._booking_run", AsyncMock(return_value=booking_ok)), \
             patch("app.agents.orchestrator._crm_run", AsyncMock(return_value=CRMResult(sent=True))):

            result = await run_agent_flow(
                query_fr="je voudrais un rendez-vous cardiologue",
                patient_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                conversation_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                iot_anomalies=[],
                is_urgent_from_rag=False,
                db=mock_db,
            )

            assert result.route == AgentRoute.BOOK
            assert result.booking is not None
            assert result.booking.success is True
            assert "cardiologie" in result.chat_message

    @pytest.mark.asyncio
    async def test_info_route_no_booking(self):
        """INFO triage → INFO route, booking not called."""
        from app.agents.orchestrator import run_agent_flow, AgentRoute
        from app.agents.triage_agent import TriageResult, Severity
        from app.agents.crm_agent import CRMResult

        info_triage = TriageResult(
            severity=Severity.INFO,
            reason="Question générale",
            confidence=0.8,
        )

        with patch("app.agents.orchestrator._triage_run", AsyncMock(return_value=info_triage)), \
             patch("app.agents.orchestrator._booking_run") as mock_booking, \
             patch("app.agents.orchestrator._crm_run", AsyncMock(return_value=CRMResult(sent=False, skipped=True))):

            result = await run_agent_flow(
                query_fr="quels aliments éviter avec l'HTA?",
                patient_id=None,
                conversation_id=None,
                iot_anomalies=[],
                is_urgent_from_rag=False,
                db=None,
            )

            assert result.route == AgentRoute.INFO
            mock_booking.assert_not_called()

    @pytest.mark.asyncio
    async def test_triage_timeout_returns_info_fallback(self):
        """
        Triage timeout must NOT raise an exception — it must fall back to INFO.

        This is critical for medical use: a slow agent must never leave
        a patient with an unhandled exception.
        """
        from app.agents.orchestrator import run_agent_flow, AgentRoute

        async def slow_triage(**kwargs):
            await asyncio.sleep(10)   # longer than AGENT_TIMEOUT_S=5

        with patch("app.agents.orchestrator._triage_run", new=lambda **kw: slow_triage(**kw)), \
             patch("app.agents.orchestrator._crm_run", AsyncMock(return_value=None)):
            result = await run_agent_flow(
                query_fr="question médicale",
                patient_id=None,
                conversation_id=None,
                iot_anomalies=[],
                is_urgent_from_rag=False,
                db=None,
            )
            # Must not raise; must return INFO fallback
            assert result.route == AgentRoute.INFO
            assert len(result.errors) > 0   # timeout logged in errors

    @pytest.mark.asyncio
    async def test_iot_critical_in_orchestrator_escalates(self):
        """
        End-to-end: critical IoT anomaly passed to orchestrator → ESCALATE.
        Verifies IoT context flows from pipeline to orchestrator correctly.
        """
        from app.agents.orchestrator import run_agent_flow, AgentRoute
        from app.agents.crm_agent import CRMResult

        critical_anomalies = [
            {"metric": "SpO2", "value": 88.0, "unit": "%", "severity": "critical"}
        ]

        with patch("app.agents.orchestrator._crm_run", AsyncMock(return_value=CRMResult(sent=False))):
            result = await run_agent_flow(
                query_fr="je me sens fatigue",
                patient_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                conversation_id=None,
                iot_anomalies=critical_anomalies,
                is_urgent_from_rag=False,
                db=None,
            )
            assert result.route == AgentRoute.ESCALATE
            assert result.triage.iot_triggered is True


# ── CRM Agent Circuit Breaker ─────────────────────────────────────────────────

class TestCRMCircuitBreaker:
    """
    Tests for circuit breaker logic in app.agents.crm_agent.

    WHAT IS A CIRCUIT BREAKER?
    A design pattern (from electrical engineering) that prevents
    cascading failures. After N consecutive failures:
      - CLOSED state → OPEN: all requests rejected immediately (no timeout wait)
      - After RESET_TIMEOUT_S → HALF-OPEN: one trial request allowed
      - If trial succeeds → CLOSED again

    WHY TEST THIS?
    CRM is an external service that can go down. Without circuit breaker,
    every chat response would wait 3s for Salesforce timeout × 50 patients
    = 150 thread-seconds wasted. With circuit breaker, after 3 failures
    the CRM is bypassed instantly.
    """

    def setup_method(self):
        """Reset circuit breaker state before each test."""
        import app.services.salesforce_client as sf
        sf._cb_failures = 0
        sf._cb_open_since = None

    @pytest.mark.asyncio
    async def test_skipped_when_no_webhook_url(self):
        """No SALESFORCE_WEBHOOK_URL configured → silently skip."""
        from app.agents.crm_agent import run
        from unittest.mock import MagicMock
        mock_settings = MagicMock()
        mock_settings.SALESFORCE_WEBHOOK_URL = ""
        with patch("app.services.salesforce_client.get_settings", return_value=mock_settings):
            result = await run(
                patient_id="aaa", severity="routine",
                appointment_id=None, specialist_type=None,
                query_fr="test", iot_triggered=False,
            )
            assert result.skipped is True
            assert result.sent is False

    @pytest.mark.asyncio
    async def test_info_severity_skipped(self):
        """INFO severity never triggers CRM action."""
        from app.agents.crm_agent import run
        from unittest.mock import MagicMock
        mock_settings = MagicMock()
        mock_settings.SALESFORCE_WEBHOOK_URL = "https://sf.example.com"
        with patch("app.services.salesforce_client.get_settings", return_value=mock_settings):
            result = await run(
                patient_id="aaa", severity="info",
                appointment_id=None, specialist_type=None,
                query_fr="test", iot_triggered=False,
            )
            assert result.skipped is True

    @pytest.mark.asyncio
    async def test_circuit_opens_after_failures(self):
        """After 3 consecutive 500 errors, circuit breaker opens."""
        import app.services.salesforce_client as sf
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_settings = MagicMock()
        mock_settings.SALESFORCE_WEBHOOK_URL = "https://sf.example.com"
        mock_settings.SALESFORCE_TOKEN = ""
        mock_settings.SALESFORCE_TIMEOUT_SECONDS = 3.0

        with patch("app.services.salesforce_client.get_settings", return_value=mock_settings):
            with patch("app.services.salesforce_client.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                # 3 failures → circuit opens
                for _ in range(3):
                    await sf.send_crm_event(
                        patient_id="aaa", severity="urgent",
                        appointment_id=None, specialist_type=None,
                        query_fr="test", iot_triggered=False,
                    )

                assert sf._cb_open_since is not None

                # 4th request → rejected immediately (cb_open=True)
                result = await sf.send_crm_event(
                    patient_id="aaa", severity="urgent",
                    appointment_id=None, specialist_type=None,
                    query_fr="test", iot_triggered=False,
                )
                assert result.cb_open is True
                assert result.sent is False


# ── Redis Conversation Cache ──────────────────────────────────────────────────

class TestConversationCache:
    """
    Tests for app.core.conversation_cache (US-15).

    We mock the Redis client to test the cache layer logic without a real Redis.
    Key behaviors tested:
      1. push_turn stores data and sets TTL
      2. get_turns retrieves last N turns
      3. Failures are silently caught (never raise to caller)
      4. clear_conversation deletes both keys
    """

    @pytest.fixture
    def mock_redis_client(self):
        """Mock Redis client returned by _get_client()."""
        client = AsyncMock()
        client.rpush = AsyncMock(return_value=1)
        client.expire = AsyncMock(return_value=True)
        client.lrange = AsyncMock(return_value=[])
        client.llen = AsyncMock(return_value=0)
        client.set = AsyncMock(return_value=True)
        client.get = AsyncMock(return_value=None)
        client.delete = AsyncMock(return_value=1)
        client.aclose = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_push_turn_calls_rpush_and_expire(self, mock_redis_client):
        """push_turn must RPUSH the turn JSON and EXPIRE the key."""
        from app.core.conversation_cache import push_turn, CONVERSATION_TTL

        with patch("app.core.conversation_cache._get_client", AsyncMock(return_value=mock_redis_client)):
            await push_turn(
                conversation_id="conv-123",
                role="user",
                content="j'ai mal à la tête",
                confidence=0.85,
            )
            mock_redis_client.rpush.assert_called_once()
            # Verify TTL is set correctly
            mock_redis_client.expire.assert_called_with(
                "conversation:conv-123:turns", CONVERSATION_TTL
            )

    @pytest.mark.asyncio
    async def test_push_turn_stores_valid_json(self, mock_redis_client):
        """The value stored in Redis must be valid JSON with expected keys."""
        from app.core.conversation_cache import push_turn

        stored_json = None

        async def capture_rpush(key, value):
            nonlocal stored_json
            stored_json = value
            return 1

        mock_redis_client.rpush = capture_rpush

        with patch("app.core.conversation_cache._get_client", AsyncMock(return_value=mock_redis_client)):
            await push_turn(
                conversation_id="conv-123",
                role="assistant",
                content="Voici mon conseil médical",
                context_chunks=[{"source": "ICD-10", "score": 0.9}],
                confidence=0.82,
            )

        assert stored_json is not None
        data = json.loads(stored_json)
        assert data["role"] == "assistant"
        assert data["confidence"] == 0.82
        assert len(data["context_chunks"]) == 1

    @pytest.mark.asyncio
    async def test_get_turns_returns_parsed_turns(self, mock_redis_client):
        """get_turns must parse JSON strings from Redis LIST."""
        from app.core.conversation_cache import get_turns

        turn1 = json.dumps({"role": "user", "content": "bonjour", "context_chunks": [], "confidence": None})
        turn2 = json.dumps({"role": "assistant", "content": "Bonjour!", "context_chunks": [], "confidence": 0.9})
        mock_redis_client.lrange = AsyncMock(return_value=[turn1, turn2])

        with patch("app.core.conversation_cache._get_client", AsyncMock(return_value=mock_redis_client)):
            turns = await get_turns("conv-123", last_n=10)

        assert len(turns) == 2
        assert turns[0]["role"] == "user"
        assert turns[1]["confidence"] == 0.9

    @pytest.mark.asyncio
    async def test_redis_failure_returns_empty_silently(self):
        """
        Redis connection failure must return empty list — never raise.
        This is the key resilience property: chat works even if Redis is down.
        """
        from app.core.conversation_cache import get_turns

        with patch("app.core.conversation_cache._get_client", side_effect=ConnectionRefusedError("Redis down")):
            turns = await get_turns("conv-123")
            assert turns == []   # empty, no exception

    @pytest.mark.asyncio
    async def test_clear_conversation_deletes_both_keys(self, mock_redis_client):
        """clear_conversation must delete both turns and meta keys."""
        from app.core.conversation_cache import clear_conversation

        with patch("app.core.conversation_cache._get_client", AsyncMock(return_value=mock_redis_client)):
            await clear_conversation("conv-456")
            mock_redis_client.delete.assert_called_once_with(
                "conversation:conv-456:turns",
                "conversation:conv-456:meta",
            )


# ── IoT Context Fetcher ───────────────────────────────────────────────────────

class TestIoTContext:
    """
    Tests for app.rag.iot_context.fetch_iot_context().

    Tests the graceful degradation (no patient_id → empty),
    mock mode, and has_critical flag logic.
    """

    @pytest.mark.asyncio
    async def test_no_patient_id_returns_empty(self):
        from app.rag.iot_context import fetch_iot_context
        ctx = await fetch_iot_context(patient_id=None, db=None)
        assert ctx.is_empty
        assert ctx.has_critical is False

    @pytest.mark.asyncio
    async def test_mock_mode_returns_critical_data(self):
        """MOCK_IOT=true must return sample critical anomalies for demos."""
        from app.rag.iot_context import fetch_iot_context

        with patch.dict("os.environ", {"MOCK_IOT": "true"}):
            ctx = await fetch_iot_context(
                patient_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                db=None,
            )
            assert not ctx.is_empty
            assert ctx.has_critical is True
            assert ctx.summary_text.startswith("Données IoT")

    @pytest.mark.asyncio
    async def test_db_failure_returns_empty_silently(self):
        """DB error must return empty IoTContext — never raise."""
        from app.rag.iot_context import fetch_iot_context

        mock_db = AsyncMock()
        mock_db.execute.side_effect = Exception("DB connection lost")

        ctx = await fetch_iot_context(
            patient_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            db=mock_db,
        )
        assert ctx.is_empty
        assert ctx.has_critical is False

    @pytest.mark.asyncio
    async def test_has_critical_flag_from_db_rows(self):
        """has_critical must be True when any anomaly severity == 'critical'."""
        from app.rag.iot_context import fetch_iot_context
        from app.db.models.biometric_anomaly import BiometricAnomaly

        mock_anomaly = BiometricAnomaly()
        mock_anomaly.metric_type = "SpO2"
        mock_anomaly.value = 88.0
        mock_anomaly.threshold = 95.0
        mock_anomaly.unit = "%"
        mock_anomaly.severity = "critical"
        mock_anomaly.source = "test"
        mock_anomaly.detected_at = datetime.now(timezone.utc)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_anomaly]

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        ctx = await fetch_iot_context(
            patient_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            db=mock_db,
        )
        assert ctx.has_critical is True
        assert len(ctx.anomalies) == 1
        assert ctx.anomalies[0]["metric"] == "SpO2"


# ── Booking Agent ─────────────────────────────────────────────────────────────

class TestBookingAgent:
    """
    Unit tests for app.agents.booking_agent.

    booking_agent is always mocked out in orchestrator tests (via _booking_run
    patch), so these unit tests provide the only direct coverage of its logic.
    All tests use a mock AsyncSession — no real DB required.
    """

    def _empty_db(self):
        """Mock DB that returns empty results for all queries."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_result.fetchone.return_value = None
        mock_db.execute.return_value = mock_result
        return mock_db

    def _doctor_db(self, doctor_uuid: str):
        """Mock DB that returns one doctor row."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(doctor_uuid,)]
        mock_result.fetchone.return_value = (doctor_uuid,)
        mock_db.execute.return_value = mock_result
        return mock_db

    @pytest.mark.asyncio
    async def test_no_doctors_returns_failure(self):
        """No doctors in DB → success=False with secrétariat message."""
        from app.agents.booking_agent import run

        result = await run("patient-id", "cardiologie", self._empty_db())

        assert result.success is False
        assert "secrétariat" in result.message.lower() or "médecin" in result.message.lower()

    @pytest.mark.asyncio
    async def test_specialist_type_none_defaults_to_medecine_generale(self):
        """specialist_type=None → specialty becomes 'médecine générale'."""
        from app.agents.booking_agent import run

        result = await run("patient-id", None, self._empty_db())

        assert result.success is False
        assert result.specialist_type == "médecine générale"

    @pytest.mark.asyncio
    async def test_no_slot_returns_failure(self):
        """No free slot found → success=False with créneau message."""
        import uuid as _uuid
        from app.agents.booking_agent import run

        doctor_uuid = str(_uuid.uuid4())
        mock_db = self._doctor_db(doctor_uuid)

        with patch("app.agents.booking_agent._find_free_slot", AsyncMock(return_value=None)):
            result = await run("patient-id", "cardiologie", mock_db)

        assert result.success is False
        assert "créneau" in result.message.lower() or "secrétariat" in result.message.lower()

    @pytest.mark.asyncio
    async def test_successful_booking(self):
        """Happy path: doctor found, slot found → success=True."""
        import uuid as _uuid
        from app.agents.booking_agent import run

        doctor_uuid = str(_uuid.uuid4())
        mock_db = self._doctor_db(doctor_uuid)
        future_slot = "2027-01-15T10:00:00+00:00"

        patient_uuid = str(_uuid.uuid4())
        with patch("app.agents.booking_agent._find_free_slot", AsyncMock(return_value=future_slot)):
            result = await run(patient_uuid, "cardiologie", mock_db)

        assert result.success is True
        assert result.appointment_id is not None
        assert result.doctor_id == doctor_uuid

    @pytest.mark.asyncio
    async def test_db_exception_returns_graceful_failure(self):
        """DB exception during doctor query → success=False, no raise."""
        from app.agents.booking_agent import run

        mock_db = AsyncMock()
        mock_db.execute.side_effect = RuntimeError("connection lost")

        result = await run("patient-id", "cardiologie", mock_db)

        assert result.success is False

    @pytest.mark.asyncio
    async def test_find_free_slot_returns_next_available(self):
        """_find_free_slot returns a slot when no existing appointments."""
        from app.agents.booking_agent import _find_free_slot

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        slot = await _find_free_slot(str(MagicMock()), mock_db)
        assert slot is not None  # always finds a slot when calendar is empty

    @pytest.mark.asyncio
    async def test_fallback_to_any_doctor_when_specialty_not_found(self):
        """Specialty query returns empty but fallback finds a doctor → success=True."""
        import uuid as _uuid
        from app.agents.booking_agent import run

        patient_uuid = str(_uuid.uuid4())
        doctor_uuid = str(_uuid.uuid4())

        empty = MagicMock()
        empty.fetchall.return_value = []
        empty.fetchone.return_value = None

        fallback = MagicMock()
        fallback.fetchone.return_value = (doctor_uuid,)
        fallback.fetchall.return_value = []

        slot_res = MagicMock()
        slot_res.fetchall.return_value = []  # no booked slots → first slot free

        insert_res = MagicMock()

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [empty, fallback, slot_res, insert_res]

        result = await run(patient_uuid, "neurologie", mock_db)

        assert result.success is True
        assert result.doctor_id == doctor_uuid


class TestOrchestratorHelpers:
    """Direct unit tests for orchestrator helper functions."""

    @pytest.mark.asyncio
    async def test_run_with_timeout_general_exception_returns_fallback(self):
        """Non-TimeoutError exception in coroutine → logged and fallback returned."""
        from app.agents.orchestrator import _run_with_timeout

        async def crashing():
            raise ValueError("unexpected DB error")

        errors: list = []
        result = await _run_with_timeout(crashing(), "booking", errors, "fallback_value")

        assert result == "fallback_value"
        assert len(errors) == 1
        assert "booking_agent_error" in errors[0]

    @pytest.mark.asyncio
    async def test_routine_failed_booking_composes_fallback_message(self):
        """ROUTINE triage with failed booking → chat_message uses booking.message."""
        from app.agents.orchestrator import run_agent_flow, AgentRoute
        from app.agents.triage_agent import TriageResult, Severity
        from app.agents.booking_agent import BookingResult
        from app.agents.crm_agent import CRMResult

        routine_triage = TriageResult(
            severity=Severity.ROUTINE,
            reason="Suivi gastro",
            specialist="gastroentérologie",
            confidence=0.85,
        )
        booking_failed = BookingResult(
            success=False,
            specialist_type="gastroentérologie",
            message="Aucun créneau. Contactez le secrétariat.",
        )

        with patch("app.agents.orchestrator._triage_run", AsyncMock(return_value=routine_triage)), \
             patch("app.agents.orchestrator._booking_run", AsyncMock(return_value=booking_failed)), \
             patch("app.agents.orchestrator._crm_run", AsyncMock(return_value=CRMResult(sent=False))):
            result = await run_agent_flow(
                query_fr="douleurs abdominales",
                patient_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                conversation_id=None,
                iot_anomalies=[],
                is_urgent_from_rag=False,
                db=AsyncMock(),
            )

        assert result.route == AgentRoute.BOOK
        assert result.booking is not None
        assert result.booking.success is False
        assert "gastroentérologie" in result.chat_message

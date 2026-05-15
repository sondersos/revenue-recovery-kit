"""
Unit tests for the insights service — generate_insight().
Mocks session and AnthropicAdapter; no real I/O.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.integrations.anthropic.client import AnthropicResponse
from app.models.detection import Detection, DetectionRun, Insight
from app.services.insights.service import generate_insight, _compute_cost


ORG_ID = uuid.uuid4()
RUN_ID = uuid.uuid4()


def _make_run(status: str = "complete") -> MagicMock:
    run = MagicMock(spec=DetectionRun)
    run.id = RUN_ID
    run.organization_id = ORG_ID
    run.status = status
    run.started_at = datetime.now(tz=timezone.utc)
    return run


def _make_detection(
    rule_name: str = "stalled_invoice",
    subject_type: str = "invoice",
    amount_usd: Decimal | None = Decimal("500.00"),
    days_outstanding: int | None = 10,
) -> MagicMock:
    det = MagicMock(spec=Detection)
    det.id = uuid.uuid4()
    det.detection_run_id = RUN_ID
    det.organization_id = ORG_ID
    det.rule_name = rule_name
    det.severity = "HIGH"
    det.subject_type = subject_type
    det.subject_id = uuid.uuid4()
    det.amount_usd = amount_usd
    det.days_outstanding = days_outstanding
    det.recommended_action = "Send reminder"
    return det


def _make_session(run: MagicMock, detections: list) -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()

    run_result = MagicMock()
    run_result.scalar_one_or_none.return_value = run

    det_result = MagicMock()
    det_result.scalars.return_value.all.return_value = detections

    session.execute = AsyncMock(side_effect=[run_result, det_result])
    return session


_MOCK_RESPONSE = AnthropicResponse(
    text="Your portfolio has significant overdue exposure.",
    input_tokens=120,
    output_tokens=80,
    model="claude-sonnet-4-5-20250929",
    stop_reason="end_turn",
)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_insight_raises_if_run_not_found():
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result)

    with pytest.raises(ValueError, match="not found"):
        await generate_insight(session, RUN_ID)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_insight_raises_if_run_not_complete():
    run = _make_run(status="running")
    session = _make_session(run, [])

    with pytest.raises(ValueError, match="expected 'complete'"):
        await generate_insight(session, RUN_ID)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_insight_creates_insight_row():
    run = _make_run()
    det = _make_detection()
    session = _make_session(run, [det])

    with patch("app.services.insights.service.AnthropicAdapter") as MockAdapter:
        instance = MockAdapter.return_value
        instance.complete = AsyncMock(return_value=_MOCK_RESPONSE)
        insight = await generate_insight(session, RUN_ID)

    session.add.assert_called_once_with(insight)
    assert isinstance(insight, Insight)
    assert insight.detection_run_id == RUN_ID
    assert insight.organization_id == ORG_ID
    assert insight.summary_text == _MOCK_RESPONSE.text
    assert insight.model == _MOCK_RESPONSE.model
    assert insight.input_tokens == 120
    assert insight.output_tokens == 80


@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_insight_input_payload_contains_totals():
    run = _make_run()
    det1 = _make_detection(amount_usd=Decimal("300.00"), subject_type="invoice")
    det2 = _make_detection(amount_usd=Decimal("700.00"), subject_type="invoice")
    session = _make_session(run, [det1, det2])

    with patch("app.services.insights.service.AnthropicAdapter") as MockAdapter:
        instance = MockAdapter.return_value
        instance.complete = AsyncMock(return_value=_MOCK_RESPONSE)
        insight = await generate_insight(session, RUN_ID)

    payload = insight.input_payload
    assert payload["total_at_risk_usd"] == pytest.approx(1000.0)
    assert payload["total_detections"] == 2
    assert "stalled_invoice" in payload["rule_counts"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_insight_computes_cost():
    run = _make_run()
    session = _make_session(run, [])

    with patch("app.services.insights.service.AnthropicAdapter") as MockAdapter:
        instance = MockAdapter.return_value
        instance.complete = AsyncMock(return_value=_MOCK_RESPONSE)
        insight = await generate_insight(session, RUN_ID)

    # 120 input tokens @ $3/M + 80 output tokens @ $15/M
    expected = Decimal("120") / 1_000_000 * Decimal("3.00") + Decimal("80") / 1_000_000 * Decimal("15.00")
    assert insight.cost_usd == expected.quantize(Decimal("0.0001"))


@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_insight_does_not_commit():
    """Transaction discipline: service must not call session.commit()."""
    run = _make_run()
    session = _make_session(run, [])

    with patch("app.services.insights.service.AnthropicAdapter") as MockAdapter:
        instance = MockAdapter.return_value
        instance.complete = AsyncMock(return_value=_MOCK_RESPONSE)
        await generate_insight(session, RUN_ID)

    session.commit.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_insight_passes_model_from_settings():
    run = _make_run()
    session = _make_session(run, [])

    with patch("app.services.insights.service.AnthropicAdapter") as MockAdapter:
        instance = MockAdapter.return_value
        instance.complete = AsyncMock(return_value=_MOCK_RESPONSE)

        with patch("app.services.insights.service.settings") as mock_settings:
            mock_settings.ANTHROPIC_API_KEY = "key"
            mock_settings.ANTHROPIC_MODEL = "claude-sonnet-4-5-20250929"
            await generate_insight(session, RUN_ID)

        call_kwargs = instance.complete.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-4-5-20250929"
        assert call_kwargs["max_tokens"] == 800
        assert call_kwargs["temperature"] == pytest.approx(0.2)


# ---------------------------------------------------------------------------
# _compute_cost helper
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_compute_cost_zero_tokens():
    assert _compute_cost(0, 0) == Decimal("0.0000")


@pytest.mark.unit
def test_compute_cost_one_million_input():
    cost = _compute_cost(1_000_000, 0)
    assert cost == Decimal("3.0000")


@pytest.mark.unit
def test_compute_cost_one_million_output():
    cost = _compute_cost(0, 1_000_000)
    assert cost == Decimal("15.0000")

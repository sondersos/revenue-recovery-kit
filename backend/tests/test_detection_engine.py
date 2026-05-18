"""
Unit tests for the detection engine — run_detection(), transaction discipline.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.detection import Detection, DetectionRun
from app.services.detection.engine import run_detection


ORG_ID = uuid.uuid4()


def _make_detection(rule_name: str = "stalled_invoice") -> MagicMock:
    det = MagicMock(spec=Detection)
    det.detection_run_id = None
    det.rule_name = rule_name
    return det


def _make_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    return session


def _make_rule(name: str, detections: list) -> MagicMock:
    rule = MagicMock()
    rule.name = name
    rule.find = AsyncMock(return_value=detections)
    return rule


@pytest.mark.unit
@pytest.mark.asyncio
async def test_engine_creates_detection_run():
    session = _make_session()
    with patch("app.services.detection.engine.REGISTRY", []):
        run = await run_detection(session, ORG_ID)

    assert isinstance(run, DetectionRun)
    session.add.assert_called_once_with(run)
    session.flush.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_engine_status_complete_on_success():
    session = _make_session()
    with patch("app.services.detection.engine.REGISTRY", []):
        run = await run_detection(session, ORG_ID)

    assert run.status == "complete"
    assert run.rule_count == 0
    assert run.detection_count == 0
    assert run.finished_at is not None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_engine_bulk_inserts_detections():
    det1 = _make_detection("stalled_invoice")
    det2 = _make_detection("stale_lead")
    rule1 = _make_rule("stalled_invoice", [det1])
    rule2 = _make_rule("stale_lead", [det2])

    session = _make_session()
    with patch("app.services.detection.engine.REGISTRY", [rule1, rule2]):
        run = await run_detection(session, ORG_ID)

    assert run.detection_count == 2
    assert run.rule_count == 2
    session.add_all.assert_called_once()
    inserted = session.add_all.call_args[0][0]
    assert len(inserted) == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_engine_assigns_detection_run_id_to_each_detection():
    det = _make_detection()
    rule = _make_rule("stalled_invoice", [det])

    session = _make_session()

    # Simulate flush assigning an id to the run
    run_id = uuid.uuid4()

    async def flush_side_effect():
        # The run object passed to session.add gets an id assigned
        session.add.call_args[0][0].id = run_id

    session.flush.side_effect = flush_side_effect

    with patch("app.services.detection.engine.REGISTRY", [rule]):
        await run_detection(session, ORG_ID)

    assert det.detection_run_id == run_id


@pytest.mark.unit
@pytest.mark.asyncio
async def test_engine_never_calls_commit():
    """Transaction discipline: engine must not commit — caller owns the transaction."""
    session = _make_session()
    with patch("app.services.detection.engine.REGISTRY", []):
        await run_detection(session, ORG_ID)

    session.commit.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_engine_status_failed_on_rule_exception():
    failing_rule = _make_rule("stalled_invoice", [])
    failing_rule.find = AsyncMock(side_effect=RuntimeError("db exploded"))

    session = _make_session()
    with patch("app.services.detection.engine.REGISTRY", [failing_rule]):
        with pytest.raises(RuntimeError, match="db exploded"):
            await run_detection(session, ORG_ID)

    # The run object that was added to the session should have status='failed'
    added_run = session.add.call_args[0][0]
    assert added_run.status == "failed"
    assert "db exploded" in added_run.error_message


@pytest.mark.unit
@pytest.mark.asyncio
async def test_engine_no_add_all_when_no_detections():
    session = _make_session()
    with patch("app.services.detection.engine.REGISTRY", []):
        await run_detection(session, ORG_ID)

    session.add_all.assert_not_called()

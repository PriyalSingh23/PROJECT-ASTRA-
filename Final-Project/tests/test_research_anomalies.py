"""Tests for the Phase C "honest AI" surfaces.

Two contracts are asserted here:

* the eight-domain EW battery always reports real domains with baseline,
  observed value and drift (never an invented number); and
* the operational anomaly strip is derived from recorded rows only, and the
  consolidated endpoint answers even when the store is empty.
"""
import os
import shutil
import tempfile
import uuid

import pytest

from integration.sdr_research.service import SDRResearchService
from messaging.anomaly_service import AnomalyService
from messaging.db import get_db_session, init_db
from messaging.models import Message
from messaging.server import create_app
from messaging.service import MessagingService
from messaging.state_machine import MessageState

EW_KEYS = ["ks", "kurt", "entropy", "circ", "papr", "scf", "c42", "wvd"]
OPERATIONAL_KEYS = {
    "retry_pressure", "failed_final", "expired",
    "payload_ceiling", "latency_p95", "stuck_inflight",
}


def _fresh_db():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, f"test_anomaly_{uuid.uuid4().hex[:8]}.db")
    init_db(db_path)
    return db_path


@pytest.fixture
def client(tmp_path):
    app = create_app(db_path=str(tmp_path / "anomaly.db"))
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# EW anomaly battery
# ---------------------------------------------------------------------------
def test_ew_anomaly_report_reports_eight_domains():
    svc = SDRResearchService()
    report = svc.get_ew_anomaly_report(n_frames=16)
    assert report["provenance"] in ("LIVE_COMPUTED", "BASELINE_REPLAY")
    assert [d["key"] for d in report["domains"]] == EW_KEYS
    for domain in report["domains"]:
        assert "baseline" in domain and "observed" in domain
        assert domain["state"] in ("NOMINAL", "WATCH", "ANOMALY", "UNKNOWN")
        assert domain["tolerance"] > 0
        assert domain["tolerance_mode"] in ("abs", "rel")


def test_ew_report_is_cached_between_calls():
    svc = SDRResearchService()
    first = svc.get_ew_anomaly_report(n_frames=16)
    second = svc.get_ew_anomaly_report(n_frames=16)
    # Identical object means the expensive generator pass was served from cache.
    assert first is second


def test_model_telemetry_reports_real_checkpoint_identity():
    svc = SDRResearchService()
    telemetry = svc.get_model_telemetry()
    assert telemetry["subsystem"].startswith("LPI-CGAN")
    assert telemetry["inference_device"] == "cpu"
    if telemetry["sha256"]:  # checkpoint present in this workspace
        assert telemetry["sha256_short"].startswith(telemetry["sha256"][:8])
        assert telemetry["epoch"] == 16
        assert telemetry["manifest_verified"] is True


# ---------------------------------------------------------------------------
# Operational anomaly strip
# ---------------------------------------------------------------------------
def test_operational_anomalies_empty_store_is_nominal():
    db_path = _fresh_db()
    try:
        with get_db_session(db_path) as session:
            items = AnomalyService.operational_anomalies(session)
        assert {i["key"] for i in items} == OPERATIONAL_KEYS
        assert all(i["state"] == "NOMINAL" for i in items)
        summary = AnomalyService.summarize(items)
        assert summary["state"] == "NOMINAL"
        assert summary["counts"]["ANOMALY"] == 0
    finally:
        shutil.rmtree(os.path.dirname(db_path), ignore_errors=True)


def test_operational_anomalies_flags_retry_pressure():
    db_path = _fresh_db()
    try:
        with get_db_session(db_path) as session:
            for i in range(3):
                msg, _ = MessagingService.submit_message(
                    session=session,
                    client_idempotency_key=f"retry-{i}",
                    sender_endpoint_id="endpoint-a",
                    recipient_endpoint_id="endpoint-b",
                    payload="retry me",
                )
                session.query(Message).filter_by(message_id=msg.message_id).update(
                    {"current_state": MessageState.FAILED_RETRYABLE.value}
                )
            session.commit()

        with get_db_session(db_path) as session:
            items = {i["key"]: i for i in AnomalyService.operational_anomalies(session)}
        assert items["retry_pressure"]["observed"] == 3
        assert items["retry_pressure"]["state"] == "ANOMALY"
    finally:
        shutil.rmtree(os.path.dirname(db_path), ignore_errors=True)


def test_operational_anomalies_flags_payload_over_dmr_ceiling():
    db_path = _fresh_db()
    try:
        with get_db_session(db_path) as session:
            MessagingService.submit_message(
                session=session,
                client_idempotency_key="big-1",
                sender_endpoint_id="endpoint-a",
                recipient_endpoint_id="endpoint-b",
                payload="X" * 400,
            )
        with get_db_session(db_path) as session:
            items = {i["key"]: i for i in AnomalyService.operational_anomalies(session)}
        assert items["payload_ceiling"]["observed"] == 1
        assert items["payload_ceiling"]["state"] == "WATCH"
    finally:
        shutil.rmtree(os.path.dirname(db_path), ignore_errors=True)


def test_summarize_rolls_worst_state_to_the_top():
    groups = [
        [{"state": "NOMINAL"}, {"state": "WATCH"}],
        [{"state": "ANOMALY"}],
    ]
    summary = AnomalyService.summarize(*groups)
    assert summary["state"] == "ANOMALY"
    assert summary["counts"] == {"NOMINAL": 1, "WATCH": 1, "ANOMALY": 1, "UNKNOWN": 0}


# ---------------------------------------------------------------------------
# Consolidated endpoint
# ---------------------------------------------------------------------------
def test_anomalies_endpoint_always_answers(client):
    res = client.get("/api/v1/research/anomalies?frames=16")
    assert res.status_code == 200
    body = res.get_json()
    assert len(body["domains"]) == 8
    assert len(body["operational"]) == 6
    assert body["summary"]["total"] == 14
    assert body["provenance"] in ("LIVE_COMPUTED", "BASELINE_REPLAY")
    assert body["summary"]["state"] in ("NOMINAL", "WATCH", "ANOMALY", "UNKNOWN")
    assert body["model"]["subsystem"].startswith("LPI-CGAN")
    assert "generated_at" in body


def test_anomalies_endpoint_survives_bad_frames_param(client):
    res = client.get("/api/v1/research/anomalies?frames=not-a-number")
    assert res.status_code == 200
    assert len(res.get_json()["domains"]) == 8

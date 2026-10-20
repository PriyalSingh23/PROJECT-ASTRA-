"""Tests for the Motorola hardware bridge (PDU codec + safety gating)."""
import os

import pytest

from integration.motorola.hardware_bridge import (
    DMR_MAX_PAYLOAD_BYTES,
    MotorolaHardwareBridge,
    build_tms_pdu,
    parse_tms_pdu,
)
from integration.motorola.adapter import MotorolaMOTOTRBOAdapter


def test_tms_pdu_roundtrip():
    payload = b"SHADOWCOMM-FIELD-TEST"
    frame = build_tms_pdu(b"\x2a", payload)
    decoded = parse_tms_pdu(frame)
    assert decoded["payload"] == payload
    assert decoded["radio_lo"] == 0x2A
    assert decoded["length"] == len(payload)


def test_tms_pdu_rejects_oversize():
    with pytest.raises(ValueError):
        build_tms_pdu(b"\x01", b"x" * (DMR_MAX_PAYLOAD_BYTES + 1))


def test_tms_pdu_detects_corruption():
    frame = bytearray(build_tms_pdu(b"\x01", b"hello"))
    frame[-1] ^= 0xFF  # flip a payload bit
    with pytest.raises(ValueError):
        parse_tms_pdu(bytes(frame))


def test_bridge_dry_run_when_not_approved(monkeypatch):
    monkeypatch.delenv("MOTOROLA_RADIO_APPROVED", raising=False)
    bridge = MotorolaHardwareBridge(backend="mnis_udp")
    assert bridge.approved() is False
    res = bridge.transmit("endpoint-b", b"hello-field")
    assert res["success"] is True
    assert res["dry_run"] is True
    assert res["bytes_on_wire"] > len(b"hello-field")  # framing overhead added


def test_bridge_rejects_oversize_payload():
    bridge = MotorolaHardwareBridge(backend="mnis_udp")
    res = bridge.transmit("endpoint-b", b"x" * (DMR_MAX_PAYLOAD_BYTES + 1))
    assert res["success"] is False
    assert res["error_code"] == "PAYLOAD_TOO_LARGE"


def test_adapter_stays_simulated_without_approval(monkeypatch):
    monkeypatch.delenv("MOTOROLA_RADIO_APPROVED", raising=False)
    adapter = MotorolaMOTOTRBOAdapter()
    res = adapter.send("endpoint-b", b"simulated", {})
    assert res["success"] is True
    assert res["error_code"] is None
    assert "simulated" in res["details"]
    # Probe must never raise and must report approval status.
    probe = adapter.bridge_probe()
    assert "approved" in probe and probe["approved"] is False


def test_adapter_uses_bridge_when_approved(monkeypatch):
    monkeypatch.setenv("MOTOROLA_RADIO_APPROVED", "true")
    adapter = MotorolaMOTOTRBOAdapter()
    res = adapter.send("endpoint-b", b"approved-dispatch", {})
    # No MNIS/GPIO present in CI, so this exercises the bridge path and its
    # either-dry-run-or-error contract without ever crashing.
    assert "backend" in res
    assert res["error_code"] in (None, "MNIS_TX_ERROR", "GPIO_UNAVAILABLE", "GPIO_TX_ERROR")

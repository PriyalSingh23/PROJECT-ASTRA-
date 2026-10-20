import torch
import os
import pytest
from messaging.server import create_app
from integration.workstation_service import workstation_service


@pytest.fixture
def client(tmp_path):
    test_db = str(tmp_path / "test_workstation.db")
    app = create_app(db_path=test_db)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_sdr_hardware_probe():
    probe = workstation_service.probe_sdr_hardware()
    assert "driver_installed" in probe
    assert "driver_version" in probe
    assert "device_connected" in probe
    assert "operating_mode" in probe
    assert probe["center_freq_hz"] == 2484000000.0
    assert probe["sample_rate_sps"] == 245760.0
    assert probe["operating_mode"] in ["SIMULATION_BENCH", "LIVE_SDR_HARDWARE"]


def test_mission_overview():
    overview = workstation_service.get_mission_overview()
    assert overview["system_name"] == "ASTRA"
    assert "system_state" in overview
    assert "sdr_hardware" in overview
    assert "model_status" in overview
    assert "crypto_status" in overview
    assert "stealth_summary" in overview
    assert overview["stealth_summary"]["adv_acc"] <= 60.0


def test_transmitter_prepare_and_generate():
    prep = workstation_service.prepare_transmitter_payload("ALPHA_BURST_TEST_42", msg_type="TACTICAL")
    assert prep["raw_bytes_count"] > 0
    assert prep["crypto_envelope"]["envelope_bytes"] == prep["raw_bytes_count"] + 28
    assert prep["error_correction"]["total_codeword_bytes"] >= prep["crypto_envelope"]["envelope_bytes"]
    assert prep["rf_budget"]["burst_airtime_ms"] > 0

    gen = workstation_service.generate_waveform_burst(text="ALPHA_BURST_TEST_42")
    assert gen["samples_total"] > 0
    assert "peak_amplitude" in gen
    assert "papr_db" in gen
    assert len(gen["constellation_preview"]) > 0


def test_transmitter_safety_lockout():
    # Without confirmation, transmission must be rejected
    fail_res = workstation_service.execute_transmission(
        text="TEST_TRANSMISSION",
        mode="SIMULATION",
        confirm=False,
    )
    assert fail_res["success"] is False
    assert fail_res["error"] == "OPERATOR_CONFIRMATION_REQUIRED"

    # With confirmation, transmission succeeds
    ok_res = workstation_service.execute_transmission(
        text="TEST_TRANSMISSION",
        mode="SIMULATION",
        confirm=True,
    )
    assert ok_res["success"] is True
    assert ok_res["status"] == "TRANSMISSION_COMPLETE"
    assert ok_res["samples_transmitted"] > 0


def test_receiver_dsp_pipeline():
    result = workstation_service.execute_receiver_dsp_pipeline(mode="SIMULATION", target_snr_db=8.0)
    assert result["recovery_status"] == "SUCCESS_VERIFIED"
    assert result["total_duration_ms"] > 0
    assert len(result["stages"]) == 14
    assert result["stages"][0]["stage_id"] == 1
    assert result["stages"][-1]["stage_id"] == 14
    assert result["recovered_plaintext"] != ""


def test_channel_simulation():
    res = workstation_service.simulate_channel(target_snr_db=6.0, cfo_hz=40.0, phase_offset_deg=15.0, multipath=True)
    assert res["channel_parameters"]["target_snr_db"] == 6.0
    assert "measured_snr_db" in res["channel_parameters"]
    assert "clean_waveform_preview" in res
    assert "distorted_waveform_preview" in res
    assert len(res["clean_waveform_preview"]) > 0


def test_signal_intelligence():
    sig = workstation_service.get_signal_intelligence_data()
    assert "time_domain" in sig
    assert "frequency_spectrum" in sig
    assert "spectrogram" in sig
    assert "autocorrelation" in sig
    assert "statistics" in sig
    assert sig["provenance"]["source"] == "LPI_CGAN_NEURAL_SYNTHESIS"


def test_api_workstation_endpoints(client):
    # Test GET /api/v1/workstation/overview
    res = client.get("/api/v1/workstation/overview")
    assert res.status_code == 200
    data = res.get_json()
    assert data["system_name"] == "ASTRA"

    # Test GET /api/v1/workstation/sdr-status
    res = client.get("/api/v1/workstation/sdr-status")
    assert res.status_code == 200

    # Test POST /api/v1/workstation/transmitter/prepare
    res = client.post("/api/v1/workstation/transmitter/prepare", json={"text": "HELLO_ASTRA"})
    assert res.status_code == 200
    assert res.get_json()["raw_bytes_count"] > 0

    # Test POST /api/v1/workstation/receiver/capture
    res = client.post("/api/v1/workstation/receiver/capture", json={"mode": "SIMULATION", "target_snr_db": 6.0})
    assert res.status_code == 200
    assert res.get_json()["recovery_status"] == "SUCCESS_VERIFIED"

    # Test GET /api/v1/workstation/signal/analysis
    res = client.get("/api/v1/workstation/signal/analysis")
    assert res.status_code == 200
    assert len(res.get_json()["time_domain"]) > 0

    # Test GET /api/v1/workstation/diagnostics
    res = client.get("/api/v1/workstation/diagnostics")
    assert res.status_code == 200
    assert "pytorch_backend" in res.get_json()

    # Test GET /api/v1/workstation/experiments
    res = client.get("/api/v1/workstation/experiments")
    assert res.status_code == 200
    assert "current_evaluation" in res.get_json()

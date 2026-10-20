import torch
import os
import pytest
import numpy as np
from messaging.server import create_app
from integration.workstation_service import workstation_service
from integration.sdr_research.service import SDRResearchService


@pytest.fixture
def client(tmp_path):
    test_db = str(tmp_path / "test_presentation.db")
    app = create_app(db_path=test_db)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_presentation_mode_hardware_connected():
    """Verify presentation mode behavior when Ettus USRP B205mini hardware is connected."""
    orig_probe = workstation_service.probe_sdr_hardware
    workstation_service.probe_sdr_hardware = lambda: {
        "driver_installed": True,
        "driver_version": "UHD_4.7.0.0",
        "device_connected": True,
        "device_count": 1,
        "devices": ["Ettus USRP B205mini-i (Serial: 3125B6C)"],
        "operating_mode": "SDR_HARDWARE",
        "center_freq_hz": 2484000000.0,
        "sample_rate_sps": 245760.0,
        "decimation_ratio": 407,
        "master_clock_hz": 100000000.0,
        "tx_gain_db": 45.0,
        "rx_gain_db": 30.0,
    }
    try:
        data = workstation_service.get_signal_intelligence_data(source="LIVE_SDR", fft_size=256)
        assert data["status"] == "ONLINE"
        assert data["provenance"]["is_calibrated_rf"] is True
        assert data["provenance"]["units"]["power"] == "dBm"
        assert data["provenance"]["units"]["amplitude"] == "V"
        assert "CALIBRATED RF HARDWARE (dBm)" in data["provenance"]["calibration_badge"]
        assert "LIVE SDR" in data["provenance"]["source_label"]
        assert len(data["time_domain"]) > 0
        assert len(data["frequency_spectrum"]) == 256
        assert len(data["constellation"]) > 0
        assert len(data["autocorrelation"]) == 32
        assert len(data["spectrogram"]) > 0
        assert data["statistics"]["sample_rate_sps"] == 245760.0
        assert data["statistics"]["center_freq_hz"] == 2484000000.0
    finally:
        workstation_service.probe_sdr_hardware = orig_probe


def test_presentation_mode_hardware_disconnected_fallback():
    """Verify that when USRP hardware is absent, presentation mode displays recorded laboratory baseline."""
    orig_probe = workstation_service.probe_sdr_hardware
    workstation_service.probe_sdr_hardware = lambda: {
        "driver_installed": True,
        "driver_version": "UHD_4.7.0.0",
        "device_connected": False,
        "device_count": 0,
        "devices": [],
        "operating_mode": "DISCONNECTED",
        "center_freq_hz": 2484000000.0,
        "sample_rate_sps": 245760.0,
        "decimation_ratio": 407,
        "master_clock_hz": 100000000.0,
        "tx_gain_db": 0.0,
        "rx_gain_db": 0.0,
    }
    try:
        data = workstation_service.get_signal_intelligence_data(source="LIVE_SDR", fft_size=256)
        # Status must explicitly reflect disconnection
        assert data["status"] == "HARDWARE_DISCONNECTED"
        # Must not fabricate calibrated RF measurements
        assert data["provenance"]["is_calibrated_rf"] is False
        assert data["fallback_source"] == "RECORDED_IQ"
        assert "RECORDED" in data["provenance"]["source_label"] or "FALLBACK" in data["provenance"]["source_label"]
        # Prominent warning and notes
        assert "USRP B205mini not detected" in data["warning"]
        assert "RECORDED LABORATORY BASELINE" in data["warning"]
        # Authentic valid waveform points are still available for presentation display
        assert len(data["time_domain"]) > 0
        assert len(data["frequency_spectrum"]) == 256
        assert len(data["constellation"]) > 0
        assert len(data["spectrogram"]) > 0
        assert data["statistics"]["peak_amplitude"] > 0
    finally:
        workstation_service.probe_sdr_hardware = orig_probe


def test_presentation_mode_recorded_iq_replay():
    """Verify recorded IQ dataset loading and provenance for presentation replay."""
    data = workstation_service.get_signal_intelligence_data(source="RECORDED_IQ", fft_size=512)
    assert data["status"] == "ONLINE"
    assert data["provenance"]["is_calibrated_rf"] is False
    assert data["provenance"]["units"]["power"] == "dBFS"
    assert "RECORDED_IQ" in data["provenance"]["source"]
    assert len(data["frequency_spectrum"]) == 512
    assert "file_metadata" in data["provenance"]
    assert data["provenance"]["file_metadata"] is not None


def test_empirical_evaluation_report_accuracy():
    """Verify that empirical research results are loaded from eval.json without fabricated data."""
    svc = SDRResearchService()
    report = svc.get_evaluation_report()
    assert report["has_report"] is True

    stealth = report["stealth"]
    # Verify verified research numbers from IEEE GCON / Elsevier paper experiments
    assert abs(stealth["ks_p"] - 0.8647) < 0.01
    assert abs(stealth["kurt"] - 2.9907) < 0.01
    assert abs(stealth["adv_acc"] - 55.9) < 0.2  # Blind/sub-noise chance detection range
    assert stealth["n_pass"] == 8

    # Verify SNR breakdown
    link_snrs = report["link_snrs"]
    assert len(link_snrs) >= 3
    snr_map = {row["snr_db"]: row for row in link_snrs}
    assert 2.0 in snr_map
    assert 6.0 in snr_map
    assert 10.0 in snr_map

    # At 6 dB and 10 dB, field BER and FER should be near zero / zero
    assert snr_map[6.0]["field_ber"] < 0.001  # Empirical 3e-5
    assert snr_map[10.0]["field_ber"] == 0.0
    assert snr_map[10.0]["fer"] == 0.0


def test_workstation_overview_and_real_event_log():
    """Verify workstation overview provides real status, warnings, and event audit stream."""
    overview = workstation_service.get_mission_overview()
    assert "system_state" in overview
    assert "sdr_hardware" in overview
    assert "model_status" in overview
    assert "crypto_status" in overview
    assert "stealth_summary" in overview
    assert "recent_events" in overview

    events = overview["recent_events"]
    assert isinstance(events, list)
    assert len(events) > 0
    first_event = events[0]
    assert "timestamp" in first_event
    assert "level" in first_event
    assert "source" in first_event
    assert "message" in first_event


def test_presentation_mode_api_routes(client):
    """Verify API endpoints used by Presentation Mode return 200 OK with correct schemas."""
    # 1. Signal intelligence
    sig_res = client.get("/api/v1/workstation/signal/analysis?source=RECORDED_IQ")
    assert sig_res.status_code == 200
    assert "time_domain" in sig_res.get_json()

    # 2. Research evaluation
    eval_res = client.get("/api/v1/research/evaluation")
    assert eval_res.status_code == 200
    assert eval_res.get_json()["has_report"] is True

    # 3. System diagnostics
    diag_res = client.get("/api/v1/workstation/diagnostics")
    assert diag_res.status_code == 200
    assert "sdr_hardware" in diag_res.get_json()

    # 4. Workstation overview
    over_res = client.get("/api/v1/workstation/overview")
    assert over_res.status_code == 200
    assert "recent_events" in over_res.get_json()

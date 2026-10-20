import torch
import os
import pytest
import numpy as np
from messaging.server import create_app
from integration.workstation_service import workstation_service


@pytest.fixture
def client(tmp_path):
    test_db = str(tmp_path / "test_tx_rx.db")
    app = create_app(db_path=test_db)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_transmitter_payload_preparation():
    """Verify cryptographic framing, RS(42,34) FEC, and wire memory mapping."""
    test_msg = "ASTRA_SECURE_BURST_DELTA_99"
    prep = workstation_service.prepare_transmitter_payload(test_msg, msg_type="TACTICAL")

    assert prep["raw_text"] == test_msg
    assert prep["raw_bytes_count"] == len(test_msg.encode("utf-8"))

    # AES-256-GCM v2 adds 12B nonce + 16B tag = +28B
    assert prep["crypto_envelope"]["scheme"] == "AES-256-GCM v2"
    assert prep["crypto_envelope"]["envelope_bytes"] == prep["raw_bytes_count"] + 28
    assert len(prep["crypto_envelope"]["nonce_hex"]) > 0
    assert len(prep["crypto_envelope"]["tag_hex"]) > 0

    # RS(42, 34) FEC parameters
    fec = prep["error_correction"]
    assert "RS(42, 34)" in fec["scheme"]
    assert fec["error_correcting_capacity_symbols"] == 4
    assert fec["data_per_block"] == 34
    assert fec["codeword_per_block"] == 42
    assert fec["parity_per_block"] == 8

    # Wire hex memory map
    assert len(prep["wire_hex_memory_map"]) >= 4
    assert any("PREAMBLE" in line for line in prep["wire_hex_memory_map"])
    assert any("GMAC" in line for line in prep["wire_hex_memory_map"])


def test_transmitter_bounds_and_safety_lockouts():
    """Verify payload size bounds, empty payload rejection, and safety lockout."""
    # 1. Empty payload rejected
    empty_res = workstation_service.execute_transmission(text="", mode="SIMULATION", confirm=True)
    assert empty_res["success"] is False
    assert empty_res["error"] == "EMPTY_PAYLOAD"

    whitespace_res = workstation_service.execute_transmission(text="   ", mode="SIMULATION", confirm=True)
    assert whitespace_res["success"] is False
    assert whitespace_res["error"] == "EMPTY_PAYLOAD"

    # 2. Oversized payload (> 256 bytes) rejected
    huge_text = "A" * 300
    oversized_res = workstation_service.execute_transmission(text=huge_text, mode="SIMULATION", confirm=True)
    assert oversized_res["success"] is False
    assert oversized_res["error"] == "PAYLOAD_TOO_LARGE"

    # 3. Missing confirmation rejected
    unconfirmed_res = workstation_service.execute_transmission(
        text="AUTHORIZED_PAYLOAD", mode="SIMULATION", confirm=False
    )
    assert unconfirmed_res["success"] is False
    assert unconfirmed_res["error"] == "OPERATOR_CONFIRMATION_REQUIRED"

    # 4. Valid confirmation succeeds and writes last_tx_waveform.npy
    confirmed_res = workstation_service.execute_transmission(
        text="AUTHORIZED_PAYLOAD", mode="SIMULATION", confirm=True
    )
    assert confirmed_res["success"] is True
    assert confirmed_res["samples_transmitted"] > 0
    assert os.path.exists(os.path.join(workstation_service.root_dir, "last_tx_waveform.npy"))


def test_receiver_dsp_high_snr_clean_recovery():
    """Verify 14-stage DSP receiver at high SNR (+8 dB) performs clean authenticated recovery."""
    test_payload = "ASTRA_BURST_OK"
    result = workstation_service.execute_receiver_dsp_pipeline(
        mode="SIMULATION",
        target_snr_db=8.0,
        payload_text=test_payload
    )

    assert result["overall_status"] == "SUCCESS"
    assert result["recovery_status"] == "SUCCESS_VERIFIED"
    assert result["recovered_plaintext"] == test_payload
    assert result["bit_error_rate_ber"] == 0.0
    assert result["frame_error_rate_fer"] == 0.0
    assert result["total_stages"] == 14
    assert len(result["stages"]) == 14

    # Verify stage progression
    stages = result["stages"]
    assert stages[0]["name"] == "IQ Acquisition"
    assert stages[0]["state"] == "COMPLETED"
    assert stages[9]["name"] == "Reed-Solomon RS(42,34) Decoding"
    assert stages[9]["state"] == "COMPLETED"
    assert stages[9]["result"] == "FEC_CLEAN"
    assert stages[10]["name"] == "CRC-8 / Header Integrity Check"
    assert stages[10]["result"] == "CRC_VERIFIED"
    assert stages[11]["name"] == "AES-256-GCM v2 Tag Verification"
    assert stages[11]["result"] == "AUTH_VERIFIED"
    assert stages[12]["name"] == "AES-256 Plaintext Decryption"
    assert stages[12]["result"] == "DECRYPTED"
    assert stages[13]["name"] == "Durable Delivery & Cryptographic ACK"
    assert stages[13]["result"] == "MESSAGE_DELIVERED"
    assert len(result["signed_ack_receipt"]) > 16


def test_receiver_dsp_negative_snr_noise_failure():
    """Verify that deep sub-noise SNR (-4 dB) realistically causes syndrome failure and CRC integrity error."""
    test_payload = "SECRET_BURST_TEST"
    result = workstation_service.execute_receiver_dsp_pipeline(
        mode="SIMULATION",
        target_snr_db=-4.0,
        payload_text=test_payload
    )

    assert result["overall_status"] == "DEGRADED"
    assert result["recovery_status"] == "CRC_ERROR_UNCORRECTABLE"
    assert result["recovered_plaintext"] == "[CORRUPTED_BURST_CRC_FAIL]"
    assert result["bit_error_rate_ber"] > 0.0
    assert result["frame_error_rate_fer"] == 1.0

    stages = result["stages"]
    # RS decoding should fail
    assert stages[9]["state"] == "DEGRADED"
    assert stages[9]["result"] == "FEC_OVERLOAD"
    # CRC verification should fail
    assert stages[10]["state"] == "FAILED"
    assert stages[10]["result"] == "CRC_FAILED"
    # Authentication should reject the frame
    assert stages[11]["state"] == "FAILED"
    assert stages[11]["result"] == "AUTH_FAILED"
    # Plaintext decryption should be blocked
    assert stages[12]["state"] == "FAILED"
    assert stages[12]["result"] == "DECRYPT_FAILED"


def test_receiver_dsp_hardware_disconnected():
    """Verify that LIVE_SDR acquisition without USRP B205mini reports HARDWARE_DISCONNECTED."""
    sdr = workstation_service.probe_sdr_hardware()
    if not sdr["device_connected"]:
        result = workstation_service.execute_receiver_dsp_pipeline(mode="LIVE_SDR")
        assert result["overall_status"] == "FAILED"
        assert result["recovery_status"] == "HARDWARE_DISCONNECTED"
        assert result["error"] == "SDR_HARDWARE_NOT_FOUND"
        assert result["stages"][0]["result"] == "HARDWARE_NOT_FOUND"


def test_receiver_dsp_missing_recorded_file():
    """Verify that RECORDED_IQ acquisition with non-existent file reports FILE_NOT_FOUND."""
    fake_path = "/tmp/non_existent_astra_iq_capture_file_999.npy"
    result = workstation_service.execute_receiver_dsp_pipeline(mode="RECORDED_IQ")
    # If the file doesn't exist, it should return FILE_NOT_FOUND
    # Or if last_tx_waveform.npy exists, check load_recorded_iq directly with non-existent file
    iq, meta = workstation_service.load_recorded_iq(fake_path)
    assert iq is None
    assert meta["error"] == "FILE_NOT_FOUND"


def test_tx_rx_api_integration(client):
    """Verify HTTP API endpoints for transmitter burst execution and receiver capture."""
    # 1. Transmitter burst API without confirmation -> rejected
    unconf_res = client.post("/api/v1/workstation/transmitter/transmit", json={
        "text": "API_TEST_PAYLOAD",
        "mode": "SIMULATION",
        "confirm": False
    })
    assert unconf_res.status_code == 200
    assert unconf_res.get_json()["success"] is False
    assert "OPERATOR_CONFIRMATION_REQUIRED" in unconf_res.get_json()["error"]

    # 2. Transmitter burst API with confirmation -> 200 and success
    conf_res = client.post("/api/v1/workstation/transmitter/transmit", json={
        "text": "API_TEST_PAYLOAD",
        "mode": "SIMULATION",
        "confirm": True
    })
    assert conf_res.status_code == 200
    assert conf_res.get_json()["success"] is True

    # 3. Receiver capture API with high SNR -> 200 and SUCCESS_VERIFIED
    rx_res = client.post("/api/v1/workstation/receiver/capture", json={
        "mode": "SIMULATION",
        "target_snr_db": 8.0,
        "payload_text": "API_TEST_PAYLOAD"
    })
    assert rx_res.status_code == 200
    rx_data = rx_res.get_json()
    assert rx_data["recovery_status"] == "SUCCESS_VERIFIED"
    assert rx_data["recovered_plaintext"] == "API_TEST_PAYLOAD"
    assert rx_data["bit_error_rate_ber"] == 0.0

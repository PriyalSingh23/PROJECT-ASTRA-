import pytest
from messaging.server import create_app
from integration.workstation_service import workstation_service


@pytest.fixture
def client(tmp_path):
    test_db = str(tmp_path / "test_guided.db")
    app = create_app(db_path=test_db)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_glossary_content_and_structure():
    """Verify that glossary terms are comprehensive, categorised, and scientifically accurate."""
    glossary = workstation_service.get_glossary()
    assert isinstance(glossary, dict)
    assert len(glossary) >= 12

    # Core required terms in ASTRA
    required_terms = [
        "AES",
        "DSSS",
        "FHSS",
        "QPSK",
        "CGAN",
        "FFT",
        "IQ",
        "AWGN",
        "SNR",
        "BER",
        "PAPR",
        "RS",
        "Zadoff-Chu",
        "UHD",
    ]

    for term in required_terms:
        assert term in glossary, f"Expected term {term} missing from ASTRA glossary"
        item = glossary[term]
        assert "term" in item
        assert "category" in item
        assert "definition" in item
        assert "relevance" in item
        assert len(item["definition"]) > 10
        assert len(item["relevance"]) > 5


def test_help_documentation_structure():
    """Verify that Help Centre documentation provides complete getting started, pipeline, visualisations, and FAQ."""
    help_doc = workstation_service.get_help_documentation()
    assert isinstance(help_doc, dict)

    # 4 Main sections
    assert "getting_started" in help_doc
    assert "communication_pipeline" in help_doc
    assert "signal_visualisations" in help_doc
    assert "diagnostics_faq" in help_doc

    # Check Getting Started
    gs = help_doc["getting_started"]
    assert "title" in gs
    assert len(gs["sections"]) >= 3
    assert any("Safety" in s.get("heading", "") or "Hardware" in s.get("heading", "") for s in gs["sections"])

    # Check Communication Pipeline
    cp = help_doc["communication_pipeline"]
    assert "title" in cp
    assert len(cp["sections"]) >= 2
    assert any("Transmitter" in s.get("heading", "") for s in cp["sections"])
    assert any("Receiver" in s.get("heading", "") for s in cp["sections"])

    # Check Signal Visualisations
    sv = help_doc["signal_visualisations"]
    assert "title" in sv
    assert len(sv["sections"]) >= 4

    # Check FAQs
    faq = help_doc["diagnostics_faq"]
    assert "title" in faq
    assert len(faq["faqs"]) >= 3
    assert any("SDR" in f["q"] or "USRP" in f["q"] for f in faq["faqs"])


def test_glossary_and_help_api_endpoints(client):
    """Verify HTTP API endpoints for glossary and help documentation."""
    # 1. GET /api/v1/workstation/glossary
    res_gloss = client.get("/api/v1/workstation/glossary")
    assert res_gloss.status_code == 200
    data_gloss = res_gloss.get_json()
    assert "AES" in data_gloss
    assert "CGAN" in data_gloss
    assert "relevance" in data_gloss["AES"]
    assert "Cryptography" in data_gloss["AES"]["category"]

    # 2. GET /api/v1/workstation/help
    res_help = client.get("/api/v1/workstation/help")
    assert res_help.status_code == 200
    data_help = res_help.get_json()
    assert "getting_started" in data_help
    assert "communication_pipeline" in data_help
    assert "signal_visualisations" in data_help
    assert "diagnostics_faq" in data_help
    assert len(data_help["diagnostics_faq"]["faqs"]) > 0


def test_guided_workflow_step_endpoints(client):
    """Verify that every step of the 9-step guided communication experiment maps to operational backend APIs."""
    # Step 1: Query system state and operational mode
    res_diag = client.get("/api/v1/workstation/diagnostics")
    assert res_diag.status_code == 200
    diag = res_diag.get_json()
    assert "backend_status" in diag
    assert "sdr_hardware" in diag

    # Step 2: Prepare tactical message
    res_prep = client.post("/api/v1/workstation/transmitter/prepare", json={"text": "ASTRA_GUIDED_TEST_01"})
    assert res_prep.status_code == 200
    prep = res_prep.get_json()
    assert prep["is_valid"] is True
    assert prep["crypto_envelope"]["scheme"] == "AES-256-GCM v2"
    assert prep["error_correction"]["scheme"] == "Reed-Solomon RS(42, 34)"

    # Step 3 & 4: Synthesize baseband burst
    res_synth = client.post("/api/v1/workstation/transmitter/generate", json={"text": "ASTRA_GUIDED_TEST_01"})
    assert res_synth.status_code == 200
    synth = res_synth.get_json()
    assert synth["samples_total"] == 576  # 64 Zadoff-Chu + 512 CGAN payload
    assert len(synth["time_series_preview"]) > 0

    # Step 5: Simulate channel impairments
    res_chan = client.post("/api/v1/workstation/channel/simulate", json={
        "target_snr_db": 6.0,
        "cfo_hz": 25.0,
        "phase_offset_deg": 10.0,
        "multipath": False
    })
    assert res_chan.status_code == 200
    chan = res_chan.get_json()
    assert "channel_parameters" in chan
    assert chan["channel_parameters"]["target_snr_db"] == 6.0

    # Step 6: Safe transmission in simulation mode (confirm=True)
    res_tx = client.post("/api/v1/workstation/transmitter/transmit", json={
        "text": "ASTRA_GUIDED_TEST_01",
        "mode": "SIMULATION",
        "confirm": True
    })
    assert res_tx.status_code == 200
    tx = res_tx.get_json()
    assert tx["success"] is True

    # Step 7: Receiver 14-stage DSP execution
    res_rx = client.post("/api/v1/workstation/receiver/capture", json={
        "mode": "SIMULATION",
        "target_snr_db": 6.0,
        "payload_text": "ASTRA_GUIDED_TEST_01"
    })
    assert res_rx.status_code == 200
    rx = res_rx.get_json()
    assert rx["recovery_status"] == "SUCCESS_VERIFIED"
    assert rx["recovered_plaintext"] == "ASTRA_GUIDED_TEST_01"
    assert rx["total_stages"] == 14

    # Step 8: Signal analysis
    res_sig = client.get("/api/v1/workstation/signal/analysis?source=SYNTHESIS&fft_size=256&window=blackman_harris")
    assert res_sig.status_code == 200
    sig = res_sig.get_json()
    assert sig["status"] == "ONLINE"
    assert len(sig["time_domain"]) > 0
    assert len(sig["frequency_spectrum"]) == 256

    # Step 9: Empirical evaluation report
    res_eval = client.get("/api/v1/research/evaluation")
    assert res_eval.status_code == 200
    assert res_eval.get_json()["has_report"] is True


def test_invalid_configurations_and_error_handling(client):
    """Verify safety lockouts, validation, and error messages across transmitter and receiver paths."""
    # 1. Transmission without explicit confirmation flag
    res_unconfirmed = client.post("/api/v1/workstation/transmitter/transmit", json={
        "text": "ASTRA_TEST",
        "mode": "SIMULATION",
        "confirm": False
    })
    assert res_unconfirmed.status_code == 200
    unconf = res_unconfirmed.get_json()
    assert unconf["success"] is False
    assert unconf["error"] == "OPERATOR_CONFIRMATION_REQUIRED"

    # 2. Transmission with empty payload
    res_empty = client.post("/api/v1/workstation/transmitter/transmit", json={
        "text": "",
        "mode": "SIMULATION",
        "confirm": True
    })
    assert res_empty.status_code == 200
    empty_res = res_empty.get_json()
    assert empty_res["success"] is False
    assert empty_res["error"] == "EMPTY_PAYLOAD"

    # 3. Transmission exceeding maximum capacity (> 256 bytes)
    res_oversized = client.post("/api/v1/workstation/transmitter/transmit", json={
        "text": "X" * 300,
        "mode": "SIMULATION",
        "confirm": True
    })
    assert res_oversized.status_code == 200
    oversized_res = res_oversized.get_json()
    assert oversized_res["success"] is False
    assert oversized_res["error"] == "PAYLOAD_TOO_LARGE"

    # 4. Hardware transmission when USRP hardware is absent
    res_hw = client.post("/api/v1/workstation/transmitter/transmit", json={
        "text": "ASTRA_TEST",
        "mode": "SDR_HARDWARE",
        "confirm": True
    })
    assert res_hw.status_code == 200
    hw_res = res_hw.get_json()
    sdr = workstation_service.probe_sdr_hardware()
    if not sdr["device_connected"]:
        assert hw_res["success"] is False
        assert hw_res["error"] == "SDR_HARDWARE_NOT_FOUND"
        assert "USRP" in hw_res["details"]


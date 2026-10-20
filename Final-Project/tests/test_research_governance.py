import torch  # Critical on Apple Silicon macOS: MUST precede numpy/scipy to prevent OpenBLAS symbol collision (SIGSEGV 139)
import os
import sys
import json
import hashlib
import yaml
import pytest

from messaging.server import create_app
from messaging.db import get_db_session, init_db
from messaging.models import SecurityAuditLog
from integration.sdr_research.service import sdr_research_service, SDRResearchService


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V4_DIR = os.path.join(REPO_ROOT, "lpi_v4")
BEST_MODEL_PATH = os.path.join(V4_DIR, "run", "lpi_v4.best.pt")
MANIFEST_PATH = os.path.join(V4_DIR, "run", "export_manifest.json")
EXPECTED_SHA256 = "0e8e515355be8bffb48fc27ad63b8e4a4aead57b72d2b5ad969d58aeb1c0887c"


@pytest.fixture
def test_app(tmp_path):
    db_file = str(tmp_path / "test_governance.db")
    app = create_app(db_path=db_file)
    app.config["TESTING"] = True
    app.config["DB_PATH"] = db_file
    return app, db_file


@pytest.fixture
def client(test_app):
    app, _ = test_app
    with app.test_client() as c:
        yield c


@pytest.fixture
def test_db_path(test_app):
    _, db_file = test_app
    return db_file


# ---------------------------------------------------------------------------
# Test 1: Checkpoint SHA-256 and bundle verification
# ---------------------------------------------------------------------------
def test_checkpoint_sha256_matches_manifest():
    assert os.path.exists(BEST_MODEL_PATH), f"Model checkpoint not found: {BEST_MODEL_PATH}"
    
    # Verify SHA-256 matches exact authorized export
    hasher = hashlib.sha256()
    with open(BEST_MODEL_PATH, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    actual_sha256 = hasher.hexdigest()
    assert actual_sha256 == EXPECTED_SHA256, (
        f"Checkpoint SHA-256 mismatch! Got {actual_sha256}, expected {EXPECTED_SHA256}"
    )

    # Verify export_manifest.json
    assert os.path.exists(MANIFEST_PATH), f"Manifest not found: {MANIFEST_PATH}"
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    assert manifest["exported_from"] == "lpi_v4.best.pt"
    assert manifest["sha256"] == EXPECTED_SHA256
    assert manifest["epoch"] == 16

    # Verify bundle files exist in lpi_v4/run/
    run_dir = os.path.join(V4_DIR, "run")
    bundle_files = ["generator_lpi.pt", "decoder_lpi.pt", "lpi_config.json"]
    for bf in bundle_files:
        bf_path = os.path.join(run_dir, bf)
        assert os.path.exists(bf_path), f"Bundle file missing: {bf_path}"
        assert os.path.getsize(bf_path) > 0, f"Bundle file is empty: {bf_path}"


# ---------------------------------------------------------------------------
# Test 2: Checkpoint verification endpoint & audit logging
# ---------------------------------------------------------------------------
def test_checkpoint_verify_endpoint(client, test_db_path):
    sdr_research_service.simulate_tamper(False)
    resp = client.post("/api/v1/research/checkpoints/verify")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["verified"] is True
    assert data["sha256"] == EXPECTED_SHA256
    assert "bundle_files" in data
    assert "audit_log_id" in data

    # Verify audit log in SQLite
    with get_db_session(test_db_path) as session:
        logs = session.query(SecurityAuditLog).order_by(SecurityAuditLog.timestamp.desc()).all()
        verified_logs = [
            l for l in logs 
            if (l.action == "MODEL_CHECKPOINT_VERIFIED" or l.event_type == "MODEL_CHECKPOINT_VERIFIED")
        ]
        assert len(verified_logs) > 0, "MODEL_CHECKPOINT_VERIFIED audit log not found"
        assert verified_logs[0].severity == "INFO"


# ---------------------------------------------------------------------------
# Test 3: Tamper simulation activates analytical fallback
# ---------------------------------------------------------------------------
def test_tamper_simulation_activates_analytical_fallback(client, test_db_path):
    # Trigger simulated tamper
    resp = client.post("/api/v1/research/checkpoints/test-tamper", json={"tamper": True})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["fallback_active"] is True
    assert data["tamper_simulated"] is True
    assert data["status"] == "ANALYTICAL_FALLBACK_ACTIVE"
    assert "audit_log_id" in data

    # Verify HIGH severity audit log
    with get_db_session(test_db_path) as session:
        logs = session.query(SecurityAuditLog).order_by(SecurityAuditLog.timestamp.desc()).all()
        tamper_logs = [
            l for l in logs
            if (l.action == "MODEL_CHECKPOINT_HASH_MISMATCH" or l.event_type == "MODEL_CHECKPOINT_HASH_MISMATCH")
        ]
        assert len(tamper_logs) > 0, "MODEL_CHECKPOINT_HASH_MISMATCH audit log not found"
        assert tamper_logs[0].severity == "HIGH"

    # Verify signal sample returns synthetic analytical fallback
    sample_resp = client.get("/api/v1/research/signal-sample")
    assert sample_resp.status_code == 200
    sample_data = sample_resp.get_json()
    assert sample_data["source"] == "SYNTHETIC_ANALYTICAL_FALLBACK"
    assert sample_data["fallback_active"] is True
    assert "footnote" in sample_data
    assert "(Analytical Fallback Active: Neural Inference Disabled)" in sample_data["footnote"]

    # Reset tamper mode
    restore_resp = client.post("/api/v1/research/checkpoints/test-tamper", json={"tamper": False})
    assert restore_resp.status_code == 200
    restore_data = restore_resp.get_json()
    assert restore_data["fallback_active"] is False
    assert restore_data["tamper_simulated"] is False

    # Verify signal sample restored to neural generator
    restored_sample_resp = client.get("/api/v1/research/signal-sample")
    assert restored_sample_resp.status_code == 200
    restored_sample_data = restored_sample_resp.get_json()
    assert restored_sample_data["source"] == "LPI_CGAN_NEURAL_GENERATOR"
    assert restored_sample_data["fallback_active"] is False


# ---------------------------------------------------------------------------
# Test 4: Apple Silicon MPS detection & fallback
# ---------------------------------------------------------------------------
def test_apple_silicon_mps_detection_and_fallback(client):
    resp = client.get("/api/v1/research/environment")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "is_apple_silicon" in data
    assert "mps_available" in data
    assert "active_backend" in data or "active_inference_backend" in data
    assert "thread_count" in data

    # Test LPIDecoder execution does not crash with ComplexFloat error
    sys.path.insert(0, V4_DIR)
    from lpi_core import LPIConfig, LPIDecoder
    cfg = LPIConfig()
    dec = LPIDecoder(cfg)
    
    # Test on CPU
    y_cpu = torch.randn(2, 2, cfg.frame_len)
    bits_cpu = dec.hard_bits(y_cpu)
    assert bits_cpu.shape == (2, cfg.n_bits)

    # If MPS available, test decoder forward/hard_bits without throwing ComplexFloat TypeError
    if torch.backends.mps.is_available():
        dec_mps = LPIDecoder(cfg).to("mps")
        y_mps = y_cpu.to("mps")
        try:
            bits_mps = dec_mps.hard_bits(y_mps)
            assert bits_mps.shape == (2, cfg.n_bits)
        except TypeError as exc:
            pytest.fail(f"LPIDecoder crashed with ComplexFloat TypeError on MPS: {exc}")


# ---------------------------------------------------------------------------
# Test 5: Comparative benchmark endpoint (MPS vs CPU)
# ---------------------------------------------------------------------------
def test_comparative_benchmark_endpoint(client):
    resp = client.post("/api/v1/research/benchmark/compare", json={"frames": 16})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "cpu" in data or "cpu_time_ms" in data
    cpu_ms = data.get("cpu_time_ms", data.get("cpu", {}).get("time_ms", 0))
    assert cpu_ms > 0
    speedup = data.get("speedup_factor", 0)
    assert speedup > 0

    if torch.backends.mps.is_available():
        mps_ms = data.get("mps_time_ms", data.get("mps", {}).get("time_ms", 0))
        assert mps_ms > 0


# ---------------------------------------------------------------------------
# Test 6: GNU Radio flowgraphs calibrated to 2.484 GHz & 245.76 kS/s
# ---------------------------------------------------------------------------
def test_gnuradio_flowgraphs_calibrated_to_2484_ghz():
    flowgraphs = [
        os.path.join(REPO_ROOT, "grc", "tx_lpi_cgan.grc"),
        os.path.join(REPO_ROOT, "grc", "rx_lpi_cgan.grc"),
        os.path.join(V4_DIR, "tx_lpi_v4.grc"),
        os.path.join(V4_DIR, "rx_lpi_v4.grc"),
    ]

    for fg_path in flowgraphs:
        assert os.path.exists(fg_path), f"Flowgraph not found: {fg_path}"
        with open(fg_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert data is not None, f"Failed to parse YAML from {fg_path}"
        blocks = data.get("blocks", [])

        # Find samp_rate and center_freq variables
        samp_rate_val = None
        center_freq_val = None

        for b in blocks:
            name = b.get("name")
            if name == "samp_rate":
                samp_rate_val = b.get("parameters", {}).get("value")
            elif name == "center_freq":
                center_freq_val = b.get("parameters", {}).get("value")

        assert samp_rate_val is not None, f"samp_rate variable missing in {fg_path}"
        assert center_freq_val is not None, f"center_freq variable missing in {fg_path}"

        # Clean/evaluate string representation if needed
        sr_float = float(str(samp_rate_val).strip("'\""))
        cf_float = float(str(center_freq_val).strip("'\""))

        assert int(sr_float) == 245760, (
            f"{os.path.basename(fg_path)}: samp_rate must be 245760, got {samp_rate_val}"
        )
        assert int(cf_float) == 2484000000 or cf_float == 2.484e9, (
            f"{os.path.basename(fg_path)}: center_freq must be 2484000000 (2.484e9), got {center_freq_val}"
        )

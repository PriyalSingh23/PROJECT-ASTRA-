"""Experiment runner contracts (CSV columns, JSON provenance, plots) and
RS benchmark JSON schema."""

import csv
import json

import numpy as np
import pytest

from comms.experiments import parse_ebn0, run_sweep
from comms.plots import make_plots


def test_parse_ebn0():
    assert parse_ebn0("0,4,8") == (0.0, 4.0, 8.0)
    with pytest.raises(Exception):
        parse_ebn0(" , ")


def test_run_sweep_outputs_and_contracts(tmp_path):
    from comms.config import config_from_preset
    cfg = config_from_preset("debug", frames=4, ebn0_db=(6.0, 10.0))
    summary = run_sweep(cfg, tmp_path)

    assert summary["all_invariants_ok"] is True
    assert len(summary["rows"]) == 2

    # CSV: columns must be a superset of every row's keys
    with (tmp_path / "sweep.csv").open() as fh:
        reader = csv.DictReader(fh)
        cols = set(reader.fieldnames)
        csv_rows = list(reader)
    assert len(csv_rows) == 2
    for row in summary["rows"]:
        assert set(row.keys()) <= cols

    # JSON provenance: config, seed, versions, timestamp, Eb/N0 definition
    prov = json.loads((tmp_path / "config.json").read_text())
    assert prov["config"]["frames"] == 4
    assert prov["config"]["seed"] == cfg.seed
    assert "created_utc" in prov and "versions" in prov
    assert "python" in prov["versions"] and "numpy" in prov["versions"]
    assert "Eb/N0" in prov["ebn0_definition"]
    assert "latency" in prov["latency_definition"].lower()

    # artifact records exist for plots
    assert (tmp_path / "artifacts_point00.npz").exists()
    art = np.load(tmp_path / "artifacts_point00.npz")
    assert {"tx_bits", "rx_bits", "tx_symbols", "rx_symbols",
            "tx_wave", "rx_wave"} <= set(art.files)


def test_make_plots_from_records(tmp_path):
    from comms.config import config_from_preset
    cfg = config_from_preset("debug", frames=3, ebn0_db=(4.0, 8.0))
    run_sweep(cfg, tmp_path)
    made = make_plots(tmp_path, tmp_path / "plots")
    names = {p.name for p in made}
    assert names == {"ber_vs_ebn0.png", "per_vs_ebn0.png", "bits_tx_rx.png",
                     "waveform.png", "spectrum.png", "constellation.png",
                     "latency.png"}
    for p in made:
        assert p.stat().st_size > 1000        # rendered, not empty stubs


def test_plots_refuse_missing_records(tmp_path):
    with pytest.raises(FileNotFoundError):
        make_plots(tmp_path / "nothing_here")


# ---- RS benchmark ------------------------------------------------------

def test_benchmark_json_contract():
    from comms.bench_rs import run_benchmark
    report = run_benchmark(trials=3, timing_iterations=4, seed=99)

    for key in ("generated_utc", "environment", "parameters", "correctness",
                "injection", "malformed", "timing", "legacy_app_engine",
                "notes"):
        assert key in report

    p = report["parameters"]
    assert (p["ndata"], p["nparity"], p["ncode"], p["t_correctable_per_codeword"]) \
        == (223, 32, 255, 16)
    assert p["code_rate"] == pytest.approx(223 / 255)

    assert report["correctness"]["roundtrip_failures"] == 0

    per_n = {r["symbol_errors_injected"]: r for r in report["injection"]["per_n"]}
    # within t: every trial corrects fully and reports the exact count
    for n in (1, 4, 16):
        assert per_n[n]["correct"] == per_n[n]["trials"]
        assert per_n[n]["failed"] == 0
        assert per_n[n]["corrected_symbols_reported"] == per_n[n]["trials"] * n
    # beyond t: trials are fully accounted, never silently "correct"
    for n in (17, 20, 32):
        r = per_n[n]
        assert r["correct"] + r["miscorrected"] + r["failed"] == r["trials"]
        assert r["miscorrected"] + r["failed"] == r["trials"]

    mal = report["malformed"]
    assert mal["structural_failures_detected"] == mal["non_multiple_of_255_inputs"]
    assert mal["truncated_stream_detected"] is True
    assert mal["empty_input_roundtrips_empty"] is True

    for k in ("encode_frame_76B", "decode_frame_76B_to255B",
              "encode_10000B", "decode_12675B_to10000B"):
        assert report["timing"][k]["ops_per_second"] > 0
        assert report["timing"][k]["mb_per_second"] > 0

    legacy = report["legacy_app_engine"]
    assert legacy["imported"] is True
    assert legacy["codeword_equivalence"]["identical_codewords"] == \
        legacy["codeword_equivalence"]["trials"]
    assert legacy["legacy_roundtrip"]["ok"] == legacy["legacy_roundtrip"]["texts"]
    assert legacy["corruption_within_t"]["legacy_returned_original_plaintext"] is True
    assert legacy["corruption_beyond_t"]["legacy_returned_original_plaintext"] is False
    assert legacy["corruption_beyond_t"]["our_layer_failed"] is True


def test_benchmark_writes_file(tmp_path):
    from comms.bench_rs import main as bench_main
    out = tmp_path / "rs.json"
    rc = bench_main(["--out", str(out), "--trials", "2", "--iterations", "3"])
    assert rc == 0 and out.exists()
    json.loads(out.read_text())


def test_cli_entry_points_respond_to_help():
    """`python3 -m comms.*` must actually invoke main() (__main__ guard)."""
    import subprocess
    import sys
    for mod in ("comms.experiments", "comms.plots", "comms.bench_rs"):
        r = subprocess.run([sys.executable, "-m", mod, "--help"],
                           capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, (mod, r.stderr)
        assert "usage" in r.stdout.lower()

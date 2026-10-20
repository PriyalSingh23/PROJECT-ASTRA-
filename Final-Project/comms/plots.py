"""Baseline plots, rendered only from saved experiment records.

Usage::

    python3 -m comms.plots --results results/gate1_baseline
    python3 -m comms.plots --results results/gate1_baseline --out /tmp/p

Reads ``config.json``, ``sweep.csv`` and ``artifacts_pointXX.npz`` from a
directory produced by ``comms.experiments``; refuses to draw anything it
cannot read from those records. Figures produced:

``ber_vs_ebn0.png``      raw / frame-level / payload BER vs Eb/N0
``per_vs_ebn0.png``      PER (log) and PDR vs Eb/N0
``bits_tx_rx.png``       transmitted vs received bits (first frame)
``waveform.png``         transmitted vs received waveform
``spectrum.png``         Welch PSD of tx/rx waveform
``constellation.png``    received-symbol scatter vs ideal points
``latency.png``          measured per-frame processing latency

The theoretical curve overlaid on the BER plot is the closed-form AWGN
hard-decision curve ``0.5*erfc(sqrt(Eb/N0))`` (valid for BPSK and
Gray-mapped QPSK), clearly labelled "theory" - it is math, not a
measurement of this system, and zero-error points are omitted from the
log axis rather than faked up to a floor value.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                              # noqa: E402
from scipy.signal import welch                               # noqa: E402
from scipy.special import erfc                               # noqa: E402


def _theory_ber(ebn0_db) -> np.ndarray:
    return 0.5 * erfc(np.sqrt(10.0 ** (np.asarray(ebn0_db, dtype=float) / 10.0)))


def _load_run(results_dir: Path):
    cfg = json.loads((results_dir / "config.json").read_text())
    with (results_dir / "sweep.csv").open() as fh:
        rows = list(csv.DictReader(fh))
    return cfg, rows


def _col(rows, key) -> np.ndarray:
    out = []
    for r in rows:
        v = r.get(key, "")
        out.append(float(v) if v not in ("", None) else np.nan)
    return np.asarray(out, dtype=float)


def _log_series(values) -> np.ndarray:
    """Zeros become NaN so log axes show gaps instead of fake floors."""
    a = np.asarray(values, dtype=float)
    a[a <= 0] = np.nan
    return a


def make_plots(results_dir, out_dir=None) -> list:
    results_dir = Path(results_dir)
    out = Path(out_dir) if out_dir else results_dir / "plots"
    out.mkdir(parents=True, exist_ok=True)
    cfg_json, rows = _load_run(results_dir)
    cfg = cfg_json["config"]
    x = _col(rows, "ebn0_db")
    made = []

    def save(fig, name):
        path = out / name
        fig.savefig(path, dpi=120, bbox_inches="tight")
        plt.close(fig)
        made.append(path)
        return path

    # 1) BER vs Eb/N0 ---------------------------------------------------
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(x, _log_series(_col(rows, "ber_raw")), "o-", label="raw BER (pre-FEC, measured)")
    ax.plot(x, _log_series(_col(rows, "ber_frame_effective")), "s-",
            label="frame BER (post-FEC, measured; unmeasurable bits as upper bound)")
    ax.plot(x, _log_series(_col(rows, "ber_payload_effective")), "^-",
            label="payload BER (failed frames counted fully erroneous)")
    if cfg["mode"] == "uncoded":
        ax.plot(x, _theory_ber(x), "k--", linewidth=1,
                label="theory: 0.5*erfc(sqrt(Eb/N0)) (AWGN hard decisions)")
    ax.set_yscale("log")
    ax.set_xlabel("Eb/N0 (dB) - per information payload bit")
    ax.set_ylabel("bit error rate")
    ax.set_title(f"BER vs Eb/N0  ({cfg['mode']}, {cfg['modulation']}, "
                 f"{cfg['frames']} frames/point, seed {cfg['seed']})")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(fontsize=7)
    save(fig, "ber_vs_ebn0.png")

    # 2) PER / PDR vs Eb/N0 --------------------------------------------
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(x, _log_series(_col(rows, "per")), "o-", color="tab:red",
            label="PER (failed / sent frames)")
    ax.set_yscale("log")
    ax.set_xlabel("Eb/N0 (dB)")
    ax.set_ylabel("packet error rate")
    ax2 = ax.twinx()
    ax2.plot(x, _col(rows, "pdr"), "s--", color="tab:green",
             label="PDR (delivered / sent frames)")
    ax2.set_ylabel("packet delivery ratio")
    ax2.set_ylim(0, 1.05)
    ax.set_title("PER and PDR vs Eb/N0 (failed frames always in denominator)")
    ax.grid(True, which="both", alpha=0.3)
    lines = ax.get_lines() + ax2.get_lines()
    ax.legend(lines, [ln.get_label() for ln in lines], fontsize=8, loc="center right")
    save(fig, "per_vs_ebn0.png")

    # artifact-backed figures (last sweep point = highest Eb/N0) --------
    art_files = sorted(results_dir.glob("artifacts_point*.npz"))
    if not art_files:
        print(f"note: no artifact records in {results_dir}; "
              "bit/waveform/constellation/spectrum figures skipped")
        return made
    art = np.load(art_files[-1])
    tx_bits = art["tx_bits"]
    rx_bits = art["rx_bits"]
    tx_sym = art["tx_symbols"]
    rx_sym = art["rx_symbols"]
    tx_wave = art["tx_wave"]
    rx_wave = art["rx_wave"]

    # 3) transmitted vs received bits ----------------------------------
    n_show = min(128, tx_bits.size)
    fig, ax = plt.subplots(figsize=(9, 3))
    t = np.arange(n_show)
    ax.step(t, tx_bits[:n_show], where="mid", label="tx bits", linewidth=1.2)
    ax.step(t, rx_bits[:n_show] - 0.06, where="mid", label="rx bits (offset)",
            linewidth=1.2)
    diff = np.nonzero(tx_bits[:n_show] != rx_bits[:n_show])[0]
    if diff.size:
        ax.plot(diff, tx_bits[diff] + 0.03, "rx", color="tab:red", markersize=8,
                label=f"bit errors ({diff.size} in shown span)")
    ax.set_xlabel("bit index (first frame)")
    ax.set_yticks([0, 1])
    ax.set_title("Transmitted vs received bits (first frame, first 128 bits)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    save(fig, "bits_tx_rx.png")

    # 4) waveform -------------------------------------------------------
    sps = max(1, tx_wave.size // max(tx_sym.size, 1))
    n_sym_show = min(64, tx_sym.size)
    fig, ax = plt.subplots(figsize=(9, 3.5))
    ax.plot(tx_wave[: n_sym_show * sps].real, label="tx I", linewidth=0.9)
    ax.plot(rx_wave[: n_sym_show * sps].real, label="rx I (with noise)",
            linewidth=0.9, alpha=0.8)
    ax.set_xlabel("sample index (rect pulse, sps=8)")
    ax.set_ylabel("amplitude")
    ax.set_title("Transmitted vs received waveform (in-phase, first frame)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    save(fig, "waveform.png")

    # 5) spectrum -------------------------------------------------------
    nperseg = min(1024, tx_wave.size)
    f_tx, p_tx = welch(tx_wave, nperseg=nperseg)
    f_rx, p_rx = welch(rx_wave, nperseg=nperseg)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(f_tx, 10 * np.log10(p_tx + 1e-30), label="tx PSD")
    ax.plot(f_rx, 10 * np.log10(p_rx + 1e-30), label="rx PSD (with noise)",
            alpha=0.8)
    ax.set_xlabel("normalized frequency (cycles/sample)")
    ax.set_ylabel("power spectral density (dB)")
    ax.set_title("Spectrum of transmitted vs received waveform (Welch)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    save(fig, "spectrum.png")

    # 6) constellation --------------------------------------------------
    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    step = max(1, rx_sym.size // 4000)      # keep the scatter readable
    ax.plot(rx_sym[::step].real, rx_sym[::step].imag, ".", alpha=0.25,
            label="rx symbols")
    ideal = np.unique(np.round(tx_sym, 6))
    ax.plot(ideal.real, ideal.imag, "x", color="k", markersize=9,
            label="ideal points (tx)")
    ax.set_xlabel("I")
    ax.set_ylabel("Q")
    ax.set_aspect("equal")
    ax.set_title(f"Constellation, first frame ({cfg['modulation']})")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    save(fig, "constellation.png")

    # 7) latency --------------------------------------------------------
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(x, _col(rows, "latency_tx_mean_ms"), "o-", label="tx mean")
    ax.plot(x, _col(rows, "latency_rx_mean_ms"), "s-", label="rx mean")
    ax.plot(x, _col(rows, "latency_tx_p95_ms"), "o--", alpha=0.5,
            label="tx p95")
    ax.plot(x, _col(rows, "latency_rx_p95_ms"), "s--", alpha=0.5,
            label="rx p95")
    ax.set_xlabel("Eb/N0 (dB)")
    ax.set_ylabel("processing latency (ms, this host)")
    ax.set_title("Per-frame processing latency (perf_counter, local host)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    save(fig, "latency.png")

    return made


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="comms.plots",
        description="Render ASTRA baseline plots from saved experiment records.")
    p.add_argument("--results", required=True, type=Path,
                   help="directory written by comms.experiments")
    p.add_argument("--out", type=Path, default=None,
                   help="output directory (default: <results>/plots)")
    a = p.parse_args(argv)
    made = make_plots(a.results, a.out)
    for m in made:
        print(m)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

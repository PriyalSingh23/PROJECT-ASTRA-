"""Reproducible sweep runner for the ASTRA measurable-link baseline.

Usage::

    python3 -m comms.experiments --preset debug --out results/gate1_debug
    python3 -m comms.experiments --preset montecarlo --mode rs255_223 \\
        --modulation qpsk --ebn0 0,2,4,6,8,10 --seed 7 \\
        --out results/gate1_rs_qpsk

Outputs written to ``--out`` (every number is measured from the seeded
run; nothing is interpolated or copied from another source):

``config.json``    full provenance: config values, RNG seed, package
                   versions, platform, timestamp, Eb/N0 definition.
``sweep.csv``      one row per Eb/N0 point, stable column set.
``summary.json``   the same rows plus per-point accounting-invariant
                   results (``all_invariants_ok``).
``artifacts_pointXX.npz``  first-frame bits/symbols/waveforms used by
                   ``comms.plots`` - plots render only from these records.

Each sweep point gets its own RNG derived as
``default_rng([seed, point_index])`` so points are independent and any
subset can be reproduced exactly.
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
import sys
from datetime import datetime, timezone
from importlib import metadata as importlib_metadata
from pathlib import Path

import numpy as np

from .config import config_from_preset
from .pipeline import LinkSimulator

_VERSION_PKGS = ("numpy", "scipy", "matplotlib", "reedsolo", "cryptography",
                 "torch")


def _versions() -> dict:
    vers = {"python": sys.version.split()[0], "platform": platform.platform()}
    for pkg in _VERSION_PKGS:
        try:
            vers[pkg] = importlib_metadata.version(pkg)
        except importlib_metadata.PackageNotFoundError:
            vers[pkg] = None
    return vers


def parse_ebn0(text: str) -> tuple:
    pts = tuple(float(x) for x in text.split(",") if x.strip())
    if not pts:
        raise argparse.ArgumentTypeError("need at least one Eb/N0 point")
    return pts


def run_sweep(config, out_dir) -> dict:
    """Execute one sweep; write CSV/JSON/npz records; return the summary."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sim = LinkSimulator(config)
    rows = []
    invariant_problems = []
    for idx, ebn0 in enumerate(config.ebn0_db):
        rng = np.random.default_rng([config.seed, idx])
        metrics, artifacts = sim.run_point(ebn0, config.frames, rng,
                                           collect_artifacts=True)
        row = metrics.as_dict()
        row["ebn0_db"] = ebn0
        rows.append(row)
        problems = metrics.check_invariants()
        if problems:
            invariant_problems.append({"ebn0_db": ebn0, "problems": problems})
        keep = {k: v for k, v in artifacts.items()
                if isinstance(v, np.ndarray)}
        if keep:
            np.savez_compressed(out_dir / f"artifacts_point{idx:02d}.npz",
                                **keep)

    csv_path = out_dir / "sweep.csv"
    cols = list(rows[0].keys())
    with csv_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    provenance = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "label": config.name,
        "command": " ".join(sys.argv),
        "config": {
            "modulation": config.modulation,
            "mode": config.mode,
            "payload_bytes": config.payload_bytes,
            "frames": config.frames,
            "ebn0_db": list(config.ebn0_db),
            "seed": config.seed,
            "name": config.name,
            "description": config.description,
        },
        "ebn0_definition": (
            "Eb/N0 is energy per information payload bit relative to N0; "
            "Es/N0 is derived per point from info_bits / actual transmitted "
            "symbols (coded bits + symbol padding), i.e. code rate, framing "
            "overhead and padding are included in one exact ratio "
            "(comms/config.py)."),
        "latency_definition": (
            "latency_* values are single-host processing time "
            "(time.perf_counter around the per-frame tx/rx chain), NOT "
            "over-the-air latency."),
        "versions": _versions(),
    }
    (out_dir / "config.json").write_text(json.dumps(provenance, indent=2))

    summary = {"rows": rows,
               "invariant_problems": invariant_problems,
               "all_invariants_ok": not invariant_problems}
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def _fmt(v) -> str:
    if v is None:
        return f"{'n/a':>10}"
    if isinstance(v, float):
        return f"{v:10.4g}"
    return f"{str(v):>10}"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="comms.experiments",
        description="Reproducible Eb/N0 sweep for the ASTRA link baseline.")
    p.add_argument("--preset", default="debug", choices=("debug", "montecarlo"))
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--frames", type=int, default=None)
    p.add_argument("--ebn0", type=parse_ebn0, default=None,
                   help="comma-separated Eb/N0 points in dB")
    p.add_argument("--mode", choices=("uncoded", "rs255_223"), default=None)
    p.add_argument("--modulation", choices=("bpsk", "qpsk"), default=None)
    p.add_argument("--payload-bytes", type=int, default=None)
    p.add_argument("--label", default=None)
    a = p.parse_args(argv)

    overrides = {k: v for k, v in {
        "seed": a.seed, "frames": a.frames, "ebn0_db": a.ebn0,
        "mode": a.mode, "modulation": a.modulation,
        "payload_bytes": a.payload_bytes, "name": a.label,
    }.items() if v is not None}
    config = config_from_preset(a.preset, **overrides)

    summary = run_sweep(config, a.out)
    print(f"{config.name}: {config.mode} {config.modulation}, "
          f"{config.frames} frames x {len(config.ebn0_db)} points -> {a.out}")
    print(f"{'Eb/N0':>7} {'frames':>7} {'ok':>6} {'PER':>10} {'ber_raw':>10} "
          f"{'ber_frame':>10} {'goodput':>10}")
    for r in summary["rows"]:
        ge = r["goodput_efficiency"]
        ge_s = f"{ge * 100:8.2f}%" if ge is not None else f"{'n/a':>9}"
        print(f"{r['ebn0_db']:>7.2f} {r['frames_sent']:>7} {r['frames_ok']:>6} "
              f"{_fmt(r['per'])} {_fmt(r['ber_raw'])} "
              f"{_fmt(r['ber_frame_effective'])} {ge_s}")
    if not summary["all_invariants_ok"]:
        print("INVARIANT PROBLEMS:", json.dumps(summary["invariant_problems"],
                                                indent=2))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

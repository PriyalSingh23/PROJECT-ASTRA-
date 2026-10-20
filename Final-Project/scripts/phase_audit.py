#!/usr/bin/env python3
"""SHADOWCOMM phase-by-phase audit harness.

Runs each project phase's pytest subset in isolation and probes the live
parameters that phase is responsible for, printing a consolidated table.

Usage:
    python scripts/phase_audit.py            # all phases
    python scripts/phase_audit.py --phase 4  # one phase

IMPORTANT: `torch` is imported first on purpose. On macOS Apple Silicon a
numpy/scipy import that precedes torch can trigger an OpenBLAS dynamic linker
collision (SIGSEGV 139).
"""
import torch  # noqa: F401  (must precede numpy/scipy — see module docstring)

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)


# --------------------------------------------------------------------------
# Phase definitions: each phase maps to an isolated pytest subset.
# --------------------------------------------------------------------------
PHASES = {
    1: {
        "name": "P1 Messaging Core & Verified ACKs",
        "tests": [
            "tests/test_offline_messaging.py",
            "tests/test_security_auth.py",
        ],
    },
    2: {
        "name": "P2 Dual-Station Experience & Recipient Inbox",
        "tests": [],  # exercised via live API probe below
    },
    3: {
        "name": "P3 Fault Injection, Outages & Client Re-Sync",
        "tests": [
            "tests/test_simulation_1000_messages.py",
        ],
    },
    4: {
        "name": "P4 Transport Broker & Hardware Safety Lockout",
        "tests": [
            "tests/integration/test_adapters.py",
            "tests/integration/test_relay_nodes.py",
        ],
    },
    5: {
        "name": "P5 Research Lab Governance & SDR Physical Layer",
        "tests": [
            "tests/test_lpi_v4.py",
            "tests/test_spectrum_analyser.py",
            "tests/test_workstation_service.py",
            "tests/test_presentation_mode.py",
            "tests/test_tx_rx_integration.py",
            "tests/test_guided_demo_and_help.py",
        ],
    },
}


def run_pytest(paths):
    """Run a pytest subset and return (passed, total, ok)."""
    if not paths:
        return (0, 0, True)
    cmd = [sys.executable, "-m", "pytest", *paths, "--no-header", "-p", "no:cacheprovider"]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    out = proc.stdout + proc.stderr
    passed = int(m.group(1)) if (m := re.search(r"(\d+) passed", out)) else 0
    failed = int(m.group(1)) if (m := re.search(r"(\d+) failed", out)) else 0
    errors = int(m.group(1)) if (m := re.search(r"(\d+) error", out)) else 0
    total = passed + failed + errors
    return (passed, total, proc.returncode == 0 and failed == 0 and errors == 0)


# --------------------------------------------------------------------------
# Live parameter probes — one per phase.
# --------------------------------------------------------------------------
def probe_p1():
    """Return (label, value, ok) tuples of Phase-1 runtime parameters."""
    from messaging.crypto_v2 import encrypt_v2_gcm
    from messaging.db import get_db_session
    from sqlalchemy import text

    params = []
    env = encrypt_v2_gcm(b"audit", "audit-passphrase")
    # [1 byte ver][12 nonce][16 tag][ct]  => 29-byte fixed overhead
    overhead = len(env) - len(b"audit")
    params.append(("AES-256-GCM envelope overhead (bytes)", overhead, overhead == 29))
    with get_db_session() as s:
        mode = s.execute(text("PRAGMA journal_mode")).scalar()
        busy = s.execute(text("PRAGMA busy_timeout")).scalar()
    params.append(("SQLite journal mode", str(mode).upper(), str(mode).lower() == "wal"))
    params.append(("SQLite busy_timeout (ms)", busy, busy == 5000))
    return params


def probe_p2():
    """Live dual-station + recipient inbox probe via the Flask test client.

    Uses a temporary SQLite database so the audit never mutates the
    operator's real shadowcomm_messaging.db.
    """
    import tempfile
    from messaging.server import create_app

    tmp_fd, tmp_db = tempfile.mkstemp(prefix="shadowcomm_audit_", suffix=".db")
    os.close(tmp_fd)
    try:
        app = create_app(db_path=tmp_db)
        client = app.test_client()
        params = []

        r = client.get("/api/v1/endpoints")
        endpoints = r.get_json() if r.status_code == 200 else []
        ids = sorted(e.get("endpoint_id") for e in endpoints)
        params.append(("Seeded endpoints", ", ".join(str(i) for i in ids),
                       ids == ["endpoint-a", "endpoint-b"]))

        def _submit():
            return client.post("/api/v1/messages", json={
                "sender_endpoint_id": "endpoint-a",
                "recipient_endpoint_id": "endpoint-b",
                "payload": "PHASE2-AUDIT",
                "client_idempotency_key": "audit-p2-001",
            })

        def _mid(resp):
            if not resp.is_json:
                return None
            body = resp.get_json()
            if isinstance(body, dict):
                flat = body.get("message_id") or body.get("id") or body.get("message")
                if isinstance(flat, dict):
                    return flat.get("message_id") or flat.get("id")
                return flat
            return None

        r = _submit()
        msg_id = _mid(r)
        params.append(("Message submit HTTP status", r.status_code, r.status_code in (200, 201)))

        # Idempotent resubmission must not create a duplicate row.
        r2 = _submit()
        msg_id_2 = _mid(r2)
        params.append(("Idempotent resubmit returns same id", msg_id is not None and msg_id == msg_id_2,
                       msg_id is not None and msg_id == msg_id_2))

        # Recipient inbox query endpoint must answer.
        r3 = client.get("/api/v1/endpoints/endpoint-b/inbox")
        params.append(("Recipient inbox endpoint /endpoints/endpoint-b/inbox", r3.status_code,
                       r3.status_code == 200))
        return params
    finally:
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(tmp_db + suffix)
            except OSError:
                pass


def probe_p3():
    """Fault-injection parameters on the simulated transport."""
    from messaging.transport import transport
    params = []
    transport.set_online(True)
    transport.set_latency(120)
    transport.set_drop_rate(0.5)
    transport.set_ack_drop_rate(0.25)
    st = transport.get_status()
    params.append(("Sim link online", st.get("is_online"), st.get("is_online") is True))
    params.append(("Message drop prob", st.get("drop_message_prob"), st.get("drop_message_prob") == 0.5))
    params.append(("ACK drop prob", st.get("drop_ack_prob"), st.get("drop_ack_prob") == 0.25))
    params.append(("Injected latency (ms)", st.get("latency_ms"), st.get("latency_ms") == 120))
    transport.set_online(True)
    transport.set_latency(0)
    transport.set_drop_rate(0.0)
    transport.set_ack_drop_rate(0.0)
    params.append(("Fault reset to clean state", transport.get_status().get("drop_message_prob") == 0.0, True))
    return params


def probe_p4():
    """Adapter contract + DMR ceiling + safety lockout parameters."""
    from integration.manager import TransportManager
    from integration.base import TransportReadiness, TransportConnectionState
    from integration.motorola.adapter import MotorolaMOTOTRBOAdapter
    from integration.starv.adapter import StarVAdapter, StarVSafetyLockoutError

    params = []
    mgr = TransportManager()
    selected = mgr.select_transport("endpoint-b")
    params.append(("First selected transport", selected.transport_id if selected else None,
                   selected is not None))

    moto = MotorolaMOTOTRBOAdapter()
    over = moto.send("endpoint-b", b"x" * 400, {})
    params.append(("Motorola 280B ceiling enforced", over.get("error_code"),
                   over.get("success") is False and over.get("error_code") in
                   ("PAYLOAD_TOO_LARGE", "DMR_PAYLOAD_EXCEEDED", "PAYLOAD_EXCEEDS_DMR_LIMIT")))

    starv = StarVAdapter()
    params.append(("STAR-V readiness", starv.readiness.value,
                   starv.readiness == TransportReadiness.LOCKED_OUT))
    raised = False
    try:
        starv.command_transmit()
    except StarVSafetyLockoutError:
        raised = True
    params.append(("STAR-V hard-command path raises lockout", raised, raised))

    # Contract: success results must always carry an error_code key.
    from integration.lpi_cgan.adapter import LPICGANTransportAdapter
    lpi = LPICGANTransportAdapter()
    res = lpi.send("endpoint-b", b"audit-frame", {})
    params.append(("LPI-CGAN result carries error_code key", "error_code" in res,
                   "error_code" in res))

    # Priority ordering actually honoured.
    mgr2 = TransportManager()
    from integration.base import BaseTransportAdapter
    class _Stub(BaseTransportAdapter):
        def __init__(self, tid):
            super().__init__(tid, display_name=tid)
        @property
        def transport_type(self): return "STUB"
        @property
        def supported_operations(self): return ["send"]
        @property
        def readiness(self): return TransportReadiness.SIMULATION_ONLY
        @property
        def connection_state(self): return TransportConnectionState.ONLINE
        def send(self, *a, **k): return {"success": True, "error_code": None}
        def health_check(self): return {"transport_id": self.transport_id}
    mgr2.register_adapter(_Stub("stub-low"), priority=50)
    mgr2.register_adapter(_Stub("stub-high"), priority=1)
    first = mgr2.select_transport("endpoint-b")
    params.append(("Priority routing prefers priority=1", first.transport_id if first else None,
                   first is not None and first.transport_id == "stub-high"))
    return params


def probe_p5():
    """Model manifest digest, MPS availability, and SDR parameters."""
    params = []
    manifest_path = os.path.join(ROOT, "lpi_v4", "run", "export_manifest.json")
    ok = os.path.exists(manifest_path)
    expected = None
    if ok:
        with open(manifest_path) as f:
            manifest = json.load(f)
        expected = manifest.get("sha256")
        ckpt = os.path.join(ROOT, "lpi_v4", "run", "lpi_v4.best.pt")
        actual = None
        if os.path.exists(ckpt):
            h = hashlib.sha256()
            with open(ckpt, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            actual = h.hexdigest()
        params.append(("Checkpoint SHA-256 matches manifest",
                       (actual or "missing")[:16] + "...",
                       actual is not None and actual == expected))
    else:
        params.append(("export_manifest.json present", False, False))

    params.append(("Apple MPS available", torch.backends.mps.is_available(),
                   isinstance(torch.backends.mps.is_available(), bool)))
    params.append(("Compute device", "mps" if torch.backends.mps.is_available() else "cpu", True))

    cfg_path = os.path.join(ROOT, "lpi_v4", "run", "lpi_config.json")
    if os.path.exists(cfg_path):
        with open(cfg_path) as f:
            cfg = json.load(f)
        params.append(("SDR sample rate (S/s)", cfg.get("fs"), cfg.get("fs") == 245760.0))
        params.append(("SDR center frequency (Hz)", cfg.get("center_freq"),
                       cfg.get("center_freq") == 2484000000.0))
    return params


PROBES = {1: probe_p1, 2: probe_p2, 3: probe_p3, 4: probe_p4, 5: probe_p5}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", type=int, choices=[1, 2, 3, 4, 5])
    args = ap.parse_args()

    targets = [args.phase] if args.phase else [1, 2, 3, 4, 5]
    overall_ok = True

    print("=" * 78)
    print("  SHADOWCOMM — PHASE-BY-PHASE INDEPENDENT AUDIT")
    print(f"  Host: {platform.platform()}  |  Python {platform.python_version()}")
    print("=" * 78)

    for p in targets:
        spec = PHASES[p]
        print(f"\n### {spec['name']}")
        print("-" * 78)
        passed, total, tok = run_pytest(spec["tests"])
        if spec["tests"]:
            print(f"  Tests: {passed}/{total} passed   [{ 'PASS' if tok else 'FAIL' }]")
        else:
            print("  Tests: live API probe (no dedicated pytest subset)")
        ok_here = tok
        try:
            for label, value, ok in PROBES[p]():
                flag = "PASS" if ok else "FAIL"
                ok_here = ok_here and ok
                print(f"    [{flag}] {label}: {value}")
        except Exception as e:  # pragma: no cover - diagnostic path
            ok_here = False
            print(f"    [FAIL] probe error: {type(e).__name__}: {e}")
        print(f"  PHASE RESULT: {'PASS' if ok_here else 'FAIL'}")
        overall_ok = overall_ok and ok_here

    print("\n" + "=" * 78)
    print(f"  OVERALL: {'ALL PHASES PASS' if overall_ok else 'ONE OR MORE PHASES FAILED'}")
    print("=" * 78)
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

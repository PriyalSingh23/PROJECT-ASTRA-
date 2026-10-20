#!/usr/bin/env python3
"""SHADOWCOMM live end-to-end integration check.

Boots the real Flask server (with its embedded delivery worker) against a
throwaway SQLite database, then drives a genuine Alpha -> Bravo message
through the HTTP API and verifies durable delivery + signed ACK receipt.

This is the "integrate every phase together" gate: it exercises Phase 1
(crypto/queue/ACK), Phase 2 (inbox REST), and Phase 3 (worker auto-delivery)
simultaneously over the real network stack rather than the test client.

Usage: python scripts/integration_e2e.py [--port 5051]
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def http(method, url, body=None, timeout=5):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode()
            try:
                return r.status, json.loads(raw)
            except json.JSONDecodeError:
                return r.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=5051)
    ap.add_argument("--timeout", type=float, default=40.0)
    args = ap.parse_args()
    base = f"http://127.0.0.1:{args.port}"

    fd, db = tempfile.mkstemp(prefix="shadowcomm_e2e_", suffix=".db")
    os.close(fd)
    os.remove(db)  # let the server create it cleanly

    env = dict(os.environ)
    log_fd, log_path = tempfile.mkstemp(prefix="shadowcomm_e2e_", suffix=".log")
    log_file = os.open(log_path, os.O_WRONLY | os.O_TRUNC)
    proc = subprocess.Popen(
        [sys.executable, "-m", "messaging.server", "--db", db,
         "--port", str(args.port), "--host", "127.0.0.1"],
        cwd=ROOT, env=env,
        stdout=log_file, stderr=subprocess.STDOUT,
    )

    results = []
    ok_all = True

    def check(label, value, ok):
        nonlocal ok_all
        ok_all = ok_all and ok
        results.append((label, value, ok))
        print(f"    [{'PASS' if ok else 'FAIL'}] {label}: {value}")

    try:
        print("=" * 78)
        print("  SHADOWCOMM — LIVE END-TO-END INTEGRATION (real server + worker)")
        print("=" * 78)

        # 1. Wait for health.
        t0 = time.time()
        healthy = False
        while time.time() - t0 < 30:
            try:
                st, body = http("GET", f"{base}/api/v1/health")
                if st == 200 and body and body.get("status") == "HEALTHY":
                    healthy = True
                    break
            except Exception:
                pass
            time.sleep(0.3)
        check("Server health after boot (s)", round(time.time() - t0, 2), healthy)
        if not healthy:
            print("  --- server log (boot failure) ---")
            try:
                with open(log_path) as f:
                    print("  " + "\n  ".join(f.read().splitlines()[-25:]))
            except OSError:
                pass
            print("  --------------------------------")

        # 2. Frontend SPA is served at /.
        try:
            st, html = http("GET", f"{base}/")
        except Exception as e:
            st, html = f"{type(e).__name__}", ""
        is_spa = isinstance(html, str) and "root" in html and "<div id=\"root\"" in html
        check("React SPA served at / (HTTP + bundle root)", st, st == 200 and is_spa)

        st, endpoints = http("GET", f"{base}/api/v1/endpoints")
        ids = sorted(e["endpoint_id"] for e in (endpoints or []))
        check("Seeded endpoints", ", ".join(ids), ids == ["endpoint-a", "endpoint-b"])

        # 3. Submit Alpha -> Bravo.
        t_sub = time.time()
        st, body = http("POST", f"{base}/api/v1/messages", {
            "sender_endpoint_id": "endpoint-a",
            "recipient_endpoint_id": "endpoint-b",
            "payload": "E2E-INTEGRATION-PROOF",
            "client_idempotency_key": "e2e-int-001",
        })
        msg = (body or {}).get("message") if isinstance(body, dict) and "message" in (body or {}) else body
        mid = (msg or {}).get("message_id") if isinstance(msg, dict) else None
        check("Submit message (HTTP)", st, st in (200, 201) and mid is not None)

        # 4. Wait for the embedded worker to deliver + reconcile the ACK.
        delivered = None
        deadline = time.time() + args.timeout
        while time.time() < deadline:
            st, msgs = http("GET", f"{base}/api/v1/messages?sender=endpoint-a")
            for m in (msgs or []):
                if m.get("message_id") == mid:
                    delivered = m
            if delivered and delivered.get("current_state") in ("DELIVERED", "FAILED_FINAL", "EXPIRED"):
                break
            time.sleep(0.5)

        t_deliver = round(time.time() - t_sub, 2)
        state = (delivered or {}).get("current_state")
        check("Message reached terminal state", state, state == "DELIVERED")
        check("Time to delivery (s)", t_deliver, delivered is not None and t_deliver <= args.timeout)

        # 5. Signed ACK receipt populated (Phase 1 core guarantee).
        receipt = (delivered or {}).get("signed_ack_receipt")
        check("Signed ACK receipt present", (receipt or "")[:24] + ("..." if receipt else ""),
              bool(receipt))

        # 6. Recipient durable inbox (Phase 2).
        st, inbox = http("GET", f"{base}/api/v1/endpoints/endpoint-b/inbox")
        inbox = inbox or []
        inbox_ids = [i.get("message_id") for i in inbox]
        check("Recipient inbox contains message", len(inbox),
              mid in inbox_ids)

        # 7. Lifecycle events recorded (Phase 2 timeline).
        st, events = http("GET", f"{base}/api/v1/messages/{mid}/events")
        event_types = [e.get("event_type") for e in (events or [])]
        check("Lifecycle events recorded", " -> ".join(event_types[:6]) or "none",
              len(event_types) >= 3)

        # 8. Queue drained.
        st, stats = http("GET", f"{base}/api/v1/queue/stats")
        queued = (stats or {}).get("queued", (stats or {}).get("QUEUED", 0))
        check("Queue drained after delivery", queued, queued in (0, None) or queued == 0)

        # 9. Idempotent resubmit returns the same message (Phase 3 invariant).
        st, body2 = http("POST", f"{base}/api/v1/messages", {
            "sender_endpoint_id": "endpoint-a",
            "recipient_endpoint_id": "endpoint-b",
            "payload": "E2E-INTEGRATION-PROOF",
            "client_idempotency_key": "e2e-int-001",
        })
        msg2 = (body2 or {}).get("message") if isinstance(body2, dict) and "message" in (body2 or {}) else body2
        mid2 = (msg2 or {}).get("message_id") if isinstance(msg2, dict) else None
        check("Idempotent resubmit -> same id", mid2, mid2 == mid)

        # 10. Transport broker advertises adapters (Phase 4).
        st, transports = http("GET", f"{base}/api/v1/transports")
        n = len(transports or [])
        check("Transport adapters advertised", n, n >= 3)

        # 11. Research manifest endpoint answers (Phase 5).
        st, rstatus = http("GET", f"{base}/api/v1/research/status")
        check("Research status endpoint (HTTP)", st, st == 200)

        # 11b. Phase C integrity endpoint: the eight-domain EW battery measured
        #      live from the checkpoint, plus the delivery-plane anomaly strip.
        st, anomalies = http("GET", f"{base}/api/v1/research/anomalies?frames=16", timeout=30)
        dom = (anomalies or {}).get("domains") or []
        ops = (anomalies or {}).get("operational") or []
        model = (anomalies or {}).get("model") or {}
        summary = (anomalies or {}).get("summary") or {}
        check("Integrity endpoint returns 8 EW domains", len(dom), st == 200 and len(dom) == 8)
        check("Integrity endpoint returns 6 operational checks", len(ops), len(ops) == 6)
        check("Integrity endpoint reports checkpoint identity",
              model.get("sha256_short"), bool(model.get("manifest_verified")))
        check("Integrity summary totals every domain", summary.get("total"), summary.get("total") == 14)
        check("Integrity provenance is a live measurement",
              (anomalies or {}).get("provenance"),
              (anomalies or {}).get("provenance") == "LIVE_COMPUTED")

        # ------------------------------------------------------------------
        # 12. Live dispatch path (Phase 4 <-> Phase 3). The console flips the
        #     node onto the Motorola radio adapter; the delivery worker is a
        #     SEPARATE process, so success here proves the selection travels
        #     through shared storage rather than local memory.
        #     MOTOROLA_RADIO_APPROVED is unset, so the hardware bridge stays in
        #     dry-run — no RF is emitted.
        # ------------------------------------------------------------------
        st, active = http("GET", f"{base}/api/v1/transports/active")
        check("Outbound path defaults to simulation",
              (active or {}).get("mode"), st == 200 and (active or {}).get("is_live") is False)

        st, switched = http("POST", f"{base}/api/v1/transports/active",
                            {"transport_id": "motorola-mototrbo-01"})
        check("Console can select the Motorola radio path",
              (switched or {}).get("mode"),
              st == 200 and (switched or {}).get("is_live") is True)

        st, body3 = http("POST", f"{base}/api/v1/messages", {
            "sender_endpoint_id": "endpoint-a",
            "recipient_endpoint_id": "endpoint-b",
            "payload": "E2E-LIVE-PATH-PROOF",
            "client_idempotency_key": "e2e-live-001",
        })
        msg3 = (body3 or {}).get("message") if isinstance(body3, dict) and "message" in (body3 or {}) else body3
        mid3 = (msg3 or {}).get("message_id") if isinstance(msg3, dict) else None

        live_state = None
        deadline = time.time() + args.timeout
        while time.time() < deadline:
            st, msgs = http("GET", f"{base}/api/v1/messages?sender=endpoint-a")
            for m in (msgs or []):
                if m.get("message_id") == mid3:
                    live_state = m.get("current_state")
            if live_state in ("DELIVERED", "FAILED_FINAL", "EXPIRED"):
                break
            time.sleep(0.5)
        check("Message delivered over the live radio path", live_state, live_state == "DELIVERED")

        st, events3 = http("GET", f"{base}/api/v1/messages/{mid3}/events")
        modes = [
            (e.get("safe_metadata") or {}).get("transport_mode")
            for e in (events3 or [])
            if e.get("event_type") == "DELIVERY_ATTEMPT_STARTED"
        ]
        check("Worker honoured the shared transport switch", modes, modes == ["motorola-mototrbo-01"])

        st, reverted = http("POST", f"{base}/api/v1/transports/active", {"transport_id": None})
        check("Operator can return to the simulated link",
              (reverted or {}).get("mode"), st == 200 and (reverted or {}).get("is_live") is False)

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        try:
            os.close(log_file)
        except OSError:
            pass
        for p in (log_path, db, db + "-wal", db + "-shm"):
            try:
                os.remove(p)
            except OSError:
                pass

    print("-" * 78)
    passed = sum(1 for _, _, ok in results if ok)
    print(f"  RESULT: {passed}/{len(results)} integration checks passed")
    print(f"  OVERALL: {'INTEGRATION PASS' if ok_all else 'INTEGRATION FAIL'}")
    print("=" * 78)
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())

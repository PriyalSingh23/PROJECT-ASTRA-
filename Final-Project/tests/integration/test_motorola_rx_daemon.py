"""Tests for the Motorola sound-card listener.

The three properties worth protecting here are:

1. **The listener cannot transmit.** It is meant to run unattended as a systemd
   service, so there must be no path from the receive loop to the PTT line.
   The self-test is confined to the software loopback for the same reason.
2. **A retransmitted burst is one message.** The ingest idempotency key is
   derived from the decoded bytes, so radios repeating themselves (and operators
   repeating a callsign) do not fill the platform inbox with duplicates.
3. **The listener outlives the platform.** If the API is down or mid-restart,
   the failure is reported and the loop keeps listening. A transport adapter
   that dies when the backend restarts is useless in the field.

None of this needs hardware, so it all runs on a laptop and in CI.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import integration.motorola.hardware_bridge as hb

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DAEMON_PATH = os.path.join(PROJECT_ROOT, "scripts", "motorola_rx_daemon.py")


@pytest.fixture(scope="module")
def daemon():
    spec = importlib.util.spec_from_file_location("motorola_rx_daemon_under_test", DAEMON_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _decoded(text: str) -> dict:
    """A receive_voice() result shaped exactly like the real one."""
    body = text.encode("utf-8")
    return {
        "ok": True,
        "transport": "soundcard_voice",
        "payload": text,
        "payload_hex": body.hex(),
        "payload_bytes": len(body),
        "payload_is_utf8": True,
        "tms_crc_ok": True,
        "sync_score": 1.0,
        "phase_offset": 3,
    }


class ApiStub:
    """Records inbound POSTs and replies with a chosen status and body."""

    def __init__(self, status: int = 201, body: dict | None = None):
        self.requests: list = []
        self.status = status
        self.body = body if body is not None else {"message_id": "msg-0001", "is_new": True}
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length).decode("utf-8")
                outer.requests.append(
                    {
                        "path": self.path,
                        "headers": dict(self.headers),
                        "json": json.loads(raw or "{}"),
                    }
                )
                payload = json.dumps(outer.body).encode("utf-8")
                self.send_response(outer.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):  # keep the test output readable
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}"


def _dead_url() -> str:
    """A URL nothing is listening on: bind, capture the port, release it."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return f"http://127.0.0.1:{port}"


# ---------------------------------------------------------------------------
# Content-addressed idempotency
# ---------------------------------------------------------------------------
def test_idempotency_key_is_content_addressed(daemon):
    hex_a = b"FIELD TEST BURST 01".hex()
    assert daemon._idempotency_key(hex_a) == daemon._idempotency_key(hex_a)
    assert daemon._idempotency_key(hex_a) != daemon._idempotency_key(b"FIELD TEST BURST 02".hex())


def test_idempotency_key_is_a_sha256_of_the_frame(daemon):
    hex_a = b"FIELD TEST BURST 01".hex()
    expected = "radio-" + hashlib.sha256(hex_a.encode("ascii")).hexdigest()[:32]
    assert daemon._idempotency_key(hex_a) == expected


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------
def test_ingest_posts_text_with_key_and_token(daemon):
    with ApiStub() as api:
        result = daemon._ingest(api.url, "endpoint-a", "endpoint-b",
                                "SITREP GRID 8842", b"SITREP GRID 8842".hex(), "tok-123")

    assert result == {"ingested": True, "is_new": True, "message_id": "msg-0001"}
    assert len(api.requests) == 1
    req = api.requests[0]
    assert req["path"] == "/api/v1/messages"
    assert req["json"]["sender_endpoint_id"] == "endpoint-a"
    assert req["json"]["recipient_endpoint_id"] == "endpoint-b"
    assert req["json"]["payload"] == "SITREP GRID 8842"
    assert "payload_hex" not in req["json"]  # the hex stays local, for the log
    assert req["json"]["client_idempotency_key"] == daemon._idempotency_key(
        b"SITREP GRID 8842".hex())
    assert req["headers"].get("X-Endpoint-Token") == "tok-123"


def test_ingest_reports_a_duplicate_honestly(daemon):
    with ApiStub(status=200, body={"message_id": "msg-0001", "is_new": False}) as api:
        result = daemon._ingest(api.url, "endpoint-a", "endpoint-b", "again", b"again".hex(), None)
    assert result["ingested"] is True
    assert result["is_new"] is False


def test_ingest_survives_a_rejected_request(daemon):
    with ApiStub(status=400, body={"error": "Sender endpoint 'ghost' does not exist"}) as api:
        result = daemon._ingest(api.url, "ghost", "endpoint-b", "x", b"x".hex(), None)
    assert result["ingested"] is False
    assert "ghost" in result["error"]
    assert "400" in result["error"]


def test_ingest_survives_an_unreachable_api(daemon):
    result = daemon._ingest(_dead_url(), "endpoint-a", "endpoint-b", "x", b"x".hex(), None)
    assert result["ingested"] is False
    assert result["error"]


# ---------------------------------------------------------------------------
# Event log
# ---------------------------------------------------------------------------
def test_event_log_creates_dirs_and_appends(daemon, tmp_path):
    path = str(tmp_path / "nested" / "deeper" / "events.jsonl")
    daemon._append_jsonl(path, {"n": 1})
    daemon._append_jsonl(path, {"n": 2})

    lines = open(path, encoding="utf-8").read().strip().splitlines()
    assert [json.loads(line)["n"] for line in lines] == [1, 2]


def test_event_log_never_raises_on_an_unwritable_path(daemon, tmp_path):
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x")
    # Parent is a file, so makedirs must fail — and that must not escape.
    daemon._append_jsonl(str(blocker / "events.jsonl"), {"n": 1})


# ---------------------------------------------------------------------------
# The listener loop, driven through main()
# ---------------------------------------------------------------------------
def _stub_receive(text: str):
    def receive_voice(self, duration_s, save_wav=None):  # noqa: ARG001
        return _decoded(text)
    return receive_voice


def test_listener_ingests_a_decoded_message(daemon, monkeypatch, tmp_path):
    monkeypatch.setattr(hb.MotorolaHardwareBridge, "receive_voice",
                        _stub_receive("SITREP GRID 8842-1190"))
    log = str(tmp_path / "events.jsonl")

    with ApiStub() as api:
        rc = daemon.main(["--count", "1", "--api", api.url, "--log", log])

    assert rc == 0
    assert len(api.requests) == 1
    assert api.requests[0]["json"]["payload"] == "SITREP GRID 8842-1190"
    assert api.requests[0]["json"]["sender_endpoint_id"] == "endpoint-a"

    event = json.loads(open(log, encoding="utf-8").read().strip())
    assert event["payload"] == "SITREP GRID 8842-1190"
    assert event["ingest"]["message_id"] == "msg-0001"


def test_listener_never_keys_the_transmitter(daemon, monkeypatch):
    """The receive loop must not be able to reach the radio's PTT line."""
    monkeypatch.setattr(hb.MotorolaHardwareBridge, "receive_voice", _stub_receive("HELLO"))

    def forbidden(*_a, **_k):
        raise AssertionError("listener tried to play audio — it must be receive-only")

    monkeypatch.setattr(hb.SoundCardBackend, "play_audio", forbidden)

    with ApiStub() as api:
        rc = daemon.main(["--count", "1", "--api", api.url])

    assert rc == 0
    assert len(api.requests) == 1, "the decode should still have been ingested"


def test_selftest_transmits_nothing_and_keys_nothing(daemon, monkeypatch):
    # If self-test reaches for GPIO, this blows up loudly.
    def explode(pin):  # noqa: ARG001
        raise AssertionError("self-test must not touch GPIO")

    monkeypatch.setattr(hb, "_load_gpio", explode)
    monkeypatch.setattr(hb, "GPIO", None, raising=False)

    with ApiStub() as api:
        rc = daemon.main(["--selftest", "--api", api.url, "--sender", "endpoint-a"])

    assert rc == 0
    assert len(api.requests) == 1, "the loopback burst should have been decoded and ingested"


def test_no_ingest_flag_means_no_request(daemon, monkeypatch):
    monkeypatch.setattr(hb.MotorolaHardwareBridge, "receive_voice", _stub_receive("QUIET"))
    with ApiStub() as api:
        rc = daemon.main(["--count", "1", "--no-ingest", "--api", api.url])
    assert rc == 0
    assert api.requests == []

#!/usr/bin/env python3
"""Motorola radio listener — receive-only, feeds decoded traffic into SHADOWCOMM.

This is the always-on half of the ground-comms deployment. It records the
far-end radio's speaker output through a USB sound card, demodulates the audio
modem, and — when a message decodes cleanly — submits it to the local SHADOWCOMM
messaging API so it lands in the platform's inbox alongside everything else.

It owns no transmitter. The `sound-card` backend is used without ``send``, so
there is no code path here that can key a radio. That is deliberate: this
process is meant to run unattended, and an unattended process must not be able
to transmit.

    python scripts/motorola_rx_daemon.py                       # listen, ingest
    python scripts/motorola_rx_daemon.py --count 20            # bounded run
    python scripts/motorola_rx_daemon.py --no-ingest           # decode + log only
    python scripts/motorola_rx_daemon.py --seconds 5 --log /var/log/shadowcomm/motorola-rx.log

Ingest deduplication
--------------------
The idempotency key is derived from the *content* of the decoded frame, not from
the moment it arrived. Radios retransmit, and an operator repeats a callsign; if
the same bytes come through twice, the platform must treat that as one message,
not two. A content hash gives exactly that, for free.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from integration.motorola.hardware_bridge import (  # noqa: E402
    MotorolaHardwareBridge,
    SoundCardBackend,
)

BANNER = "SHADOWCOMM · MOTOROLA RADIO LISTENER (receive-only)"

_stop = False


def _handle_signal(signum: int, _frame: Any) -> None:  # noqa: ARG001
    global _stop
    _stop = True
    print(f"\n[listener] signal {signum} — finishing this window and stopping", flush=True)


def _idempotency_key(payload_hex: str) -> str:
    """Stable key for a decoded frame, so retransmissions dedupe."""
    digest = hashlib.sha256(payload_hex.encode("ascii")).hexdigest()[:32]
    return f"radio-{digest}"


def _ingest(api: str, sender: str, recipient: str, text: str,
            payload_hex: str, token: Optional[str]) -> Dict[str, Any]:
    """Submit one decoded message to the local SHADOWCOMM API.

    Returns a small status dict rather than raising, because a transport
    adapter that dies because the platform restarted is a bad neighbour. The
    decoded text is submitted when it is valid UTF-8 (what an inbox should
    show) and the hex otherwise, so binary is never lost.
    """
    body = {
        "client_idempotency_key": _idempotency_key(payload_hex),
        "sender_endpoint_id": sender,
        "recipient_endpoint_id": recipient,
        "payload": text if text else payload_hex,
        "message_type": "TEXT",
        "priority": 1,
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{api.rstrip('/')}/api/v1/messages",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    if token:
        req.add_header("X-Endpoint-Token", token)

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            response = json.loads(resp.read().decode("utf-8") or "{}")
            return {"ingested": True, "is_new": response.get("is_new", True),
                    "message_id": response.get("message_id")}
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = json.loads(e.read().decode("utf-8")).get("error", "")
        except Exception:  # noqa: BLE001
            pass
        return {"ingested": False, "error": f"HTTP {e.code}: {detail or e.reason}"}
    except Exception as e:  # noqa: BLE001 - the listener must outlive the API
        return {"ingested": False, "error": f"{type(e).__name__}: {e}"}


def _append_jsonl(path: str, record: Dict[str, Any]) -> None:
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:  # noqa: BLE001 - logging must never stop the listener
        print(f"[listener] could not write log: {e}", flush=True)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Receive-only Motorola listener that feeds SHADOWCOMM.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--seconds", type=float, default=3.0,
                   help="seconds of audio per listening window (default 3)")
    p.add_argument("--loop", action="store_true",
                   help="keep listening until stopped (default if run as a service)")
    p.add_argument("--count", type=int, default=0,
                   help="stop after N windows (0 = unlimited)")
    p.add_argument("--save-wav", help="write each window to WAV (diagnostics only; "
                                      "disk-heavy, do not leave on)")
    p.add_argument("--log", help="append one JSON line per decoded message to this file")
    p.add_argument("--verbose", action="store_true",
                   help="print levels for every empty window, not just the first")
    p.add_argument("--selftest", action="store_true",
                   help="inject one burst through the software loopback and ingest it, "
                        "proving the listener -> platform path before touching a radio")

    g = p.add_argument_group("audio hardware")
    p.add_argument("--backend", default=os.environ.get("MOTOROLA_BACKEND", "soundcard"),
                   choices=["soundcard", "mnis_udp", "gpio_ptt", "auto"])
    p.add_argument("--audio-in", default=os.environ.get("MOTOROLA_AUDIO_IN", "default"))
    p.add_argument("--audio-out", default=os.environ.get("MOTOROLA_AUDIO_OUT", "default"))
    p.add_argument("--gpio-pin", type=int, default=int(os.environ.get("MOTOROLA_PTT_GPIO", "17")))
    p.add_argument("--sample-rate", type=int, default=int(os.environ.get("MOTOROLA_AUDIO_FS", "48000")))

    p.add_argument("--ingest", dest="ingest", action="store_true", default=True,
                   help="submit decoded messages to the local API (default)")
    p.add_argument("--no-ingest", dest="ingest", action="store_false",
                   help="decode and log only; touch no platform state")
    p.add_argument("--api", default=os.environ.get("SHADOWCOMM_API", "http://127.0.0.1:5050"),
                   help="SHADOWCOMM base URL (default http://127.0.0.1:5050)")
    p.add_argument("--sender", default=os.environ.get("MOTOROLA_SENDER_EP", "endpoint-a"),
                   help="sender endpoint id recorded for received traffic")
    p.add_argument("--recipient", default=os.environ.get("MOTOROLA_RECIPIENT_EP", "endpoint-b"),
                   help="recipient endpoint id (this node)")
    p.add_argument("--token", default=os.environ.get("MOTOROLA_ENDPOINT_TOKEN"),
                   help="X-Endpoint-Token for the sender endpoint, if the API requires auth")
    return p


def main(argv: Optional[list] = None) -> int:
    global _stop, _token
    args = build_parser().parse_args(argv)
    _token = args.token

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    if args.selftest:
        # One injected burst through the software loopback: nothing is played,
        # nothing is keyed, no radio is involved.
        args.count = 1
        args.loop = False

    loop = args.loop or args.count == 0

    print(BANNER)
    print(f"  {time.strftime('%Y-%m-%d %H:%M:%S')}  ·  receive-only, keys nothing")
    print(f"  window       : {args.seconds:.1f} s")
    print(f"  duration     : {'until stopped' if loop and not args.count else f'{args.count} window(s)'}")
    if args.selftest:
        print("  mode         : SELF-TEST — one burst injected via software loopback")
    print(f"  ingest       : {'yes -> ' + args.api if args.ingest else 'no (decode + log only)'}")
    if args.ingest:
        print(f"  attribution  : sender={args.sender} recipient={args.recipient}")
    if args.log:
        print(f"  event log    : {args.log}")
    print()

    sound = SoundCardBackend(
        gpio_pin=args.gpio_pin,
        audio_out=args.audio_out,
        audio_in=args.audio_in,
        sample_rate=args.sample_rate,
        self_loopback=args.selftest,
    )
    bridge = MotorolaHardwareBridge(backend="soundcard", sound=sound)

    if args.selftest:
        probe = "LISTENER SELF-TEST — 1/1 GRID 31U-DQ-8842-1190"
        sent = bridge.transmit_voice(args.recipient, probe.encode())
        print(f"  injected     : {probe!r}")
        print(f"  loopback     : {sent.get('details')}")
        print()

    decoded = 0
    ingested = 0
    windows = 0
    fails = 0

    while not _stop:
        windows += 1
        wav = None
        if args.save_wav:
            wav = args.save_wav if windows == 1 else args.save_wav.replace(".wav", f"-{windows}.wav")
        rx = bridge.receive_voice(args.seconds, save_wav=wav)
        stamp = time.strftime("%H:%M:%S")

        if rx.get("ok"):
            fails = 0
            decoded += 1
            text = rx.get("payload") or ""
            record: Dict[str, Any] = {
                "received_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "payload": text,
                "payload_hex": rx.get("payload_hex"),
                "payload_bytes": rx.get("payload_bytes"),
                "tms_crc_ok": rx.get("tms_crc_ok"),
                "sync_score": rx.get("sync_score"),
                "phase_offset": rx.get("phase_offset"),
                "window": windows,
            }

            print(f"  [{stamp}] DECODED  {text!r}", flush=True)
            print(f"            bytes={rx.get('payload_bytes')} "
                  f"crc={rx.get('tms_crc_ok')} sync={rx.get('sync_score')}", flush=True)

            if args.ingest:
                result = _ingest(args.api, args.sender, args.recipient,
                                 text, rx.get("payload_hex") or "", args.token)
                record["ingest"] = result
                if result.get("ingested"):
                    ingested += 1
                    dup = "" if result.get("is_new") else " (duplicate — already known)"
                    print(f"            ingested -> {result.get('message_id')}{dup}", flush=True)
                else:
                    print(f"            INGEST FAILED :: {result.get('error')}", flush=True)

            if args.log:
                _append_jsonl(args.log, record)

        else:
            fails += 1
            # A silent channel is the normal case, so say it once and then only
            # occasionally. A journal that repeats "nothing heard" 20 times a
            # minute is a journal nobody reads.
            if args.verbose or fails == 1 or fails % 20 == 0:
                print(f"  [{stamp}] nothing to decode :: {rx.get('detail') or rx.get('error')}",
                      flush=True)
                lv = rx.get("levels") or {}
                if lv:
                    print(f"            audio rms={lv.get('rms')} peak={lv.get('peak')} "
                          f"clipped={lv.get('clipped_fraction')}", flush=True)
                    print(f"            {lv.get('verdict')}", flush=True)

        if args.count and windows >= args.count:
            break

    print()
    print("=" * 72)
    print(f"RESULT: {decoded} decoded, {ingested} ingested, {windows} window(s) listened")
    print("=" * 72)
    return 0


_token: Optional[str] = None


if __name__ == "__main__":
    sys.exit(main())

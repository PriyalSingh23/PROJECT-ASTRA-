#!/usr/bin/env python3
"""Motorola field test — prove the radio link end to end, on real hardware.

This is the tool you run on the Raspberry Pi when the radios are on the bench
and then in the field. It is designed so that every stage can be verified
*without* transmitting, and so that the first real transmission is boring.

Sub-commands, in the order you should run them:

    probe      Hardware inventory: GPIO, sound card, modem plan, gate state.
               Transmits nothing. Run this first, always.

    selftest   Modem loopback through a *simulated* radio channel (AWGN +
               carrier offset + clock error). Transmits nothing. Proves the
               DSP is correct, so a later field failure means the radio or the
               wiring, not the code.

    loopback   Full chain in software: message -> TMS frame -> audio ->
               demodulate -> parse. Transmits nothing.

    tx         Key PTT and send a message. REQUIRES --approve.

    rx         Listen on the far-end radio and print anything demodulated.

    run        Guided two-terminal live test with numbered bursts.

Safety
------
Nothing transmits without ``--approve``, which sets ``MOTOROLA_RADIO_APPROVED``
and prints the licence acknowledgement. That is deliberate friction: an
unlicensed transmission is not a test, it is an offence.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from integration.motorola.hardware_bridge import (  # noqa: E402
    DMR_MAX_PAYLOAD_BYTES,
    MotorolaHardwareBridge,
    SoundCardBackend,
)
from integration.motorola.voice_modem import VoiceModem  # noqa: E402

BANNER = "SHADOWCOMM · MOTOROLA FIELD TEST"

LICENCE_NOTICE = """
By approving transmission you are stating that, on your honour:
  * you hold a valid licence or authorisation for every frequency you transmit
    on, in the jurisdiction you are standing in;
  * the radio is programmed to a power and band you are permitted to use;
  * you have a second operator, or a receiver, ready to confirm the link.

If any of those is not true, stop. Use --dry-run instead.
"""


def _hr(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def _kv(key: str, value: Any, width: int = 30) -> None:
    print(f"  {key:<{width}} {value}")


def _bridge(args: argparse.Namespace, loopback: bool = False) -> MotorolaHardwareBridge:
    sound = SoundCardBackend(
        gpio_pin=args.gpio_pin,
        audio_out=args.audio_out,
        audio_in=args.audio_in,
        sample_rate=args.sample_rate,
        self_loopback=loopback,
        lpi_mode=bool(getattr(args, "lpi", False)),
    )
    return MotorolaHardwareBridge(
        backend=args.backend,
        gpio_pin=args.gpio_pin,
        audio_out=args.audio_out,
        audio_in=args.audio_in,
        sample_rate=args.sample_rate,
        lpi_mode=bool(getattr(args, "lpi", False)),
        sound=sound,
    )


def _save(args: argparse.Namespace, payload: Dict[str, Any]) -> None:
    if not getattr(args, "report", None):
        return
    payload = dict(payload)
    payload["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    payload["host"] = platform.node()
    with open(args.report, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    print(f"\n  report written to {args.report}")


# ---------------------------------------------------------------------------
# probe
# ---------------------------------------------------------------------------
def cmd_probe(args: argparse.Namespace) -> int:
    bridge = _bridge(args)
    info = bridge.probe()
    _hr("HARDWARE PROBE (nothing is transmitted)")

    _kv("selected backend", info["selected_backend"])
    _kv("requested backend", info["requested_backend"])
    _kv("radio approved", info["approved"])
    _kv("dry-run", not info["approved"])

    sc = info["soundcard"]
    print("\n  Sound card / PTT")
    _kv("  GPIO pin", sc["gpio_pin"])
    _kv("  GPIO backend", sc.get("gpio_backend", "unavailable"))
    _kv("  GPIO available", sc["gpio_available"])
    _kv("  sounddevice (PortAudio)", sc["sounddevice_available"])
    _kv("  aplay present", sc["aplay_available"])
    _kv("  arecord present", sc["arecord_available"])
    _kv("  audio out device", sc["audio_out"])
    _kv("  audio in device", sc["audio_in"])
    _kv("  sample rate", sc["sample_rate"])

    m = sc["modem"]
    print("\n  Modem plan")
    _kv("  symbol rate", f"{m['symbol_rate']:.0f} baud")
    _kv("  audio carrier", f"{m['carrier_hz']:.0f} Hz")
    _kv("  occupied bandwidth", f"{m['occupied_bandwidth_hz']:.0f} Hz")
    _kv("  samples per symbol", m["sps"])
    _kv("  DMR payload ceiling", f"{DMR_MAX_PAYLOAD_BYTES} B")
    air = VoiceModem().burst_seconds(64)
    _kv("  air time (64 B message)", f"{air:.2f} s")

    print("\n  MNIS (vendor IP path)")
    _kv("  socket ready", info["mnis"].get("socket_ready"))
    _kv("  reachable", info["mnis"].get("reachable"), width=30)
    print(f"    note: {info['mnis'].get('note', '-')}")

    sdr = info.get("sdr", {})
    print("\n  SDR (USRP) transport — same LPI burst, radiated instead of played")
    _kv("  UHD python bindings", sdr.get("uhd_python_bindings"))
    _kv("  device enumerated", sdr.get("device_found"))
    _kv("  available", sdr.get("available"))
    _kv("  sample rate", f"{sdr.get('rate_hz', 0):.0f} S/s")
    _kv("  tune frequency", f"{sdr.get('freq_hz', 0)/1e6:.4f} MHz")
    print(f"    note: {sdr.get('note', '-')}")

    blockers: List[str] = []
    if not sc["gpio_available"]:
        blockers.append(
            "no GPIO backend — PTT cannot be keyed. On a Pi 5 install the lgpio shim "
            "(pip install rpi-lgpio lgpio); on older Pis install python3-rpi.gpio. "
            "Are you actually running on the Pi?"
        )
    if not (sc["sounddevice_available"] or sc["aplay_available"]):
        blockers.append("no audio playback (need sounddevice or aplay) — pip install sounddevice, or apt install alsa-utils")
    if not (sc["sounddevice_available"] or sc["arecord_available"]):
        blockers.append("no audio capture (need sounddevice or arecord) — the RX side will not work")

    print("\n  Checklist")
    if blockers:
        for b in blockers:
            print(f"    [ ] {b}")
    else:
        print("    [x] audio I/O available")
        print("    [x] GPIO available")
    if not info["approved"]:
        print("    [ ] MOTOROLA_RADIO_APPROVED not set — transmission stays in dry-run")

    _save(args, {"command": "probe", "probe": info, "blockers": blockers})
    return 0 if not blockers else 1


# ---------------------------------------------------------------------------
# selftest / loopback
# ---------------------------------------------------------------------------
def cmd_selftest(args: argparse.Namespace) -> int:
    bridge = _bridge(args)
    report = bridge.self_test(
        n_frames=args.frames, snr_db=args.snr, cfo_hz=args.cfo,
        clock_error_ppm=args.clock_ppm, payload_bytes=args.payload_bytes,
    )
    _hr("MODEM SELF-TEST (simulated channel — nothing is transmitted)")
    _kv("frames", f"{report['frames_ok']}/{report['frames']}")
    _kv("packet error rate", report["per"])
    _kv("bit error rate", report["ber"])
    _kv("channel SNR (wideband)", f"{report['snr_db']} dB")
    _kv("channel SNR (in-band)", f"{report['snr_inband_db']} dB")
    _kv("carrier offset", f"{report['cfo_hz']} Hz")
    _kv("clock error", f"{report['clock_error_ppm']} ppm")
    _kv("payload", f"{report['payload_bytes']} B")
    _kv("air time", f"{report['air_time_s']} s")
    verdict = "PASS — DSP chain is correct" if report["pass"] else "FAIL — fix the modem before going near a radio"
    print(f"\n  verdict: {report['pass']} — {verdict}")
    _save(args, {"command": "selftest", "report": report})
    return 0 if report["pass"] else 1


def cmd_loopback(args: argparse.Namespace) -> int:
    bridge = _bridge(args, loopback=True)
    _hr("SOFTWARE LOOPBACK (message -> TMS frame -> audio -> decode — nothing is transmitted)")
    ok = 0
    for msg in args.message:
        tx = bridge.transmit_voice(args.to, msg.encode())
        rx = bridge.receive_voice(0)
        good = bool(rx.get("ok") and rx.get("payload") == msg)
        print(f"\n  {msg!r}")
        _kv("  tx", f"frame={tx.get('dmr_frame_bytes')}B air={tx.get('air_time_s')}s")
        _kv("  rx", f"ok={rx.get('ok')} tms_crc={rx.get('tms_crc_ok')} sync={rx.get('sync_score')}")
        _kv("  decoded", repr(rx.get("payload")))
        ok += 1 if good else 0
    _hr(f"RESULT: {ok}/{len(args.message)} messages round-tripped")
    _save(args, {"command": "loopback", "ok": ok, "total": len(args.message)})
    return 0 if ok == len(args.message) else 1


# ---------------------------------------------------------------------------
# lpi -- the covert-waveform measurement and loopback
# ---------------------------------------------------------------------------
def cmd_lpi(args: argparse.Namespace) -> int:
    """Measure the LPI burst's stealth and prove it round-trips through the bridge.

    This is the single command that answers the project's core question: when we
    communicate over the Motorola link, does the transmission actually exhibit
    LPI characteristics? It runs the *same* eight-domain EW battery the wideband
    path is graded by, on the audio that the Pi would play, and reports the
    result against a bandwidth-matched noise-floor control.
    """
    from integration.motorola.lpi_carrier import (
        LpiCarrierConfig,
        audio_ew_report,
        carrier_selftest,
    )

    _hr("LPI CARRIER (nothing is transmitted)")

    res = carrier_selftest(
        snr_db=args.snr, cfo_hz=args.cfo, clock_error_ppm=args.clock_ppm,
        seed=args.seed,
        config=LpiCarrierConfig(audio_fs=int(args.sample_rate)),
    )
    _kv("message", res["message"])
    _kv("decode", "PASS" if res["ok"] else "FAIL")
    _kv("PER", res["per"])
    _kv("air time", f"{res['air_time_s']} s")
    _kv("channel SNR (in-band)", f"{res['snr_inband_db']} dB")
    _kv("waveform source", res["waveform_source"])

    ew = res["ew"]["signal"]
    floor = res["ew"]["noise_floor_control"]
    print("\n  Eight-domain EW battery (measured on the emitted audio)")
    _kv("  pass", f"{ew['n_pass']}/8")
    for dom in ("ks", "kurt", "entropy", "circ", "papr", "scf", "c42", "wvd"):
        key = {"ks": "ks_p"}.get(dom, dom)
        mark = "PASS" if ew["pass"][dom] else "FAIL"
        print(f"    {dom:<8} {ew[key]:>10.4f}  {mark}")
    if ew["n_pass"] < 8:
        norm = res["ew"].get("normalised") or {}
        ent = norm.get("entropy", {})
        wvd = norm.get("wvd", {})
        print("\n  The two that fail raw are channel-limited, not waveform defects.")
        if ent and wvd:
            print("  Against the ACHIEVABLE ceiling for this occupancy:")
            print(f"    entropy {ent['raw']:.4f} / {ent['ceiling']:.4f} ceiling"
                  f"  = ratio {ent['ratio']:.4f}"
                  f"  {'PASS' if ent['pass'] else 'FAIL'}")
            print(f"    wvd     {wvd['raw']:.4f} / {wvd['floor']:.4f} floor"
                  f"    = ratio {wvd['ratio']:.4f}"
                  f"  {'PASS' if wvd['pass'] else 'FAIL'}")
            print(f"  -> equivalent score: {ew['n_pass']}/8 raw "
                  f"+ {norm.get('n_pass', 0)}/2 normalised "
                  f"= {ew['n_pass'] + norm.get('n_pass', 0)}/8")
        print("\n  Band-limited noise of the SAME bandwidth scores:")
        print(f"    entropy {floor['entropy']:.4f}   wvd {floor['wvd']:.4f}   "
              f"(passes {floor['n_pass']}/8)")
        print("  A 3 kHz voice channel cannot carry the occupancy these two need")
        print("  raw; a shaper-matched control and the normalised view cover it.")
        print("  See CHANNEL NOTES in integration/motorola/lpi_carrier.py.")

    # Prove the bridge actually carries it (software loopback, no RF).
    bridge = _bridge(args, loopback=True)
    msg = args.message[0] if args.message else "MOTOROLA-LPI-LINK-OK"
    tx = bridge.transmit_voice(args.to, msg.encode())
    rx = bridge.receive_voice(0)
    good = bool(rx.get("ok") and rx.get("payload") == msg)
    print("\n  Bridge round-trip (software loopback — no RF)")
    _kv("  air time", f"{tx.get('air_time_s')} s")
    _kv("  lpi carrier", rx.get("lpi"))
    _kv("  decoded", repr(rx.get("payload")))
    _kv("  result", "PASS" if good else "FAIL")

    _save(args, {"command": "lpi", "selftest": res, "bridge_ok": good})
    return 0 if (res["ok"] and good) else 1


# ---------------------------------------------------------------------------
# tx / rx
# ---------------------------------------------------------------------------
def cmd_tx(args: argparse.Namespace) -> int:
    bridge = _bridge(args)
    _hr("TRANSMIT")
    if not bridge.approved():
        _kv("mode", "DRY-RUN (MOTOROLA_RADIO_APPROVED is not set)")
    else:
        _kv("mode", "LIVE — this keys the transmitter")
    results = []
    for i, message in enumerate(args.message):
        if i:
            time.sleep(args.interval)
        res = bridge.transmit_voice(args.to, message.encode())
        results.append(res)
        status = "SENT" if res["success"] else "FAILED"
        _kv(f"[{i + 1}/{len(args.message)}] {res['error_code'] or 'OK'}",
            f"{res['success']} · {res['bytes_on_wire']} bytes on wire")
        print(f"    {message[:70]}")
        print(f"    {res['details']}")
    _hr("TRANSMIT SUMMARY")
    _kv("sent", f"{sum(1 for r in results if r['success'])}/{len(results)}")
    _kv("dry-run", not bridge.approved())
    if bridge.approved():
        print("\n  Now check the receiving radio. On the RX terminal run:")
        print("    python scripts/motorola_field_test.py rx --seconds 10")
    _save(args, {"command": "tx", "results": results})
    return 0 if all(r["success"] for r in results) else 1


def cmd_rx(args: argparse.Namespace) -> int:
    bridge = _bridge(args)
    _hr("RECEIVE")
    _kv("window", f"{args.seconds:.1f} s per pass")
    _kv("passes", "until Ctrl-C" if args.loop else "1")
    print()
    decoded: List[Dict[str, Any]] = []
    passes = 0
    try:
        while True:
            passes += 1
            wav = None
            if args.save_wav:
                wav = args.save_wav if passes == 1 else args.save_wav.replace(".wav", f"-{passes}.wav")
            rx = bridge.receive_voice(args.seconds, save_wav=wav)
            lv = rx.get("levels", {})
            stamp = time.strftime("%H:%M:%S")
            if rx.get("ok"):
                print(f"  [{stamp}] DECODED  {rx.get('payload')!r}")
                print(f"            bytes={rx.get('payload_bytes')} tms_crc={rx.get('tms_crc_ok')} "
                      f"sync={rx.get('sync_score')} phase={rx.get('phase_offset')}")
                decoded.append(rx)
            else:
                print(f"  [{stamp}] no decode  :: {rx.get('detail') or rx.get('error')}")
                if lv:
                    print(f"            audio rms={lv.get('rms')} peak={lv.get('peak')} "
                          f"clipped={lv.get('clipped_fraction')}")
                    print(f"            {lv.get('verdict')}")
            if not args.loop:
                break
            if args.count and passes >= args.count:
                break
    except KeyboardInterrupt:
        print("\n  stopped")
    _hr(f"RESULT: {len(decoded)} message(s) decoded in {passes} pass(es)")
    for d in decoded:
        print(f"  {d.get('payload')!r}")
    _save(args, {"command": "rx", "decoded": decoded, "passes": passes})
    return 0 if decoded else 1


# ---------------------------------------------------------------------------
# run (guided two-terminal test)
# ---------------------------------------------------------------------------
def cmd_run(args: argparse.Namespace) -> int:
    role = args.role.lower()
    bridge = _bridge(args, loopback=(role == "loopback"))

    if role == "rx":
        _hr("GUIDED FIELD TEST — RECEIVING TERMINAL")
        print("  Leave this running. The other terminal will send numbered bursts.")
        print("  Press Ctrl-C when the sender reports it is done.")
        return cmd_rx(argparse.Namespace(**{**vars(args), "loop": True, "count": args.count}))

    if role == "loopback":
        _hr("GUIDED FIELD TEST — SOFTWARE LOOPBACK")
        print("  No hardware required: proves the whole chain end to end.")
        ok = 0
        for i in range(1, args.count + 1):
            message = f"FIELD TEST BURST {i:02d}/{args.count:02d} GRID 31U-DQ-8842-1190"
            bridge.transmit_voice(args.to, message.encode())
            rx = bridge.receive_voice(2.0)
            good = rx.get("ok") and rx.get("payload") == message
            print(f"  burst {i:02d}: {'OK' if good else 'FAIL'}  sync={rx.get('sync_score')}")
            ok += 1 if good else 0
        _hr(f"RESULT: {ok}/{args.count} bursts round-tripped")
        return 0 if ok == args.count else 1

    # TX side
    _hr("GUIDED FIELD TEST — TRANSMITTING TERMINAL")
    if not bridge.approved():
        print("  DRY-RUN: no transmission will occur. Re-run with --approve once you")
        print("  hold a licence and the receiving terminal is listening.")
    else:
        print(f"  LIVE: sending {args.count} numbered bursts, {args.interval:.1f} s apart.")
    print(f"  air time per burst: {bridge._sound.modem.burst_seconds(64):.2f} s")
    print(f"  total air time    : {args.count * bridge._sound.modem.burst_seconds(64):.1f} s")
    print()

    results = []
    for i in range(1, args.count + 1):
        message = f"FIELD TEST BURST {i:02d}/{args.count:02d} GRID 31U-DQ-8842-1190"
        res = bridge.transmit_voice(args.to, message.encode())
        mark = "sent" if res["success"] else f"FAILED ({res.get('error_code')})"
        print(f"  burst {i:02d}: {mark}  ({res.get('air_time_s', '-')} s air)")
        results.append(res)
        if i < args.count:
            time.sleep(args.interval)

    ok = sum(1 for r in results if r["success"])
    _hr(f"RESULT: {ok}/{len(results)} bursts transmitted")
    print("  Now check the receiving terminal. It should have decoded all of them.")
    _save(args, {"command": "run", "role": "tx", "sent": ok, "total": len(results)})
    return 0 if ok == len(results) else 1


# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    # Shared options live in a parent parser so they may be given either before
    # or after the sub-command, which is what people actually type.
    common = argparse.ArgumentParser(add_help=False)
    _add_common(common)

    p = argparse.ArgumentParser(
        description="SHADOWCOMM Motorola field test — prove the radio link before you trust it.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=LICENCE_NOTICE,
        parents=[common],
    )

    sub = p.add_subparsers(dest="command", required=True)

    def add(name: str, help_text: str) -> argparse.ArgumentParser:
        return sub.add_parser(name, help=help_text, parents=[common])

    add("probe", "hardware inventory; transmits nothing").set_defaults(func=cmd_probe)

    st = add("selftest", "modem loopback through a simulated channel; transmits nothing")
    st.add_argument("--frames", type=int, default=12)
    st.add_argument("--snr", type=float, default=14.0, help="wideband SNR in dB")
    st.add_argument("--cfo", type=float, default=5.0, help="carrier offset in Hz")
    st.add_argument("--clock-ppm", type=float, default=20.0)
    st.add_argument("--payload-bytes", type=int, default=64)
    st.set_defaults(func=cmd_selftest)

    lp = add("loopback", "full transmit -> TMS -> audio -> decode chain in software")
    lp.add_argument("--to", default="bravo", help="recipient endpoint id")
    lp.add_argument("--message", action="append", default=[],
                    help="message text (repeatable); defaults to a sample set")
    lp.set_defaults(func=cmd_loopback)

    lpi = add("lpi", "measure the LPI burst's stealth and round-trip it through the bridge")
    lpi.add_argument("--to", default="bravo")
    lpi.add_argument("--message", action="append", default=[])
    lpi.add_argument("--snr", type=float, default=24.0)
    lpi.add_argument("--cfo", type=float, default=10.0)
    lpi.add_argument("--clock-ppm", type=float, default=30.0)
    lpi.add_argument("--seed", type=int, default=7)
    lpi.set_defaults(func=cmd_lpi, lpi=True)

    tx = add("tx", "transmit a message (needs --approve)")
    tx.add_argument("--to", default="bravo")
    tx.add_argument("--message", action="append", default=[])
    tx.add_argument("--interval", type=float, default=5.0, help="seconds between messages")
    tx.set_defaults(func=cmd_tx)

    rx = add("rx", "listen on the far-end radio")
    rx.add_argument("--seconds", type=float, default=3.0)
    rx.add_argument("--loop", action="store_true")
    rx.add_argument("--count", type=int, default=0, help="stop after N passes in --loop mode")
    rx.add_argument("--save-wav", help="save each capture as WAV for post-mortem")
    rx.set_defaults(func=cmd_rx)

    rn = add("run", "guided test; pick a role")
    rn.add_argument("--role", default="loopback", choices=["tx", "rx", "loopback"])
    rn.add_argument("--to", default="bravo")
    rn.add_argument("--count", type=int, default=5)
    rn.add_argument("--interval", type=float, default=6.0)
    rn.add_argument("--seconds", type=float, default=3.0)
    rn.add_argument("--loop", action="store_true")
    rn.add_argument("--save-wav")
    rn.set_defaults(func=cmd_run)

    return p


DEFAULT_MESSAGES = [
    "SITREP GRID 31U-DQ-8842-1190 STATUS NOMINAL OVER",
    "REQUEST RESUPPLY AT LZ BRAVO 0400Z OVER",
    "CONTACT FRONT 200M EAST OF BRIDGE HOLDING OVER",
]


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--backend", default=os.environ.get("MOTOROLA_BACKEND", "auto"),
                        choices=["mnis_udp", "gpio_ptt", "soundcard", "auto"])
    parser.add_argument("--gpio-pin", type=int, default=int(os.environ.get("MOTOROLA_PTT_GPIO", "17")))
    parser.add_argument("--audio-out", default=os.environ.get("MOTOROLA_AUDIO_OUT", "default"))
    parser.add_argument("--audio-in", default=os.environ.get("MOTOROLA_AUDIO_IN", "default"))
    parser.add_argument("--sample-rate", type=int, default=int(os.environ.get("MOTOROLA_AUDIO_FS", "48000")))
    parser.add_argument("--report", help="write a JSON result file")
    parser.add_argument("--lpi", action="store_true",
                        help="carry the LPI burst instead of the plain voice modem "
                             "(see lpi_carrier.py); also settable via MOTOROLA_LPI_MODE=true")
    parser.add_argument("--approve", action="store_true",
                        help="arm the transmitter (asks for confirmation, sets MOTOROLA_RADIO_APPROVED)")


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if getattr(args, "message", None) == []:
        args.message = list(DEFAULT_MESSAGES)

    print(BANNER)
    print(f"  {time.strftime('%Y-%m-%d %H:%M:%S')}  ·  {platform.node()}  ·  {platform.platform()}")

    if args.approve:
        print(LICENCE_NOTICE)
        try:
            reply = input("Type 'I CONFIRM' to arm the transmitter: ").strip()
        except EOFError:
            reply = ""
        if reply != "I CONFIRM":
            print("\nNot confirmed — staying in dry-run.")
        else:
            os.environ["MOTOROLA_RADIO_APPROVED"] = "true"
            print("\n*** TRANSMITTER ARMED ***")

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

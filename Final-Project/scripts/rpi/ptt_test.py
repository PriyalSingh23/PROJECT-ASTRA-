#!/usr/bin/env python3
"""Safe Raspberry Pi GPIO PTT pin test — keys PTT briefly, sends NO data.

Run this to confirm your opto-isolator wiring before any real transmission.

    python scripts/rpi/ptt_test.py --pin 17 --confirm

Without --confirm it only reports whether a GPIO backend is present and exits.

Uses the same loader as the transmit path (``RPi.GPIO`` first, then the ``lgpio``
shim), so this works on a Raspberry Pi 5, where ``RPi.GPIO`` cannot reach the
pins behind the RP1 southbridge.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from integration.motorola.hardware_bridge import _load_gpio, gpio_backend_name  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pin", type=int, default=17, help="BCM GPIO pin wired to PTT (default 17)")
    ap.add_argument("--ms", type=int, default=200, help="How long to hold PTT (default 200ms)")
    ap.add_argument("--confirm", action="store_true", help="Actually key the pin")
    args = ap.parse_args()

    gpio = _load_gpio(args.pin)
    if not gpio:
        print("[info] No GPIO backend available — not running on a Raspberry Pi. Nothing keyed.")
        print("       On the Pi: sudo apt install python3-lgpio   (Pi 5) "
              "or python3-rpi.gpio (Pi 4 and earlier)")
        return 0 if not args.confirm else 2

    backend = gpio_backend_name(gpio)
    print(f"[ok] GPIO backend: {backend}")
    if not args.confirm:
        print(f"[ok] Pin BCM{args.pin} configured LOW (PTT unkeyed).")
        print("     Re-run with --confirm to pulse PTT for wiring verification.")
        gpio.cleanup()
        return 0

    print(f"[tx] Keying PTT on BCM{args.pin} for {args.ms} ms (NO data sent)...")
    try:
        gpio.output(args.pin, gpio.HIGH)
        time.sleep(args.ms / 1000.0)
    finally:
        gpio.output(args.pin, gpio.LOW)  # always unkey
        time.sleep(0.05)
        gpio.cleanup()
    print("[ok] PTT released.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""SDR (USRP / UHD) transport for the Motorola LPI burst.

Why this file exists
--------------------
The Motorola path and the wideband SDR path used to be two separate things: the
radio bridge only knew how to key a Motorola handset through a sound card, and
``lpi_v4/tx_usrp.py`` only knew how to build a 245.76 kS/s wideband CGAN burst.
Nothing connected them, so a claim that "Motorola is integrated with the SDR"
would have been false.

This backend closes that gap without inventing a second waveform. It takes the
**exact same** LPI audio burst the sound-card path transmits -- keyed spread
codebook, dither masking, keyed Zadoff-Chu pilot, AES-128-CTR + CRC-8 +
RS(42,34), all measured by the same eight-domain battery -- and carries it over
the USRP instead of over the radio's microphone input. One waveform, two
transports.

How the audio becomes RF
------------------------
The burst is real audio sampled at 48 kHz, occupying 300-3000 Hz. It is
converted to a complex baseband by taking its analytic signal (Hilbert), which
keeps a single sideband instead of mirroring the spectrum into a redundant
upper/lower pair. The analytic signal is then resampled to the radio's sample
rate and tuned so that the burst lands at ``f_lo + 300 .. f_lo + 3000`` Hz.

The resampling ratio is exact, not approximate: ``48000 * 512 / 100 = 245760``,
which is UHD's preferred master-clock-derived rate. So a 245.76 kS/s radio
carries the burst with no fractional resampler and no rate error.

Honesty contract
----------------
``probe()`` never claims a device it cannot see. ``send()`` returns
``success=False`` with ``error_code="SDR_NOT_AVAILABLE"`` when UHD or the device
is absent, rather than pretending to transmit. When the radio is present but
``MOTOROLA_RADIO_APPROVED`` is unset, the IQ is built and measured but not
radiated, and the result says so.
"""

from __future__ import annotations

import subprocess
from typing import Any, Dict, Optional

import numpy as np

from integration.motorola.hardware_bridge import BridgeResult

# 48000 * 512 / 100 == 245760 exactly, so the audio grid maps onto UHD's
# preferred rate with an integer polyphase ratio and zero rate error.
AUDIO_FS = 48000
DEFAULT_SDR_RATE = 245_760.0
DEFAULT_SDR_FREQ = 2.484e9          # 2.4 GHz ISM; change for a licensed band
RESAMPLE_UP = 512
RESAMPLE_DOWN = 100


def _uhd_available() -> bool:
    try:
        import uhd  # noqa: F401
    except Exception:
        return False
    return True


def find_devices(timeout: float = 2.5, use_cache: bool = True) -> str:
    """Return ``uhd_find_devices`` output, without ever blocking indefinitely.

    Two hazards, both observed on this host, and both handled here:

    1. **A wedged child.** ``subprocess.run(timeout=...)`` looks bounded, but on
       timeout it kills the child and then waits for it to exit. A process stuck
       in *uninterruptible* kernel sleep (state ``D``/``UE``, e.g. a half-enumerated
       USB device inside the UHD driver) cannot be killed, so that wait never
       returns and the "bounded" call hangs anyway. Here the child is abandoned
       instead: after the deadline we signal it, wait at most another second, and
       return a timeout string regardless of whether it actually died.

    2. **Repeated enumeration.** Each call can spawn a fresh stuck process. The
       result is cached for the lifetime of the process, so the cost is paid at
       most once; pass ``use_cache=False`` to force a fresh look.
    """
    global _DEVICE_CACHE
    if use_cache and _DEVICE_CACHE is not None:
        return _DEVICE_CACHE

    import time

    def _remember(value: str) -> str:
        global _DEVICE_CACHE
        _DEVICE_CACHE = value
        return value

    try:
        proc = subprocess.Popen(
            ["uhd_find_devices"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
        )
    except FileNotFoundError:
        return _remember("(uhd_find_devices not installed)")
    except Exception as e:  # noqa: BLE001
        return _remember(f"(uhd_find_devices unavailable: {e})")

    deadline = time.monotonic() + timeout
    while True:
        if proc.poll() is not None:
            out, err = proc.communicate()
            text = (out or "").strip() or (err or "").strip()
            return _remember(text)
        if time.monotonic() >= deadline:
            # Do not wait for this child: if it is unkillable, waiting is exactly
            # the hang we are trying to avoid.
            try:
                proc.kill()
            except Exception:  # noqa: BLE001
                pass
            try:
                proc.wait(timeout=1.0)
            except Exception:  # noqa: BLE001  (TimeoutExpired or anything else)
                pass
            return _remember(
                "(uhd_find_devices timed out; the driver may be wedged "
                "on a USB enumeration)")
        time.sleep(0.05)


_DEVICE_CACHE: Optional[str] = None


def _sdr_ratio(rate: float) -> tuple[int, int]:
    """Return the exact ``(up, down)`` polyphase ratio for 48 kHz -> ``rate``.

    At the default rate this is ``(512, 100)`` because ``48000 * 512/100 =
    245760`` exactly. Any other rate falls back to the nearest rational
    approximation with a bounded denominator, so the achieved rate is always
    reported rather than silently assumed.
    """
    if abs(rate - DEFAULT_SDR_RATE) < 1e-6:
        return RESAMPLE_UP, RESAMPLE_DOWN
    from fractions import Fraction

    frac = Fraction(rate / AUDIO_FS).limit_denominator(2000)
    return frac.numerator, frac.denominator


def audio_to_iq(audio: np.ndarray, rate: float = DEFAULT_SDR_RATE) -> np.ndarray:
    """Real 48 kHz LPI audio -> complex baseband at ``rate``.

    Uses the analytic signal so the RF spectrum is a single 2700 Hz-wide hump
    rather than a mirrored double sideband. Total power is normalised to unit
    peak magnitude so the caller can apply headroom exactly once.
    """
    from scipy.signal import resample_poly

    x = np.asarray(audio, dtype=np.float64).reshape(-1)
    if x.size == 0:
        return np.zeros(0, dtype=np.complex64)

    # Hilbert via FFT on a power-of-two padded copy would introduce edge
    # transients; scipy's own Hilbert is fine at these lengths and is what
    # lpi_v4 uses.
    from scipy.signal import hilbert

    z = hilbert(x)
    up, down = _sdr_ratio(rate)
    iq = resample_poly(z, up, down)
    peak = float(np.max(np.abs(iq))) + 1e-12
    return (iq / peak).astype(np.complex64)


def iq_to_audio(iq: np.ndarray, rate: float = DEFAULT_SDR_RATE,
                target_peak: float = 0.9) -> np.ndarray:
    """Complex baseband at ``rate`` -> real 48 kHz audio.

    The exact inverse of :func:`audio_to_iq`. The radiated signal is the
    analytic signal ``z = x + j*H{x}``, so ``Re{z}`` recovers ``x``; the polyphase
    ratio is then inverted to return to the 48 kHz grid. This is the function
    the hardware RX path uses, and it is also what makes the SDR transport
    testable with no radio attached.
    """
    from scipy.signal import resample_poly

    z = np.asarray(iq).reshape(-1)
    if z.size == 0:
        return np.zeros(0, dtype=np.float64)

    up, down = _sdr_ratio(rate)
    audio = resample_poly(np.real(z), down, up)
    peak = float(np.max(np.abs(audio))) + 1e-12
    return (audio / peak * target_peak).astype(np.float64)


class SdrBackend:
    """Carry the Motorola LPI burst over a USRP instead of a radio mic input."""

    name = "sdr_usrp"

    def __init__(self, addr: str = "", rate: float = DEFAULT_SDR_RATE,
                 freq: float = DEFAULT_SDR_FREQ, gain: float = 0.0,
                 ant: str = "", lpi=None, seed_fn=None):
        self.addr = addr
        self.rate = float(rate)
        self.freq = float(freq)
        self.gain = float(gain)
        self.ant = ant
        self._lpi = lpi
        self._seed_fn = seed_fn

    # -- diagnostics -----------------------------------------------------
    def probe(self, deep: bool = True) -> Dict[str, Any]:
        have_uhd = _uhd_available()
        if have_uhd and deep:
            devices = find_devices()
        elif have_uhd:
            devices = _DEVICE_CACHE or "(deep probe not requested)"
        else:
            devices = "(python uhd bindings not importable)"
        found = "Device:" in devices
        return {
            "backend": self.name,
            "uhd_python_bindings": have_uhd,
            "device_found": bool(found),
            "devices": devices,
            "rate_hz": self.rate,
            "freq_hz": self.freq,
            "carries": "motorola_lpi_audio_burst (analytic, single sideband)",
            "available": bool(have_uhd and found),
            "note": (
                "ready" if (have_uhd and found)
                else "no USRP enumerated; nothing can be radiated from this host"
            ),
        }

    # -- transmit --------------------------------------------------------
    def send(self, frame: bytes, dry_run: bool) -> BridgeResult:
        if self._lpi is None:
            return BridgeResult(
                False, self.name, dry_run, 0,
                "SDR backend has no LPI carrier configured; refusing to "
                "transmit an unmodulated frame",
                error_code="LPI_CARRIER_MISSING",
            )

        seed = self._seed_fn(frame) if self._seed_fn else 0
        try:
            audio = self._lpi.modulate(frame, seed=seed)
            iq = audio_to_iq(audio, self.rate)
        except Exception as e:  # noqa: BLE001
            return BridgeResult(False, self.name, dry_run, 0,
                                f"SDR modulation failed: {e}",
                                error_code="MODEM_ENCODE_ERROR")

        meta: Dict[str, Any] = {
            "transport": "sdr_usrp",
            "lpi": True,
            "audio_samples": int(audio.size),
            "iq_samples": int(iq.size),
            "rate_hz": self.rate,
            "freq_hz": self.freq,
            "occupied_hz": float(getattr(self._lpi.cfg, "occupied_hz", 2700.0)),
            "air_time_s": round(iq.size / self.rate, 4),
        }

        if dry_run:
            return BridgeResult(
                True, self.name, True, len(frame),
                f"LPI burst rendered for USRP ({iq.size} IQ samples, "
                f"{meta['air_time_s']:.3f}s at {self.rate:.0f} S/s) but NOT "
                f"radiated: MOTOROLA_RADIO_APPROVED is unset",
                meta=meta,
            )

        if not _uhd_available():
            return BridgeResult(False, self.name, False, 0,
                                "python UHD bindings are not importable; cannot transmit",
                                error_code="SDR_NOT_AVAILABLE", meta=meta)

        try:
            from lpi_v4.uhd_io import Radio
        except Exception as e:  # noqa: BLE001
            return BridgeResult(False, self.name, False, 0,
                                f"UHD transport unavailable: {e}",
                                error_code="SDR_NOT_AVAILABLE", meta=meta)

        import time

        t0 = time.time()
        try:
            with Radio(addr=self.addr, rate=self.rate, freq=self.freq,
                       gain=self.gain, ant=self.ant, direction="tx") as radio:
                # 10 % leading zeros give the PA and the far-end squelch time to
                # settle, mirroring the sound-card path's PTT lead.
                pad = np.zeros(int(0.1 * self.rate), dtype=np.complex64)
                sent = radio.send(np.concatenate([pad, iq]))
                meta["samples_sent"] = int(sent)
                meta["radio"] = radio.summary()
        except Exception as e:  # noqa: BLE001
            return BridgeResult(False, self.name, False, 0,
                                f"USRP transmit failed: {e}",
                                error_code="SDR_TX_ERROR", meta=meta)

        return BridgeResult(
            True, self.name, False, len(frame),
            f"Transmitted LPI burst over USRP at {self.freq/1e6:.4f} MHz, "
            f"{meta['air_time_s']:.3f}s",
            latency_ms=(time.time() - t0) * 1000.0, meta=meta,
        )

    def receive(self, duration_s: float = 3.0, save_wav: Optional[str] = None):
        """Capture from the USRP and demodulate the LPI burst."""
        if not _uhd_available():
            return None, {"ok": False, "source": "sdr_usrp",
                          "note": "python UHD bindings are not importable"}
        try:
            from lpi_v4.uhd_io import Radio
        except Exception as e:  # noqa: BLE001
            return None, {"ok": False, "source": "sdr_usrp", "note": str(e)}

        with Radio(addr=self.addr, rate=self.rate, freq=self.freq,
                   gain=self.gain, ant=self.ant, direction="rx") as radio:
            iq = radio.recv(int(duration_s * self.rate))

        return self.decode_capture(iq, save_wav=save_wav)

    def decode_capture(self, iq: np.ndarray,
                       save_wav: Optional[str] = None):
        """Complex USRP capture -> ``(payload, meta)``.

        Deliberately separate from :meth:`receive` so the entire RX chain can be
        exercised against a recorded or simulated capture with no radio attached.
        That is what turns "the SDR path exists" into "the SDR path is tested".

        The conversion inverts the transmit step: what was radiated is the
        analytic signal ``z = x + j*H{x}``, so ``Re{z}`` recovers the original
        real burst, and the polyphase ratio then returns it to 48 kHz.
        """
        audio = iq_to_audio(iq, self.rate)

        meta: Dict[str, Any] = {
            "source": "sdr_usrp",
            "rate_hz": self.rate,
            "freq_hz": self.freq,
            "audio_samples": int(audio.size),
            "iq_samples": int(np.asarray(iq).size),
        }

        if save_wav:
            try:
                from scipy.io import wavfile
                wavfile.write(save_wav, AUDIO_FS,
                              (audio * 32767).astype(np.int16))
                meta["wav"] = save_wav
            except Exception as e:  # noqa: BLE001
                meta["wav_error"] = str(e)

        if self._lpi is None:
            meta["ok"] = False
            meta["note"] = "no LPI carrier configured; captured audio not decoded"
            return None, meta

        # ``LpiCarrier`` exposes ``demodulate``; there is no ``receive`` method.
        # (The previous version probed for ``receive`` and therefore always fell
        # through to ``(None, {"ok": False})`` -- a dead RX path that looked
        # plausible in the probe output and never decoded anything.)
        rx = self._lpi.demodulate(audio)
        meta["ok"] = bool(rx.ok)
        meta["detail"] = rx.detail
        # Keep the receiver's own diagnostics (CFO estimate, pilot score,
        # per-frame CRC states) so a failed capture can be diagnosed rather
        # than guessed at.
        for k, v in (rx.meta or {}).items():
            if k != "_rank":
                meta[k] = v
        return (rx.payload if rx.ok else None), meta

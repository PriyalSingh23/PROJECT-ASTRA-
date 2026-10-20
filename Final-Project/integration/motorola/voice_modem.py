"""Audio-frequency data modem — carries bytes through a radio's voice channel.

Why this module exists
----------------------
There are two honest ways to move SHADOWCOMM traffic over a Motorola radio:

1. **Data path** — MOTOTRBO TMS PDUs over MNIS (``MnisUdpBackend``). Clean,
   vendor-supported, but it needs MOTOTRBO CPS / Radio Management and an IP
   peripheral service in the picture.

2. **Voice path** — this module. The radio is put in analogue (or DMR voice)
   mode and treated as a *transparent pipe*: the Raspberry Pi keys PTT, plays a
   modulated audio burst into the mic input, and the far-end radio's speaker
   output is recorded and demodulated. Any radio works, including ones you
   cannot program.

The voice path is what makes a *field pilot* possible with two off-the-shelf
radios and a Pi, so it is the path the field-test tool defaults to.

Design
------
Differential BPSK on an audio subcarrier, RRC-shaped at both ends:

    bits --[differential encode]--> symbols --[RRC]--> x cos(2*pi*fc*t) --> audio

    audio --[x exp(-j*2*pi*fc*t)]--> --[RRC matched]--> z[k] --[differential
    decode]--> bits

Two deliberate choices, both borrowed from the lessons already encoded in
``lpi_v4/lpi_core.py``:

* **Differential encoding.** The absolute RF phase of a burst through an
  analogue radio is unknowable (the radio's own PLL, the squelch, the audio
  AGC). Differencing adjacent symbols removes the phase ambiguity entirely
  instead of fighting it. The LPI v4 notes record exactly this failure mode:
  a payload with randomised absolute phase left the decoder stuck at 50 % BER.

* **A sync word, not a fixed timing.** The receiver brute-forces the
  sample-phase offset (``sps`` candidates) and scores each against the known
  Barker-13 sync. Timing recovery without a PLL, and it is verifiable: the
  winning score is reported, so a weak lock is visible rather than silent.

Everything here is pure DSP with no hardware imports, so the whole chain can be
self-tested in a loopback with a simulated channel (AWGN, carrier offset,
sample-clock error) before a single watt is radiated.
"""
from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Barker-13: the canonical low-autocorrelation sync word.
BARKER13 = np.array([1, 1, 1, 1, 1, -1, -1, 1, 1, -1, 1, -1, 1], dtype=np.float64)
PREAMBLE_SYMBOLS = 32
MAX_PAYLOAD_BYTES = 4096


@dataclass
class ModemConfig:
    """Audio modem parameters. Defaults fit a 300-3000 Hz voice channel."""

    audio_fs: int = 48000          # sound-card sample rate
    symbol_rate: float = 1200.0    # baud; 1200 with beta=0.5 -> ~1.8 kHz wide
    carrier_hz: float = 1700.0     # audio subcarrier, comfortably mid-band
    roll_off: float = 0.5          # RRC beta
    span_symbols: int = 6          # RRC span each side
    amplitude: float = 0.7         # peak level, avoids sound-card clipping

    @property
    def sps(self) -> int:
        return int(round(self.audio_fs / self.symbol_rate))


@dataclass
class DecodeResult:
    payload: Optional[bytes]
    ok: bool
    sync_score: float
    phase_offset: int
    bits_decoded: int
    detail: str
    meta: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Pulse shaping
# ---------------------------------------------------------------------------
def rrc_taps(sps: int, beta: float, span: int) -> np.ndarray:
    """Root-raised-cosine taps, unit energy. Mirrors the shape used elsewhere."""
    n = np.arange(-span * sps, span * sps + 1, dtype=np.float64)
    t = n / sps
    taps = np.zeros_like(t)
    for i, ti in enumerate(t):
        if abs(ti) < 1e-8:
            taps[i] = 1.0 - beta + 4.0 * beta / np.pi
        elif beta > 0 and abs(abs(ti) - 1.0 / (4.0 * beta)) < 1e-8:
            taps[i] = (beta / np.sqrt(2.0)) * (
                (1.0 + 2.0 / np.pi) * np.sin(np.pi / (4.0 * beta))
                - (1.0 - 2.0 / np.pi) * np.cos(np.pi / (4.0 * beta))
            )
        else:
            num = np.sin(np.pi * ti * (1.0 - beta)) + 4.0 * beta * ti * np.cos(np.pi * ti * (1.0 + beta))
            den = np.pi * ti * (1.0 - (4.0 * beta * ti) ** 2)
            taps[i] = num / den
    energy = np.sqrt(np.sum(taps ** 2))
    return taps / (energy if energy > 0 else 1.0)


# ---------------------------------------------------------------------------
# Bit packing and framing
# ---------------------------------------------------------------------------
def bytes_to_bits(data: bytes) -> np.ndarray:
    """MSB-first unpacking to a +/-1 array."""
    if not data:
        return np.zeros(0)
    arr = np.frombuffer(data, dtype=np.uint8)
    bits = np.unpackbits(arr)
    return (bits.astype(np.float64) * 2.0) - 1.0


def bits_to_bytes(bits: np.ndarray) -> bytes:
    if bits.size == 0:
        return b""
    return np.packbits((np.asarray(bits) > 0).astype(np.uint8)).tobytes()


def _sync_bits() -> np.ndarray:
    preamble = np.ones(PREAMBLE_SYMBOLS, dtype=np.float64)
    preamble[1::2] = -1.0                       # alternating for clock recovery
    return np.concatenate([preamble, BARKER13])


def _frame_bits(payload: bytes) -> np.ndarray:
    """preamble | sync | u16 length | payload | u32 CRC32 — all as +/-1 bits."""
    length_bits = np.unpackbits(np.frombuffer(struct.pack(">H", len(payload)), dtype=np.uint8))
    crc = zlib.crc32(payload) & 0xFFFFFFFF
    crc_bits = np.unpackbits(np.frombuffer(struct.pack(">I", crc), dtype=np.uint8))
    body = np.concatenate([
        (length_bits.astype(np.float64) * 2.0) - 1.0,
        bytes_to_bits(payload),
        (crc_bits.astype(np.float64) * 2.0) - 1.0,
    ])
    return np.concatenate([_sync_bits(), body])


def _differential_encode(bits: np.ndarray) -> np.ndarray:
    """tx[0] = 1; tx[n] = tx[n-1] * bits[n-1]. Length grows by one."""
    out = np.empty(bits.size + 1, dtype=np.float64)
    out[0] = 1.0
    if bits.size:
        out[1:] = np.cumprod(bits)
    return out


def _differential_decode(symbols: np.ndarray) -> np.ndarray:
    """Inverse of :func:`_differential_encode`; robust to any constant phase."""
    if symbols.size < 2:
        return np.zeros(0)
    return np.sign(np.real(symbols[1:] * np.conj(symbols[:-1])))


def audio_levels(audio: np.ndarray) -> Dict[str, Any]:
    """Level diagnostics for field wiring.

    When nothing decodes, the cause is almost always the audio path: the cable
    is in the headphone jack instead of the mic jack, the radio's AGC has
    squashed the burst, or the level is so hot the sound card clips. These
    numbers tell you which, which is far more useful than a generic failure.
    """
    x = np.asarray(audio, dtype=np.float64).ravel()
    if x.size == 0:
        return {"samples": 0, "rms": 0.0, "peak": 0.0, "dbfs": None,
                "clipped_fraction": 0.0, "verdict": "EMPTY"}
    peak = float(np.max(np.abs(x)))
    rms = float(np.sqrt(np.mean(x ** 2)))
    clipped = float(np.mean(np.abs(x) >= 0.999))
    dbfs = 20.0 * np.log10(rms) if rms > 0 else None
    if peak < 1e-4:
        verdict = "SILENT — no audio reached the capture device (check the cable and the radio volume)"
    elif clipped > 0.01:
        verdict = "CLIPPING — reduce the radio/sound-card level or the modem amplitude"
    elif rms < 1e-3:
        verdict = "VERY LOW — the burst is audible but far too quiet to demodulate reliably"
    else:
        verdict = "OK — audio level is in a usable range"
    return {
        "samples": int(x.size),
        "rms": round(rms, 6),
        "peak": round(peak, 6),
        "dbfs": round(float(dbfs), 2) if dbfs is not None else None,
        "clipped_fraction": round(clipped, 5),
        "verdict": verdict,
    }


def write_wav(path: str, audio: np.ndarray, sample_rate: int = 48000) -> str:
    """Save a capture as 16-bit mono WAV (stdlib only) for post-mortem analysis."""
    import wave

    x = np.clip(np.asarray(audio, dtype=np.float64).ravel(), -1.0, 1.0)
    pcm = (x * 32767.0).astype("<i2").tobytes()
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(int(sample_rate))
        wf.writeframes(pcm)
    return path


class VoiceModem:
    """Differential BPSK audio modem. Pure DSP — no device access."""

    def __init__(self, config: Optional[ModemConfig] = None):
        self.cfg = config or ModemConfig()
        self._taps = rrc_taps(self.cfg.sps, self.cfg.roll_off, self.cfg.span_symbols)

    # -- convenience -----------------------------------------------------
    def samples_for_bits(self, n_bits: int) -> int:
        return n_bits * self.cfg.sps

    def burst_seconds(self, payload_bytes: int) -> float:
        """Air time for a payload, including preamble/sync/CRC overhead."""
        n_bits = _frame_bits(b"\x00" * payload_bytes).size
        return n_bits / self.cfg.symbol_rate

    # -- transmit --------------------------------------------------------
    def modulate(self, payload: bytes, key_up: bool = True, key_down: bool = True) -> np.ndarray:
        """bytes -> real baseband audio (float32 in [-1, 1])."""
        if len(payload) > MAX_PAYLOAD_BYTES:
            raise ValueError(f"payload {len(payload)}B exceeds modem limit {MAX_PAYLOAD_BYTES}B")
        symbols = _differential_encode(_frame_bits(payload))

        # Upsample with zeros, then shape: the text-book pulse train.
        pulse = np.zeros(symbols.size * self.cfg.sps, dtype=np.float64)
        pulse[:: self.cfg.sps] = symbols
        shaped = np.convolve(pulse, self._taps, mode="same")

        idx = np.arange(shaped.size, dtype=np.float64)
        carrier = np.cos(2.0 * np.pi * self.cfg.carrier_hz * idx / self.cfg.audio_fs)
        audio = shaped * carrier * self.cfg.amplitude

        # A short key-up ramp avoids the click that a hard start puts into a
        # radio's audio AGC — the click is a real detector artefact.
        if key_up:
            audio = np.concatenate([np.zeros(int(0.02 * self.cfg.audio_fs)), audio])
        if key_down:
            audio = np.concatenate([audio, np.zeros(int(0.02 * self.cfg.audio_fs))])
        return audio.astype(np.float32)

    # -- receive ---------------------------------------------------------
    def _parse_frame(self, decoded: np.ndarray, start: int, score: float, phase: int) -> DecodeResult:
        """Try to read a frame out of `decoded` beginning at `start`."""
        body = decoded[start:]
        if body.size < 48:
            return DecodeResult(None, False, score, phase, int(decoded.size),
                               "frame survived sync but the header is truncated",
                               meta={"_rank": 1})

        length_bytes = np.packbits((body[:16] > 0).astype(np.uint8)).tobytes()
        length = int(np.frombuffer(length_bytes, dtype=">u2")[0])
        if length > MAX_PAYLOAD_BYTES:
            return DecodeResult(None, False, score, phase, int(decoded.size),
                               f"declared length {length}B exceeds limit",
                               meta={"declared_length": length, "_rank": 0})

        payload_bits = length * 8
        if body.size < 16 + payload_bits + 32:
            return DecodeResult(None, False, score, phase, int(decoded.size),
                               "payload truncated in flight",
                               meta={"declared_length": length, "_rank": 2})

        payload = bits_to_bytes(body[16 : 16 + payload_bits])
        crc_bits = body[16 + payload_bits : 16 + payload_bits + 32]
        crc_rx = int(np.frombuffer(np.packbits((crc_bits > 0).astype(np.uint8)).tobytes(), dtype=">u4")[0])
        crc_calc = zlib.crc32(payload) & 0xFFFFFFFF
        if crc_rx != crc_calc:
            # Rank partial attempts by how plausible the frame was.
            rank = 3 + (1 if crc_rx == 0 or crc_calc == 0 else 0)
            return DecodeResult(None, False, score, phase, int(decoded.size),
                               "CRC mismatch — frame corrupted",
                               meta={"declared_length": length, "crc_rx": crc_rx,
                                     "crc_calc": crc_calc, "_rank": rank})

        return DecodeResult(
            payload, True, score, phase, int(decoded.size),
            f"decoded {length}B, CRC ok",
            meta={"declared_length": length, "crc": crc_rx, "confidence": round(score, 3), "_rank": 9},
        )

    def demodulate(self, audio: np.ndarray) -> DecodeResult:
        audio = np.asarray(audio, dtype=np.float64).ravel()
        if audio.size < self.cfg.sps * 64:
            return DecodeResult(None, False, 0.0, 0, 0, "capture too short to contain a frame")

        idx = np.arange(audio.size, dtype=np.float64)
        baseband = audio * np.exp(-2j * np.pi * self.cfg.carrier_hz * idx / self.cfg.audio_fs)
        matched = np.convolve(baseband, self._taps, mode="same")

        sync = _sync_bits()
        # Differential *decode* already undoes the encoding, so the decoder sees
        # the original frame bits and we correlate against the raw sync word.
        best_score = -1.0
        best_phase = 0
        best_decoded_size = 0
        best_failure: Optional[DecodeResult] = None

        # The symbol phase is unknown (no PLL). Try every candidate and let the
        # CRC arbitrate: a marginal phase can still lock the sync word by luck,
        # so "best correlation" alone will occasionally pick a phase that then
        # mangles the payload. The CRC is ground truth; trust it, not the score.
        for phase in range(self.cfg.sps):
            symbols = matched[phase :: self.cfg.sps]
            if symbols.size < sync.size + 8:
                continue
            decoded = _differential_decode(symbols)
            if decoded.size < sync.size:
                continue
            corr = np.correlate(decoded, sync, mode="valid")
            pos = int(np.argmax(np.abs(corr)))
            score = float(np.abs(corr[pos]) / sync.size)

            if score > best_score:
                best_score = score
                best_phase = phase
                best_decoded_size = int(decoded.size)

            if score < 0.75:
                continue

            attempt = self._parse_frame(decoded, pos + sync.size, score, phase)
            if attempt.ok:
                return attempt
            if best_failure is None or \
                    int(attempt.meta.get("_rank", 0)) > int(best_failure.meta.get("_rank", 0)) or (
                        attempt.meta.get("_rank") == best_failure.meta.get("_rank")
                        and attempt.sync_score > best_failure.sync_score):
                best_failure = attempt

        if best_failure is not None:
            best_failure.meta.pop("_rank", None)
            return best_failure

        return DecodeResult(
            None, False, best_score, best_phase, best_decoded_size,
            f"sync not locked (best score {best_score:.2f} < 0.75 across {self.cfg.sps} phases)",
            meta={"required_score": 0.75, "phases_tried": self.cfg.sps},
        )


# ---------------------------------------------------------------------------
# Channel simulation — for verifying the chain without a radio
# ---------------------------------------------------------------------------
def _analytic(x: np.ndarray) -> np.ndarray:
    """FFT-based analytic signal (avoids a scipy dependency for one Hilbert)."""
    n = x.size
    spec = np.fft.fft(x)
    h = np.zeros(n)
    h[0] = 1.0
    if n % 2 == 0:
        h[n // 2] = 1.0
        h[1 : n // 2] = 2.0
    else:
        h[1 : (n + 1) // 2] = 2.0
    return np.fft.ifft(spec * h)


def simulate_voice_channel(
    audio: np.ndarray,
    snr_db: float = 20.0,
    cfo_hz: float = 0.0,
    clock_error_ppm: float = 0.0,
    audio_fs: float = 48000.0,
    seed: Optional[int] = None,
) -> np.ndarray:
    """AWGN + carrier offset + sample-clock error, i.e. the cheap radio effects.

    Deliberately does *not* model FM capture, multipath or mechanical PTT
    transients — those need the real radio. This is the floor, not the ceiling.

    The carrier offset is applied as a rotation of the *analytic* signal. Two
    real radios differ by a few Hz of oscillator offset; modelling that as
    ``x * cos(...)`` would produce amplitude modulation instead (a double
    sideband multiplied by a real cosine is AM, not a frequency shift), and a
    5 Hz AM envelope crosses zero twice a frame and quietly corrupts the burst.
    """
    rng = np.random.default_rng(seed)
    x = np.asarray(audio, dtype=np.float64).ravel()

    if clock_error_ppm:
        scale = 1.0 + clock_error_ppm * 1e-6
        n_out = int(x.size / scale)
        t_out = np.arange(n_out, dtype=np.float64) * scale
        i0 = np.clip(np.floor(t_out).astype(int), 0, x.size - 1)
        i1 = np.clip(i0 + 1, 0, x.size - 1)
        frac = t_out - i0
        x = x[i0] * (1.0 - frac) + x[i1] * frac

    if cfo_hz:
        n = np.arange(x.size, dtype=np.float64)
        x = np.real(_analytic(x) * np.exp(2j * np.pi * cfo_hz * n / audio_fs))

    signal_power = float(np.mean(x ** 2)) or 1.0
    noise_power = signal_power / (10.0 ** (snr_db / 10.0))
    x = x + rng.normal(0.0, np.sqrt(noise_power), x.size)
    return x.astype(np.float32)


def loopback_selftest(
    n_frames: int = 12,
    snr_db: float = 18.0,
    cfo_hz: float = 5.0,
    clock_error_ppm: float = 20.0,
    payload_bytes: int = 64,
    seed: int = 1234,
) -> Dict[str, Any]:
    """End-to-end proof that modulate -> channel -> demodulate is correct.

    Returns per-frame results plus aggregate BER/PER. A correct modem must
    report 0 % BER at a realistic SNR; anything else is a bug in this file, not
    a property of radios, so the field tool treats a non-zero BER here as a
    hard failure before it will key a transmitter.
    """
    modem = VoiceModem()
    rng = np.random.default_rng(seed)
    results: List[Dict[str, Any]] = []
    bit_errors = 0
    bit_total = 0
    ok_count = 0

    for i in range(n_frames):
        payload = bytes(rng.integers(0, 256, payload_bytes, dtype=np.uint8))
        audio = modem.modulate(payload)
        rx = simulate_voice_channel(audio, snr_db=snr_db, cfo_hz=cfo_hz,
                                    clock_error_ppm=clock_error_ppm, seed=seed + i)
        res = modem.demodulate(rx)
        ok = bool(res.ok and res.payload == payload)
        ok_count += 1 if ok else 0
        if res.payload is not None:
            n = min(len(res.payload), len(payload))
            diff = np.unpackbits(np.frombuffer(res.payload[:n], dtype=np.uint8)) ^ \
                   np.unpackbits(np.frombuffer(payload[:n], dtype=np.uint8))
            bit_errors += int(diff.sum())
            bit_total += n * 8
        results.append({
            "frame": i,
            "ok": ok,
            "sync_score": round(res.sync_score, 3),
            "phase_offset": res.phase_offset,
            "detail": res.detail,
            "bytes": len(payload),
        })

    total_bits = max(1, bit_total)
    occupied_hz = modem.cfg.symbol_rate * (1.0 + modem.cfg.roll_off)
    # `snr_db` is the *wideband* SNR: noise is spread over the full sound-card
    # band, but the matched filter only admits the occupied bandwidth. The
    # in-band figure is what the receiver actually sees, and it is the honest
    # one to compare against a radio's specified sensitivity.
    inband_gain_db = 10.0 * np.log10(modem.cfg.audio_fs / occupied_hz)
    return {
        "frames": n_frames,
        "frames_ok": ok_count,
        "per": round(1.0 - ok_count / float(max(1, n_frames)), 4),
        "ber": round(bit_errors / total_bits, 6),
        "snr_db": snr_db,
        "snr_inband_db": round(snr_db + float(inband_gain_db), 2),
        "occupied_bandwidth_hz": round(occupied_hz, 1),
        "cfo_hz": cfo_hz,
        "clock_error_ppm": clock_error_ppm,
        "payload_bytes": payload_bytes,
        "air_time_s": round(modem.burst_seconds(payload_bytes), 3),
        "symbol_rate": modem.cfg.symbol_rate,
        "carrier_hz": modem.cfg.carrier_hz,
        "sps": modem.cfg.sps,
        "results": results,
        "pass": ok_count == n_frames,
    }

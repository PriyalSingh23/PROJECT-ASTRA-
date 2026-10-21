"""Thread-safe ring buffer for live Motorola LPI waveform capture.

Every message dispatched through the Motorola LPI carrier writes its
modulated audio samples here. The spectrum and waveform API endpoints
read from this buffer so the Web Console displays *actual* LPI burst
data — not synthetic noise.

Design:
  * Fixed-depth ring (default 8 bursts) — old bursts are evicted silently.
  * Thread-safe via a ``threading.Lock`` so the worker thread can write
    while the API reads.
  * The ``latest()`` method returns the most recent burst with its EW
    battery summary, or ``None`` if no burst has been captured yet.
  * The ``spectrum_snapshot()`` method returns a ready-to-JSON PSD of
    the latest burst, matching the format ``/api/v1/stream/spectrum``
    expects.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional

import numpy as np


@dataclass
class LpiBurst:
    """One captured LPI audio burst."""
    audio: np.ndarray                 # float64/float32, mono, sample_rate Hz
    sample_rate: int
    timestamp: float                  # time.time()
    message_id: Optional[str] = None
    sender: Optional[str] = None
    recipient: Optional[str] = None
    lpi_meta: Dict[str, Any] = field(default_factory=dict)
    ew_summary: Optional[Dict[str, Any]] = None


class LpiWaveformBuffer:
    """Process-wide ring buffer of recent Motorola LPI bursts."""

    def __init__(self, maxlen: int = 8):
        self._ring: Deque[LpiBurst] = deque(maxlen=maxlen)
        self._lock = threading.Lock()
        self._total_captured: int = 0

    # -- write (worker thread) -------------------------------------------
    def push(self, burst: LpiBurst) -> None:
        """Append a burst. Oldest is evicted when the ring is full."""
        with self._lock:
            self._ring.append(burst)
            self._total_captured += 1

    def push_audio(
        self,
        audio: np.ndarray,
        sample_rate: int = 48000,
        message_id: Optional[str] = None,
        sender: Optional[str] = None,
        recipient: Optional[str] = None,
        lpi_meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Convenience: push raw audio samples with metadata."""
        self.push(LpiBurst(
            audio=np.asarray(audio, dtype=np.float64),
            sample_rate=sample_rate,
            timestamp=time.time(),
            message_id=message_id,
            sender=sender,
            recipient=recipient,
            lpi_meta=lpi_meta or {},
        ))

    # -- read (API thread) -----------------------------------------------
    def latest(self) -> Optional[LpiBurst]:
        """The most recent burst, or None."""
        with self._lock:
            return self._ring[-1] if self._ring else None

    def all_bursts(self) -> List[LpiBurst]:
        """Shallow copy of the ring contents (newest last)."""
        with self._lock:
            return list(self._ring)

    @property
    def total_captured(self) -> int:
        with self._lock:
            return self._total_captured

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._ring)

    # -- derived views for the API ----------------------------------------
    def spectrum_snapshot(self, fft_size: int = 512) -> Optional[Dict[str, Any]]:
        """PSD of the latest burst, ready for JSON serialisation.

        Returns the same shape as ``/api/v1/stream/spectrum`` so the
        frontend's Spectrum & Waterfall panel can display it unchanged.
        """
        burst = self.latest()
        if burst is None:
            return None

        audio = burst.audio
        # Take a centre window of fft_size samples for the FFT
        if audio.size < fft_size:
            pad = np.zeros(fft_size - audio.size)
            window = np.concatenate([audio, pad])
        else:
            start = (audio.size - fft_size) // 2
            window = audio[start:start + fft_size]

        # Windowed FFT → PSD in dB
        win = np.hanning(fft_size)
        fft = np.fft.fftshift(np.fft.fft(window * win))
        psd = 20.0 * np.log10(np.abs(fft) + 1e-12)
        psd = psd - float(np.max(psd))  # normalise to 0 dB peak

        # Frequency axis centred on the Motorola voice channel (~1650 Hz carrier)
        fs = burst.sample_rate
        freqs_khz = np.linspace(-fs / 2000.0, fs / 2000.0, fft_size)

        # UHF centre for the radio display (typical Motorola UHF)
        center_freq_mhz = float(burst.lpi_meta.get("center_freq_mhz", 433.0))

        return {
            "fft_size": fft_size,
            "center_freq_mhz": center_freq_mhz,
            "spectrum_db": [round(float(v), 2) for v in psd],
            "timestamp": burst.timestamp,
            "source": "motorola_lpi_burst",
            "message_id": burst.message_id,
            "burst_duration_s": round(audio.size / float(fs), 4),
            "sample_rate_hz": fs,
            "total_bursts_captured": self.total_captured,
        }

    def waveform_view(self, n_samples: int = 256) -> Optional[Dict[str, Any]]:
        """Time-domain I/Q view of the latest burst for the waveform panel."""
        burst = self.latest()
        if burst is None:
            return None

        audio = burst.audio
        # Take the first n_samples
        seg = audio[:min(n_samples, audio.size)]

        # Hilbert transform to get Q (analytic signal)
        from scipy.signal import hilbert
        analytic = hilbert(seg)
        i_vals = np.real(analytic).astype(np.float64)
        q_vals = np.imag(analytic).astype(np.float64)

        return {
            "waveform": [
                {"sample": idx, "i": round(float(i_vals[idx]), 4), "q": round(float(q_vals[idx]), 4)}
                for idx in range(len(seg))
            ],
            "constellation": [
                {"i": round(float(i_vals[idx]), 4), "q": round(float(q_vals[idx]), 4)}
                for idx in range(0, len(seg), max(1, len(seg) // 128))
            ],
            "source": "motorola_lpi_burst",
            "timestamp": burst.timestamp,
            "message_id": burst.message_id,
            "total_bursts_captured": self.total_captured,
        }

    def ew_battery(self) -> Optional[Dict[str, Any]]:
        """Run the 8-domain EW battery on the latest burst and cache the result."""
        burst = self.latest()
        if burst is None:
            return None
        if burst.ew_summary is not None:
            return burst.ew_summary

        try:
            from integration.motorola.lpi_carrier import LpiCarrierConfig, audio_ew_report
            # ``audio_ew_report`` takes a CONFIG, not a bare sample rate. It was
            # being passed ``burst.sample_rate`` (48000), which is not an
            # ``LpiCarrierConfig`` -- the report then ran on defaults instead of
            # the burst's geometry and the battery scored an unrelated 5/8.
            cfg = LpiCarrierConfig(audio_fs=int(burst.sample_rate))
            report = audio_ew_report(burst.audio, cfg)
            burst.ew_summary = report
            return report
        except Exception as e:
            return {"error": str(e), "available": False}

    def status(self) -> Dict[str, Any]:
        """Status summary for health/dashboard endpoints."""
        burst = self.latest()
        return {
            "active": burst is not None,
            "total_captured": self.total_captured,
            "ring_depth": self.count,
            "latest_timestamp": burst.timestamp if burst else None,
            "latest_message_id": burst.message_id if burst else None,
            "latest_duration_s": round(
                burst.audio.size / float(burst.sample_rate), 4
            ) if burst else None,
        }


# Process-wide singleton
lpi_waveform_buffer = LpiWaveformBuffer()

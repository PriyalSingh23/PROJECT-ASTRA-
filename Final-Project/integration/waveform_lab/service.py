"""Waveform Lab — the covert waveform next to a conventional one.

Why this exists
---------------
A single waveform's KS p-value of 0.96 proves nothing on its own. The claim
"this looks like noise" is only meaningful *as a comparison*: the same
statistics, computed on a conventional burst that carries the same payload in
the same number of samples, say everything.

So this service measures two waveforms through the **identical** eight-domain
electronic-warfare battery (``lpi_v4/lpi_stats.py`` — KS, kurtosis, spectral
entropy, IQ circularity, PAPR, SCF, HOS-C42, WVD) and returns them side by side.

  Track A — **LPI-CGAN** : the real trained generator, forward pass, live.
  Track B — **Conventional QPSK** : RRC-shaped QPSK from
      ``lpi_research/waveform/baseline.py``, matched to Track A on both
      **payload** (128 bits/frame) and **real-sample budget** (1024 samples/
      frame), so neither column gets an unfair bandwidth advantage.

Fairness of the comparison
--------------------------
Track A spends 2 x 512 = 1024 real samples to carry 128 information bits.
Track B carries 2 bits per complex symbol, so 128 bits need 64 symbols; spread
over 512 complex samples that is ``sps = 8``. Both therefore occupy the same
time-bandwidth product and the same payload. Any difference in the battery is a
difference in *how the waveform is shaped*, not in how much it carries.

Everything is a measurement. When the checkpoint cannot be loaded the LPI track
is reported as ``UNAVAILABLE`` with the reason attached, and the conventional
track is still returned — we never invent numbers to fill a panel.
"""
from __future__ import annotations

import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

# Torch must be imported before numpy/scipy on Apple Silicon (OpenBLAS linker).
try:
    import torch
except ImportError:  # pragma: no cover - torch is a hard dep in this project
    torch = None

import numpy as np

# Human labels + the gate criterion each domain is judged against. The
# predicates mirror lpi_v4/lpi_stats.py CRITERIA exactly; they are duplicated
# here only so the UI can print the rule next to the number.
DOMAIN_META: Tuple[Tuple[str, str, str, str, str], ...] = (
    # (key, value key, label, unit, criterion text)
    ("ks", "ks_p", "KS p-value vs. Gaussian", "p", "p > 0.05"),
    ("kurt", "kurt", "Kurtosis", "\u2014", "|v \u2212 3| < 0.15"),
    ("entropy", "entropy", "Spectral entropy", "bits", "> 0.95"),
    ("circ", "circ", "IQ circularity", "ratio", "< 0.15"),
    ("papr", "papr", "PAPR deviation", "dB", "|v| < 3.0"),
    ("scf", "scf", "SCF ratio", "ratio", "< 3.0"),
    ("c42", "c42", "HOS C42", "\u2014", "|v| < 0.3"),
    ("wvd", "wvd", "WVD ratio", "ratio", "< 3.7"),
)


class WaveformLabService:
    """Produces the LPI-vs-conventional comparison payload."""

    def __init__(self, root_dir: Optional[str] = None):
        if root_dir is None:
            self.root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        else:
            self.root_dir = root_dir
        self.v4_dir = os.path.join(self.root_dir, "lpi_v4")
        self.best_model_path = os.path.join(self.v4_dir, "run", "lpi_v4.best.pt")
        self.eval_json_path = os.path.join(self.v4_dir, "run", "eval.json")
        self._generator: Optional[Tuple[Any, Any]] = None
        self._generator_error: Optional[str] = None
        self._cache: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Generator (Track A)
    # ------------------------------------------------------------------
    def _load_generator(self) -> Tuple[Optional[Any], Optional[Any]]:
        """Returns (cfg, generator) or (None, None). Cached after first try."""
        if self._generator is not None:
            return self._generator
        if self._generator_error is not None:
            return None, None
        if torch is None:
            self._generator_error = "PyTorch is not installed in this interpreter"
            return None, None
        if not os.path.exists(self.best_model_path):
            self._generator_error = f"Checkpoint not found: {self.best_model_path}"
            return None, None
        try:
            if self.v4_dir not in sys.path:
                sys.path.insert(0, self.v4_dir)
            from lpi_core import LPIConfig, LPIGenerator

            cfg = LPIConfig()
            # CPU is deterministic and sidesteps the missing MPS group_norm kernel.
            gen = LPIGenerator(cfg).to("cpu")
            gen.eval()
            blob = torch.load(self.best_model_path, map_location="cpu", weights_only=False)
            if not isinstance(blob, dict):
                blob = {"generator": blob}
            state = blob.get("generator") or blob.get("gen") or blob.get("g_state") or blob
            if isinstance(state, dict):
                gen.load_state_dict(state, strict=False)
            self._generator = (cfg, gen)
            return self._generator
        except Exception as exc:  # noqa: BLE001
            self._generator_error = str(exc)
            return None, None

    def generator_status(self) -> Dict[str, Any]:
        cfg, gen = self._load_generator()
        return {
            "available": gen is not None,
            "error": self._generator_error,
            "checkpoint": os.path.relpath(self.best_model_path, self.root_dir),
        }

    @staticmethod
    def _frame_geometry(cfg: Any) -> Dict[str, Any]:
        return {
            "n_bits": int(cfg.n_bits),
            "frame_len": int(cfg.frame_len),
            "out_len": int(cfg.out_len),
            "pilot_len": int(cfg.pilot_len),
            "total_len": int(cfg.total_len),
            "z_dim": int(cfg.z_dim),
            "fs_hz": float(cfg.fs),
            "dither_eps": float(cfg.dither_eps),
            "processing_gain_db": round(float(cfg.gain_db), 3),
        }

    def _lpi_frames(self, n_frames: int) -> Tuple[Optional[np.ndarray], Optional[Any], Optional[str]]:
        """Returns (frames, cfg, error) where ``cfg`` is the LPIConfig object."""
        cfg, gen = self._load_generator()
        if gen is None:
            return None, None, self._generator_error
        try:
            bits = np.random.randint(0, 2, (n_frames, cfg.n_bits)).astype(np.float32) * 2 - 1
            z = torch.randn(n_frames, cfg.z_dim)
            b = torch.tensor(bits, dtype=torch.float32)
            with torch.no_grad():
                frames = gen(z, b).cpu().numpy()
            return frames.astype(np.float32), cfg, None
        except Exception as exc:  # noqa: BLE001
            return None, None, str(exc)

    # ------------------------------------------------------------------
    # Conventional reference (Track B)
    # ------------------------------------------------------------------
    def _conventional_frames(self, n_frames: int, cfg: Any) -> np.ndarray:
        """Equal-payload, equal-sample-budget RRC-QPSK reference.

        LPI carries ``n_bits`` info bits in ``out_len`` real samples. A
        conventional QPSK symbol carries 2 bits, so ``n_bits`` bits need
        ``n_bits / 2`` symbols. To occupy the same ``out_len`` real samples the
        oversampling factor must be ``out_len / (2 * (n_bits / 2)) = out_len / n_bits``.
        """
        if self.root_dir not in sys.path:
            sys.path.insert(0, self.root_dir)
        from lpi_research.waveform.baseline import generate_qpsk

        n_symbols = max(1, cfg.n_bits // 2)
        sps = max(1, cfg.out_len // (2 * n_symbols))  # 1024 / 128 = 8
        out = []
        for _ in range(n_frames):
            x = generate_qpsk(cfg.frame_len, sps=sps, roll_off=0.35)  # (frame_len,) complex
            out.append(np.stack([x.real, x.imag], axis=0))            # (2, frame_len)
        return np.asarray(out, dtype=np.float32)

    # ------------------------------------------------------------------
    # Measurement
    # ------------------------------------------------------------------
    def _measure(self, frames: np.ndarray) -> Dict[str, Any]:
        """Run the shared eight-domain EW battery over (N,2,T) frames."""
        if self.v4_dir not in sys.path:
            sys.path.insert(0, self.v4_dir)
        from lpi_stats import ew_report

        ref = np.random.randn(*frames.shape).astype(np.float32)
        report = ew_report(frames, ref)
        domains: List[Dict[str, Any]] = []
        for key, value_key, label, unit, criterion in DOMAIN_META:
            value = report.get(value_key)
            passed = bool(report.get("pass", {}).get(key, False))
            domains.append({
                "key": key,
                "label": label,
                "unit": unit,
                "criterion": criterion,
                "value": None if value is None else float(value),
                "passed": passed,
            })
        n_pass = int(report.get("n_pass", 0))
        score = n_pass / float(len(DOMAIN_META))
        if n_pass >= 7:
            klass = "INDISTINGUISHABLE_FROM_NOISE"
        elif n_pass >= 4:
            klass = "PARTIALLY_MASKED"
        else:
            klass = "DETECTABLE"
        return {
            "domains": domains,
            "n_pass": n_pass,
            "n_domains": len(DOMAIN_META),
            "stealth_score": round(score, 4),
            "Sc": float(report.get("Sc", 0.0)),
            "grade": report.get("grade"),
            "classification": klass,
        }

    @staticmethod
    def _views(frames: np.ndarray, cfg: Any, n_wave: int = 128, n_scatter: int = 512) -> Dict[str, Any]:
        """Time-domain, constellation and PSD views for one track."""
        frame0 = frames[0]                      # (2, T)
        i_vals, q_vals = frame0[0], frame0[1]
        complex_iq = (i_vals + 1j * q_vals).astype(np.complex64)

        fft = np.fft.fftshift(np.fft.fft(complex_iq))
        psd = 20.0 * np.log10(np.abs(fft) + 1e-12)
        psd = psd - float(np.max(psd))
        freqs_khz = np.linspace(-cfg.fs / 2000.0, cfg.fs / 2000.0, len(psd))

        # Dense sample cloud — equal point count for both tracks.
        flat_i = frames[:, 0, :].reshape(-1)
        flat_q = frames[:, 1, :].reshape(-1)
        step = max(1, flat_i.size // n_scatter)
        cloud_i = flat_i[::step][:n_scatter]
        cloud_q = flat_q[::step][:n_scatter]

        return {
            "waveform": [
                {"sample": idx, "i": round(float(i_vals[idx]), 4), "q": round(float(q_vals[idx]), 4)}
                for idx in range(min(n_wave, len(i_vals)))
            ],
            "constellation": [
                {"i": round(float(a), 4), "q": round(float(b), 4)}
                for a, b in zip(cloud_i, cloud_q)
            ],
            "spectrum": [
                {"freq_khz": round(float(f), 3), "power_db": round(float(p), 2)}
                for f, p in zip(freqs_khz, psd)
            ],
            "sample_count": int(frames.size),
            "frame_shape": [int(frames.shape[0]), int(frames.shape[1]), int(frames.shape[2])],
        }

    @staticmethod
    def _symbol_centers(frames: np.ndarray, sps: int) -> List[Dict[str, float]]:
        """Symbol-rate points for the conventional track (shows the 4 clusters)."""
        pts: List[Dict[str, float]] = []
        for f in frames:
            pts.extend({"i": round(float(f[0, k]), 4), "q": round(float(f[1, k]), 4)}
                       for k in range(0, f.shape[1], sps))
        return pts

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def compare(self, n_frames: int = 4, max_age_s: float = 60.0) -> Dict[str, Any]:
        n_frames = max(1, min(int(n_frames), 16))
        now = time.time()
        cached = self._cache.get("comparison")
        if cached and cached["n_frames"] == n_frames and (now - cached["at"]) < max_age_s:
            return cached["data"]

        lpi_frames, lpi_cfg, lpi_error = self._lpi_frames(n_frames)

        # The conventional track needs solely numpy — it is produced even when
        # the checkpoint is unavailable, so the page always has a comparison.
        if lpi_cfg is not None:
            cfg = lpi_cfg
        else:
            if self.v4_dir not in sys.path:
                sys.path.insert(0, self.v4_dir)
            from lpi_core import LPIConfig
            cfg = LPIConfig()

        conventional_frames = self._conventional_frames(n_frames, cfg)

        tracks: Dict[str, Any] = {}

        # Track A — LPI-CGAN
        if lpi_frames is not None:
            lpi_track = {
                "id": "lpi",
                "label": "LPI-CGAN (covert)",
                "source": "lpi_v4/run/lpi_v4.best.pt — live generator forward pass",
                "available": True,
                **self._views(lpi_frames, cfg),
                **self._measure(lpi_frames),
            }
            lpi_track["symbol_centers"] = []
        else:
            lpi_track = {
                "id": "lpi",
                "label": "LPI-CGAN (covert)",
                "source": "lpi_v4/run/lpi_v4.best.pt",
                "available": False,
                "unavailable_reason": lpi_error,
                "domains": [],
                "n_pass": 0,
                "n_domains": len(DOMAIN_META),
                "stealth_score": None,
                "classification": "UNAVAILABLE",
                "waveform": [],
                "constellation": [],
                "spectrum": [],
                "symbol_centers": [],
            }
        tracks["lpi"] = lpi_track

        # Track B — conventional QPSK
        n_symbols = max(1, cfg.n_bits // 2)
        sps = max(1, cfg.out_len // (2 * n_symbols))
        conv_track = {
            "id": "conventional",
            "label": "Conventional QPSK (no LPI)",
            "source": "lpi_research/waveform/baseline.py — RRC-shaped QPSK",
            "available": True,
            "spec": (
                f"{n_symbols} QPSK symbols at sps={sps}, RRC roll-off 0.35 — "
                f"{cfg.n_bits} bits in {cfg.out_len} real samples (matched to LPI)"
            ),
            **self._views(conventional_frames, cfg),
            **self._measure(conventional_frames),
        }
        conv_track["symbol_centers"] = self._symbol_centers(conventional_frames, sps)
        tracks["conventional"] = conv_track

        # Contrast — which domains flip.
        contrast: List[Dict[str, Any]] = []
        if lpi_track["available"]:
            lpi_by_key = {d["key"]: d for d in lpi_track["domains"]}
            for dom in conv_track["domains"]:
                other = lpi_by_key.get(dom["key"])
                if not other:
                    continue
                contrast.append({
                    "key": dom["key"],
                    "label": dom["label"],
                    "criterion": dom["criterion"],
                    "unit": dom["unit"],
                    "lpi": other["value"],
                    "conventional": dom["value"],
                    "lpi_pass": other["passed"],
                    "conventional_pass": dom["passed"],
                    "flips": other["passed"] != dom["passed"],
                })

        if lpi_track["available"]:
            verdict = {
                "lpi_pass": lpi_track["n_pass"],
                "conventional_pass": conv_track["n_pass"],
                "domains_flipped": sum(1 for c in contrast if c["flips"]),
                "headline": (
                    f"LPI-CGAN passes {lpi_track['n_pass']}/{len(DOMAIN_META)} EW domains; "
                    f"conventional QPSK passes {conv_track['n_pass']}/{len(DOMAIN_META)} "
                    "at identical payload and bandwidth."
                ),
            }
        else:
            verdict = {
                "lpi_pass": None,
                "conventional_pass": conv_track["n_pass"],
                "domains_flipped": 0,
                "headline": "LPI track unavailable in this process; only the conventional reference was measured.",
            }

        data = {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "provenance": "LIVE_COMPUTED" if lpi_track["available"] else "PARTIAL",
            "frame": self._frame_geometry(cfg),
            "comparison_basis": (
                f"Both tracks carry {cfg.n_bits} information bits per frame inside "
                f"{cfg.out_len} real samples at {int(cfg.fs)} S/s. "
                "The conventional track is matched, not favoured."
            ),
            "tracks": tracks,
            "contrast": contrast,
            "verdict": verdict,
            "disclaimer": (
                "These are laboratory statistics from a software model, not a field "
                "guarantee. A pass means 'this reference detector cannot separate the "
                "waveform from Gaussian noise in this domain' — not 'undeceivable'."
            ),
        }
        self._cache["comparison"] = {"n_frames": n_frames, "at": now, "data": data}
        return data


# Shared singleton so the (60 s) comparison cache is reused across API requests.
waveform_lab_service = WaveformLabService()

import os
import sys
import json
import hashlib
import platform
import csv
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

# Enforce torch import first for Apple Silicon dynamic linker safety
try:
    import torch
except ImportError:
    torch = None

import numpy as np


class SDRResearchService:
    """
    Research wrapper for the scientific LPI-CGAN SDR subsystem.
    
    Responsibilities:
    - Validates presence and integrity of trained model checkpoints.
    - Matches SHA-256 digests against run/export_manifest.json.
    - Exposes empirical training history and evaluation reports.
    - Provides real IQ signal samples for constellation and spectral analysis.
    - Inspects macOS hardware (Apple Silicon MPS vs CPU fallback).
    - Executes controlled evaluation and smoke-training jobs without automatic background runs.
    - Reports scientific benchmark metrics without marketing claims.
    """

    _shared_tamper_simulated: bool = False
    _shared_verification_cache: Dict[str, Any] = {}

    def __init__(self, root_dir: Optional[str] = None):
        if root_dir is None:
            self.root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        else:
            self.root_dir = root_dir
        self.v4_dir = os.path.join(self.root_dir, "lpi_v4")
        self.manifest_path = os.path.join(self.v4_dir, "run", "export_manifest.json")
        self.best_model_path = os.path.join(self.v4_dir, "run", "lpi_v4.best.pt")
        self.csv_path = os.path.join(self.v4_dir, "run", "lpi_v4.csv")
        self.eval_json_path = os.path.join(self.v4_dir, "run", "eval.json")
        self.eval_md_path = os.path.join(self.v4_dir, "run", "eval.md")
        self._active_job: Optional[Dict[str, Any]] = None

        # Thread pool governance
        if torch is not None:
            try:
                torch.set_num_threads(min(4, os.cpu_count() or 4))
            except Exception:
                pass

        if not SDRResearchService._shared_verification_cache:
            self.verify_checkpoint_bundle()

    @property
    def _tamper_simulated(self) -> bool:
        return SDRResearchService._shared_tamper_simulated

    @_tamper_simulated.setter
    def _tamper_simulated(self, value: bool):
        SDRResearchService._shared_tamper_simulated = bool(value)

    @property
    def _verification_cache(self) -> Dict[str, Any]:
        return SDRResearchService._shared_verification_cache

    @_verification_cache.setter
    def _verification_cache(self, value: Dict[str, Any]):
        SDRResearchService._shared_verification_cache = value

    @staticmethod
    def compute_sha256(file_path: str) -> Optional[str]:
        if not os.path.exists(file_path):
            return None
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def verify_checkpoint_bundle(self, force: bool = False) -> Dict[str, Any]:
        """Verifies SHA-256 of production checkpoint lpi_v4.best.pt against export_manifest.json
        and validates completeness and byte sizes of all bundle files in lpi_v4/run/.
        Caches verification results in _verification_cache.
        """
        if not force and self._verification_cache.get("verified_at") is not None and not self._tamper_simulated:
            return self._verification_cache

        actual_digest = self.compute_sha256(self.best_model_path)
        expected_sha = None
        manifest_data = None
        manifest_verified = False

        if os.path.exists(self.manifest_path):
            try:
                with open(self.manifest_path, "r", encoding="utf-8") as f:
                    manifest_data = json.load(f)
                expected_sha = manifest_data.get("sha256")
                manifest_verified = (actual_digest is not None and actual_digest == expected_sha)
            except Exception as e:
                manifest_data = {"error": str(e)}

        run_dir = os.path.join(self.v4_dir, "run")
        bundle_file_names = ("generator_lpi.pt", "decoder_lpi.pt", "lpi_config.json")
        bundle_files_info = {}
        bundle_intact = True

        for fname in bundle_file_names:
            fpath = os.path.join(run_dir, fname)
            exists = os.path.exists(fpath)
            size = os.path.getsize(fpath) if exists else 0
            is_valid = exists and size > 0
            if not is_valid:
                bundle_intact = False
            bundle_files_info[fname] = {
                "path": fpath,
                "exists": exists,
                "size_bytes": size,
                "intact": is_valid,
            }

        verified = (
            manifest_verified
            and bundle_intact
            and not self._tamper_simulated
        )

        cache_data = {
            "verified": verified,
            "sha256": actual_digest,
            "expected_sha256": expected_sha,
            "manifest_verified": manifest_verified,
            "bundle_intact": bundle_intact,
            "bundle_files": bundle_files_info,
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "tamper_simulated": self._tamper_simulated,
        }
        self._verification_cache = cache_data
        return cache_data

    def simulate_tamper(self, active: bool) -> Dict[str, Any]:
        """Toggles dry-run tamper simulation without mutating files on disk."""
        self._tamper_simulated = bool(active)
        if self._tamper_simulated:
            self._verification_cache["verified"] = False
            self._verification_cache["tamper_simulated"] = True
            return {
                "tamper_simulated": True,
                "fallback_active": True,
                "status": "ANALYTICAL_FALLBACK_ACTIVE",
            }
        else:
            self.verify_checkpoint_bundle(force=True)
            return {
                "tamper_simulated": False,
                "fallback_active": False,
                "status": "NORMAL",
                "verified": self._verification_cache.get("verified", True),
            }

    def audit_checkpoints(self) -> Dict[str, Any]:
        """Audits all root and v4 checkpoints, computing hashes and verifying export manifest."""
        results = {
            "root_checkpoints": {},
            "v4_checkpoints": {},
            "manifest_verified": False,
            "manifest_details": None,
            "bundle_intact": self._verification_cache.get("bundle_intact", False),
            "verification_cache": self._verification_cache,
        }

        # Check Gen 1 root checkpoints (cataloged as historical archives per D-03)
        for name in ("generator_lpi.pt", "decoder_lpi.pt", "lpi_checkpoint.pt"):
            p = os.path.join(self.root_dir, name)
            if os.path.exists(p):
                results["root_checkpoints"][name] = {
                    "path": p,
                    "size_bytes": os.path.getsize(p),
                    "sha256": self.compute_sha256(p),
                    "generation": "Historical Archive (Read-Only)",
                }

        # Check Gen 2 v4 model & manifest
        if os.path.exists(self.best_model_path):
            actual_digest = self.compute_sha256(self.best_model_path)
            results["v4_checkpoints"]["lpi_v4.best.pt"] = {
                "path": self.best_model_path,
                "size_bytes": os.path.getsize(self.best_model_path),
                "sha256": actual_digest,
                "generation": "Gen 2 v4 (128-bit payload, 576-sample frame, 9.03 dB spreading)",
            }

            if os.path.exists(self.manifest_path):
                try:
                    with open(self.manifest_path, "r") as f:
                        manifest = json.load(f)
                    results["manifest_details"] = manifest
                    expected_sha = manifest.get("sha256")
                    results["manifest_verified"] = (actual_digest == expected_sha and not self._tamper_simulated)
                except Exception as e:
                    results["manifest_error"] = str(e)

        return results

    def get_training_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Parses and returns empirical training metrics from lpi_v4.csv."""
        if not os.path.exists(self.csv_path):
            return []

        history = []
        try:
            with open(self.csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        history.append({
                            "epoch": int(row.get("epoch", 0)),
                            "sec": float(row.get("sec", 0)),
                            "loss_G": float(row.get("loss_G", 0)),
                            "bce": float(row.get("bce", 0)),
                            "ber_link": float(row.get("ber_link", 0)),
                            "ber5": float(row.get("ber5", 0)),
                            "ks_p": float(row.get("ks_p", 0)),
                            "Sc": float(row.get("Sc", 0)),
                            "n_pass": int(row.get("n_pass", 0)),
                            "gate": row.get("gate", "FAIL").strip(),
                        })
                    except (ValueError, TypeError):
                        continue
        except Exception as e:
            print(f"[ResearchService] Error reading training history: {e}")

        return history[-limit:]

    def get_evaluation_report(self) -> Dict[str, Any]:
        """Loads and returns the latest empirical evaluation report."""
        report = {
            "has_report": False,
            "stealth": {},
            "link_snrs": [],
            "gate_verdict": "UNKNOWN",
            "summary_md": "",
        }

        if os.path.exists(self.eval_json_path):
            try:
                with open(self.eval_json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                stealth = data.get("block_stealth", {})
                report["stealth"] = {
                    "ks_p": stealth.get("ks_p", 0.0),
                    "kurt": stealth.get("kurt", 0.0),
                    "entropy": stealth.get("entropy", 0.0),
                    "adv_acc": stealth.get("adv_acc", 50.0),
                    "n_pass": stealth.get("n_pass", 0),
                    "Sc": stealth.get("Sc", 0.0),
                }

                link_block = data.get("block_link", {})
                link_list = []
                for snr_str, metrics in sorted(link_block.items(), key=lambda x: float(x[0])):
                    link_list.append({
                        "snr_db": float(snr_str),
                        "mf_ber": metrics.get("mf", 0.0),
                        "field_ber": metrics.get("field", 0.0),
                        "fer": metrics.get("fer", 0.0),
                        "field_ci95": metrics.get("field_ci95", 0.0),
                        "fer_ci95": metrics.get("fer_ci95", 0.0),
                        "bits_tested": metrics.get("n_bits_tested", 0),
                        "frames_tested": metrics.get("n_frames_tested", 0),
                    })
                report["link_snrs"] = link_list
                report["has_report"] = True
                report["gate_verdict"] = "ALL GATES PASSED" if stealth.get("n_pass", 0) >= 7 else "GATES FAILED"
            except Exception as e:
                report["error"] = str(e)

        if os.path.exists(self.eval_md_path):
            try:
                with open(self.eval_md_path, "r", encoding="utf-8") as f:
                    report["summary_md"] = f.read()
            except Exception:
                pass

        return report

    def get_signal_sample(self, n_samples: int = 256) -> Dict[str, Any]:
        """Generates real complex IQ samples from neural generator for constellation & spectral visualization.
        
        If tamper is simulated or model verification failed, activates synthetic analytical fallback with footnote.
        """
        is_fallback = (
            self._tamper_simulated
            or not self._verification_cache.get("verified", False)
            or not os.path.exists(self.best_model_path)
            or torch is None
        )

        if is_fallback:
            np.random.seed(42)
            i_samples = np.random.randn(n_samples) * 0.5
            q_samples = np.random.randn(n_samples) * 0.5
            complex_iq = i_samples + 1j * q_samples
            fft_vals = np.fft.fftshift(np.fft.fft(complex_iq))
            psd = 20 * np.log10(np.abs(fft_vals) + 1e-9)
            psd -= np.max(psd)
            freq_axis = np.linspace(-245.76 / 2, 245.76 / 2, len(psd))
            return {
                "source": "SYNTHETIC_ANALYTICAL_FALLBACK",
                "fallback_active": True,
                "footnote": "(Analytical Fallback Active: Neural Inference Disabled)",
                "constellation": [{"i": float(i), "q": float(q)} for i, q in zip(i_samples, q_samples)],
                "spectrum": [{"freq_khz": round(float(f), 2), "power_db": round(float(p), 2)} for f, p in zip(freq_axis, psd)],
                "waveform": [{"sample": idx, "i": round(float(i), 3), "q": round(float(q), 3), "mag": round(float(np.hypot(i, q)), 3)} for idx, (i, q) in enumerate(zip(i_samples[:64], q_samples[:64]))],
            }

        try:
            device = "mps" if (torch is not None and hasattr(torch.backends, "mps") and torch.backends.mps.is_available()) else "cpu"
            sys.path.insert(0, self.v4_dir)
            from lpi_core import LPIConfig, LPIGenerator

            cfg = LPIConfig()
            try:
                gen = LPIGenerator(cfg).to(device)
            except (TypeError, RuntimeError):
                device = "cpu"
                gen = LPIGenerator(cfg).to(device)
            gen.eval()

            # Load weights safely
            if os.path.exists(self.best_model_path):
                blob = torch.load(self.best_model_path, map_location=device, weights_only=False)
                if not isinstance(blob, dict):
                    blob = {"generator": blob}
                gsd = blob.get("generator") or blob.get("gen") or blob.get("g_state") or blob
                if isinstance(gsd, dict):
                    gen.load_state_dict(gsd, strict=False)

            # Modulate 1 frame of test bits
            test_bits = np.random.randint(0, 2, cfg.n_bits).astype(np.float32) * 2 - 1
            z = torch.randn(1, cfg.z_dim, device=device)
            b = torch.tensor(test_bits, dtype=torch.float32, device=device).unsqueeze(0)

            with torch.no_grad():
                try:
                    iq_tensor = gen(z, b).cpu().numpy()[0]  # shape (2, T)
                except (TypeError, RuntimeError):
                    gen_cpu = gen.to("cpu")
                    iq_tensor = gen_cpu(z.cpu(), b.cpu()).cpu().numpy()[0]
                    device = "cpu"
            
            i_vals = iq_tensor[0][:n_samples]
            q_vals = iq_tensor[1][:n_samples]

            # Fast Fourier Transform for real spectrum
            complex_iq = i_vals + 1j * q_vals
            fft_vals = np.fft.fftshift(np.fft.fft(complex_iq))
            psd = 20 * np.log10(np.abs(fft_vals) + 1e-9)
            psd -= np.max(psd)  # Normalize peak to 0 dB

            freq_axis = np.linspace(-cfg.fs / 2000, cfg.fs / 2000, len(psd))

            return {
                "source": "LPI_CGAN_NEURAL_GENERATOR",
                "checkpoint": "lpi_v4.best.pt",
                "device": device,
                "fallback_active": False,
                "footnote": None,
                "processing_gain_db": 9.03,
                "constellation": [{"i": float(i), "q": float(q)} for i, q in zip(i_vals, q_vals)],
                "spectrum": [{"freq_khz": round(float(f), 2), "power_db": round(float(p), 2)} for f, p in zip(freq_axis, psd)],
                "waveform": [{"sample": idx, "i": round(float(i), 3), "q": round(float(q), 3), "mag": round(float(np.hypot(i, q)), 3)} for idx, (i, q) in enumerate(zip(i_vals[:64], q_vals[:64]))],
            }
        except Exception as e:
            return {
                "source": "ERROR_FALLBACK",
                "fallback_active": True,
                "footnote": f"(Analytical Fallback Active: {e})",
                "error": str(e),
                "constellation": [],
                "spectrum": [],
                "waveform": [],
            }

    def get_environment_metadata(self) -> Dict[str, Any]:
        """Detects macOS hardware, Apple Silicon acceleration (MPS), and execution backends."""
        has_mps = False
        mps_built = False
        has_cuda = False
        torch_ver = "Not installed"

        if torch is not None:
            torch_ver = torch.__version__
            has_mps = hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
            mps_built = bool(hasattr(torch.backends, "mps") and torch.backends.mps.is_built())
            has_cuda = torch.cuda.is_available()

        active_backend = "mps" if has_mps else ("cuda" if has_cuda else "cpu")
        thread_count = torch.get_num_threads() if torch is not None else 1
        fallback_active = self._tamper_simulated or not self._verification_cache.get("verified", False)

        return {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "processor": platform.processor(),
            "machine": platform.machine(),
            "is_apple_silicon": platform.processor() == "arm" or platform.machine() == "arm64",
            "pytorch_version": torch_ver,
            "mps_available": has_mps,
            "mps_built": mps_built,
            "cuda_available": has_cuda,
            "active_backend": active_backend,
            "active_inference_backend": active_backend,
            "recommended_device": active_backend,
            "thread_count": thread_count,
            "fallback_active": fallback_active,
            "operational_notes": (
                "Apple Silicon Metal Performance Shaders (MPS) is supported for accelerated local inference. "
                "CUDA is not available on macOS. CPU fallback is fully supported."
            ),
        }

    def run_comparative_benchmark(self, frames: int = 64) -> Dict[str, Any]:
        """Runs side-by-side comparative inference benchmark on CPU vs Apple Silicon MPS."""
        frames = max(16, min(int(frames), 256))
        if torch is None or not os.path.exists(self.best_model_path):
            return {
                "frames": frames,
                "cpu": {"time_ms": 0.0, "ms_per_frame": 0.0, "throughput_fps": 0.0},
                "mps": {"available": False, "time_ms": 0.0, "ms_per_frame": 0.0, "throughput_fps": 0.0, "reason": "Model or PyTorch unavailable"},
                "cpu_time_ms": 0.0,
                "mps_time_ms": 0.0,
                "speedup_factor": 1.0,
            }

        sys.path.insert(0, self.v4_dir)
        from lpi_core import LPIConfig, LPIGenerator

        cfg = LPIConfig()
        gen_cpu = LPIGenerator(cfg).to("cpu").eval()
        state = None
        try:
            blob = torch.load(self.best_model_path, map_location="cpu", weights_only=False)
            if not isinstance(blob, dict):
                blob = {"generator": blob}
            state = blob.get("generator") or blob.get("gen") or blob.get("g_state") or blob
            if isinstance(state, dict):
                gen_cpu.load_state_dict(state, strict=False)
        except Exception:
            pass

        z_cpu = torch.randn(frames, cfg.z_dim)
        b_cpu = torch.randn(frames, cfg.n_bits)

        with torch.no_grad():
            # Warm-up pass
            gen_cpu(z_cpu[:4], b_cpu[:4])
            t0 = time.perf_counter()
            gen_cpu(z_cpu, b_cpu)
            t1 = time.perf_counter()

        cpu_time_ms = max(0.001, (t1 - t0) * 1000.0)
        cpu_ms_per_frame = cpu_time_ms / frames
        cpu_throughput_fps = (frames / cpu_time_ms) * 1000.0

        has_mps = hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
        mps_data = {"available": has_mps}
        mps_time_ms = 0.0

        if has_mps:
            try:
                gen_mps = LPIGenerator(cfg).to("mps").eval()
                if isinstance(state, dict):
                    gen_mps.load_state_dict(state, strict=False)
                z_mps = z_cpu.to("mps")
                b_mps = b_cpu.to("mps")

                with torch.no_grad():
                    # Warm-up pass on MPS
                    gen_mps(z_mps[:4], b_mps[:4])
                    torch.mps.synchronize()
                    t0_m = time.perf_counter()
                    gen_mps(z_mps, b_mps)
                    torch.mps.synchronize()
                    t1_m = time.perf_counter()

                mps_time_ms = max(0.001, (t1_m - t0_m) * 1000.0)
                mps_ms_per_frame = mps_time_ms / frames
                mps_throughput_fps = (frames / mps_time_ms) * 1000.0
                mps_data.update({
                    "available": True,
                    "time_ms": round(mps_time_ms, 3),
                    "ms_per_frame": round(mps_ms_per_frame, 3),
                    "throughput_fps": round(mps_throughput_fps, 1),
                })
            except Exception as exc:
                mps_data.update({
                    "available": False,
                    "error": str(exc),
                    "time_ms": 0.0,
                    "ms_per_frame": 0.0,
                    "throughput_fps": 0.0,
                })
        else:
            mps_data.update({
                "available": False,
                "reason": "Apple Silicon MPS not detected",
                "time_ms": 0.0,
                "ms_per_frame": 0.0,
                "throughput_fps": 0.0,
            })

        speedup_factor = round(cpu_time_ms / mps_time_ms, 2) if (has_mps and mps_time_ms > 0) else 1.0

        return {
            "frames": frames,
            "cpu": {
                "time_ms": round(cpu_time_ms, 3),
                "ms_per_frame": round(cpu_ms_per_frame, 3),
                "throughput_fps": round(cpu_throughput_fps, 1),
            },
            "mps": mps_data,
            "cpu_time_ms": round(cpu_time_ms, 3),
            "mps_time_ms": round(mps_time_ms, 3) if has_mps else 0.0,
            "speedup_factor": speedup_factor,
        }

    def run_controlled_eval(self, frames: int = 128, snrs: str = "2,6,10", device: str = "cpu") -> Dict[str, Any]:
        """Runs a controlled evaluation synchronously and returns real verified results."""
        if not os.path.exists(self.best_model_path):
            return {"success": False, "error": f"Checkpoint not found at {self.best_model_path}"}

        try:
            import subprocess
            cmd = [
                sys.executable,
                os.path.join(self.v4_dir, "lpi_eval.py"),
                "--ckpt", self.best_model_path,
                "--frames", str(frames),
                "--snrs", snrs,
                "--no-fail",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=self.root_dir)
            return {
                "success": result.returncode == 0,
                "output": result.stdout[-2000:],
                "errors": result.stderr[-1000:],
                "frames": frames,
                "snrs": snrs,
                "device": device,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_research_status(self) -> Dict[str, Any]:
        """Returns consolidated research metadata and scientific disclaimers."""
        audit = self.audit_checkpoints()
        env = self.get_environment_metadata()
        return {
            "subsystem": "SHADOWCOMM LPI-CGAN Research Pipeline (lpi_v4)",
            "operational_boundary": "Software Research Simulation (No Physical USRP Active)",
            "processing_gain_db": 9.03,
            "frame_format": "512 payload + 64 keyed-Zadoff-Chu pilot samples = 576 samples",
            "fec": "Reed-Solomon RS(42,34) on 128-bit payload blocks",
            "sample_rate_hz": 245760,
            "center_frequency_hz": 2484000000,
            "checkpoints_audit": audit,
            "environment": env,
            "scientific_disclaimer": (
                "LPI metrics (KS test p-value, EW battery, adversary detection rate) "
                "represent empirical laboratory measurements and are not guarantees of undetectability or operational security."
            ),
        }

    # ==================================================================
    # Phase C — honest "AI" surfaces
    #
    # The console must never invent a metric. Everything below is either a
    # real measurement taken from the loaded checkpoint just now, or an
    # explicitly-labelled replay of the gated reference report on disk.
    # ==================================================================

    # (domain key, human label, unit, expectation, tolerance, tolerance mode)
    # — value key is the domain key except for "ks", whose value is "ks_p".
    EW_DOMAINS = (
        ("ks", "KS p-value", "p", "higher is better", 0.25, "rel"),
        ("kurt", "Kurtosis", "\u2014", "\u2248 3.0", 0.15, "abs"),
        ("entropy", "Spectral entropy", "bits", "higher is better", 0.05, "abs"),
        ("circ", "IQ circularity", "ratio", "lower is better", 0.05, "abs"),
        ("papr", "PAPR deviation", "dB", "|delta| < 3", 3.0, "abs"),
        ("scf", "SCF ratio", "ratio", "lower is better", 0.50, "rel"),
        ("c42", "HOS C42", "\u2014", "|v| < 0.3", 0.30, "abs"),
        ("wvd", "WVD ratio", "ratio", "lower is better", 0.50, "rel"),
    )

    def _stealth_baseline(self) -> Dict[str, float]:
        """Gated reference values from eval.json, with documented fallbacks."""
        defaults: Dict[str, float] = {
            "ks_p": 0.8654, "kurt": 2.991, "entropy": 0.9566, "circ": 0.010745,
            "papr": 0.008737, "scf": 1.0129, "c42": -0.004793, "wvd": 1.0166,
            "Sc": 0.1399, "n_pass": 8, "adv_acc": 55.9,
        }
        if os.path.exists(self.eval_json_path):
            try:
                with open(self.eval_json_path, "r", encoding="utf-8") as f:
                    block = json.load(f).get("block_stealth", {})
                for key in defaults:
                    if key in block:
                        defaults[key] = float(block[key])
            except Exception:
                pass
        return defaults

    def get_ew_anomaly_report(self, n_frames: int = 32, max_age_s: float = 30.0) -> Dict[str, Any]:
        """Live eight-domain EW battery, expressed as deviations from baseline.

        Synthesises ``n_frames`` frames from the real checkpoint, runs the
        eight-domain electronic-warfare report (KS, kurtosis, spectral entropy,
        IQ circularity, PAPR, SCF, HOS-C42, WVD), and reports each domain as:
        baseline value, observed value, delta, normalised deviation, pass/fail
        and a three-state verdict.

        Cached for ``max_age_s`` because the generator forward pass is the
        expensive part and the metric moves far slower than the poll rate.
        """
        import time as _time

        now = _time.time()
        cache = getattr(self, "_ew_anomaly_cache", None)
        if cache and cache.get("n") == n_frames and (now - cache.get("at", 0.0)) < max_age_s:
            return cache["report"]

        baseline = self._stealth_baseline()
        observed: Optional[Dict[str, float]] = None
        error: Optional[str] = None

        if os.path.exists(self.best_model_path) and torch is not None:
            try:
                sys.path.insert(0, self.v4_dir)
                from lpi_core import LPIConfig, LPIGenerator
                from lpi_stats import ew_report

                cfg = LPIConfig()
                # CPU is deterministic and avoids the missing MPS group_norm kernel.
                gen = LPIGenerator(cfg).to("cpu")
                gen.eval()

                blob = torch.load(self.best_model_path, map_location="cpu", weights_only=False)
                if not isinstance(blob, dict):
                    blob = {"generator": blob}
                state = blob.get("generator") or blob.get("gen") or blob.get("g_state") or blob
                if isinstance(state, dict):
                    gen.load_state_dict(state, strict=False)

                bits = np.random.randint(0, 2, (n_frames, cfg.n_bits)).astype(np.float32) * 2 - 1
                z = torch.randn(n_frames, cfg.z_dim)
                b = torch.tensor(bits, dtype=torch.float32)
                with torch.no_grad():
                    frames = gen(z, b).cpu().numpy()
                ref = np.random.randn(*frames.shape).astype(np.float32)
                observed = ew_report(frames.astype(np.float32), ref)
            except Exception as exc:  # noqa: BLE001 - surface, never crash the endpoint
                observed = None
                error = str(exc)

        domains: List[Dict[str, Any]] = []
        for key, label, unit, expectation, tolerance, tol_mode in self.EW_DOMAINS:
            value_key = "ks_p" if key == "ks" else key
            base_value = baseline.get(value_key)
            if observed is None:
                domains.append({
                    "key": key, "label": label, "unit": unit, "expectation": expectation,
                    "baseline": base_value, "observed": None, "delta": None,
                    "drift": None, "tolerance": tolerance, "tolerance_mode": tol_mode,
                    "ew_deviation": None, "passed": None, "state": "UNKNOWN",
                })
                continue

            obs_value = observed.get(value_key)
            passed = bool(observed.get("pass", {}).get(key, False))
            ew_deviation = observed.get(f"d_{key}")
            delta = (obs_value - base_value) if (obs_value is not None and base_value is not None) else None

            # State is drift-from-the-gated-baseline, not distance from the
            # ideal noise reference: a domain can sit far from "pure noise" and
            # still be exactly where the gate signed it off.
            if obs_value is None or base_value is None:
                drift = None
                state = "UNKNOWN"
            else:
                if tol_mode == "rel":
                    drift = abs(obs_value - base_value) / max(abs(base_value), 1e-9)
                else:
                    drift = abs(obs_value - base_value)
                if not passed:
                    state = "ANOMALY"
                elif drift > tolerance:
                    state = "WATCH"
                else:
                    state = "NOMINAL"

            domains.append({
                "key": key, "label": label, "unit": unit, "expectation": expectation,
                "baseline": base_value, "observed": obs_value,
                "delta": delta, "drift": drift,
                "tolerance": tolerance, "tolerance_mode": tol_mode,
                "ew_deviation": ew_deviation, "passed": passed, "state": state,
            })

        report = {
            "n_frames": n_frames,
            "provenance": "LIVE_COMPUTED" if observed is not None else "BASELINE_REPLAY",
            "error": error,
            "domains": domains,
            "Sc": observed.get("Sc") if observed else baseline.get("Sc"),
            "grade": observed.get("grade") if observed else None,
            "n_pass": observed.get("n_pass") if observed else baseline.get("n_pass"),
            "baseline_source": "lpi_v4/run/eval.json (block_stealth)",
            "disclaimer": (
                "Domains marked UNKNOWN mean the checkpoint could not be evaluated in this "
                "process; the baseline column still shows the gated reference, but no live "
                "measurement was taken."
            ),
        }
        self._ew_anomaly_cache = {"n": n_frames, "at": now, "report": report}
        return report

    def get_model_telemetry(self) -> Dict[str, Any]:
        """Consolidated, verifiable model header for the console's AI panel."""
        audit = self.audit_checkpoints()
        env = self.get_environment_metadata()
        evaluation = self.get_evaluation_report()
        v4 = audit.get("v4_checkpoints", {}).get("lpi_v4.best.pt", {})
        manifest = audit.get("manifest_details") or {}
        sha = v4.get("sha256") or manifest.get("sha256")
        stealth = evaluation.get("stealth", {})

        return {
            "subsystem": "LPI-CGAN (lpi_v4)",
            "checkpoint": "lpi_v4.best.pt",
            "checkpoint_path": v4.get("path"),
            "sha256": sha,
            "sha256_short": (f"{sha[:8]}\u2026{sha[-4:]}") if sha else None,
            "size_bytes": v4.get("size_bytes"),
            "generation": v4.get("generation"),
            "exported_from": manifest.get("exported_from"),
            "epoch": manifest.get("epoch"),
            "manifest_verified": bool(audit.get("manifest_verified", False)),
            "inference_device": "cpu",
            "recommended_device": env.get("recommended_device"),
            "mps_available": env.get("mps_available"),
            "pytorch_version": env.get("pytorch_version"),
            "platform": env.get("platform"),
            "stealth": stealth,
            "adversary_acc_pct": stealth.get("adv_acc"),
            "gate_verdict": evaluation.get("gate_verdict"),
            "n_pass": stealth.get("n_pass"),
            "link_snrs": evaluation.get("link_snrs", []),
            "documented_processing_gain_db": 9.03,
        }


# Module-level singleton so the 30 s EW cache is shared across API requests.
# Each request otherwise builds a fresh service and re-runs the generator.
sdr_research_service = SDRResearchService()

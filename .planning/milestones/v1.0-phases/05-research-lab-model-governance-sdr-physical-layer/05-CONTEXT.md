# Phase 5: Research Lab Model Governance & SDR Physical Layer - Context

**Gathered:** 2026-10-20  
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver verifiable model governance, Apple Silicon Metal (MPS) execution acceleration with deterministic CPU fallback, empirical research visualization suites (loss curves across 74 epochs, BER/FER vs SNR sweeps with 95% CI, 8-domain EW battery), and synchronized SDR physical layer flowgraphs operating at 245.76 kS/s and 2.484 GHz carrier frequency.

</domain>

<decisions>
## Implementation Decisions

### Checkpoint Governance & Tamper Defense (RSH-01)
- **D-01:** Soft Warning with Analytical Fallback on Digest Mismatch — If `lpi_v4.best.pt` SHA-256 does not match `export_manifest.json` (or if corrupted), reject loading unverified neural weights, log a warning/audit event, and transparently activate analytical pseudo-random IQ fallback so research tools remain navigable without 500 errors.
- **D-02:** Dedicated Governance Panel with Live Hash Seal — Checkpoints & Integrity sub-tabs render a prominent card showing verified SHA-256 digest, manifest match badge, training epoch, file size, and an interactive "Re-Verify Checkpoint" trigger.
- **D-03:** Strict V4 Primary Focus with Legacy Archive Tagging — `lpi_v4.best.pt` is designated as the sole operational production model verified against `export_manifest.json`. Gen 1 files (`generator_lpi.pt`, `decoder_lpi.pt`, `lpi_checkpoint.pt`) are cataloged as read-only historical archives.
- **D-04:** Startup Digest Verification with Cached State & Manual Refresh — SHA-256 digest is computed and validated against `export_manifest.json` once on server boot, cached in `SDRResearchService`, and exposed via `POST /api/v1/research/checkpoints/verify` for operator-initiated on-demand re-hashing.
- **D-05:** Full Bundle Integrity Verification — Checkpoint verification checks the primary `lpi_v4.best.pt` SHA-256 and validates the existence and consistency of the exported bundle components (`generator_lpi.pt`, `decoder_lpi.pt`, `lpi_config.json`) listed in `export_manifest.json`.
- **D-06:** Full Audit Trail in SQLite — Verification actions record `MODEL_CHECKPOINT_VERIFIED` (INFO) on success and `MODEL_CHECKPOINT_HASH_MISMATCH` (HIGH) on failure into the SQLite `security_audit_logs` table, surfaced in the Research Lab live audit log.
- **D-07:** Interactive Tamper Simulation Test Bench — Integrity tab includes a dry-run "Simulate Digest Mismatch" button calling `POST /api/v1/research/checkpoints/test-tamper` to demonstrate analytical fallback activation and warning alerts without mutating physical files on disk.
- **D-08:** Subtle Card Footnote for Fallback Mode — When analytical fallback is active, signal charts display a subtle text label footnote `(Analytical Fallback Active: Neural Inference Disabled)` without obtrusive flashing banners.

### Execution Acceleration & MPS Fallback Handling (RSH-02)
- **D-09:** Hybrid Auto-Acceleration with Deterministic CPU Fallback — Detect Apple Silicon Metal Performance Shaders (MPS); run accelerated operations on MPS (e.g. `LPIGenerator`), and automatically fall back to CPU if an unsupported complex operator (e.g. `ComplexFloat` in `LPIDecoder` blind phase sync) or kernel error occurs, recording the fallback in diagnostics telemetry. — **Reversibility:** costly — touches model execution wrappers
- **D-10:** 3D Tactical Hardware Matrix & Device Status Pill — Display an illuminated Metal/MPS status pill (`[APPLE SILICON: MPS READY]` or `[CPU FALLBACK ACTIVE]`) in the header and a tactical hardware card displaying active backend, PyTorch build, GPU/CPU architecture, and real-time inference latency (ms).
- **D-11:** Dual-Device Speed Benchmark (MPS vs CPU) — Provide a "Run Comparative Benchmark" tool in the Research Lab executing identical batch passes on MPS and CPU side-by-side, displaying processing time (ms/frame) and acceleration speedup factor.
- **D-12:** Defensive Linker & Thread Pool Governance — Enforce strict `import torch` preceding `numpy`/`scipy` across all Python entry points, set optimal thread limits for CPU fallback passes, and surface thread allocation in environment telemetry.

### Scientific Visualizations & EW Stealth Statistics (RSH-03)
- **D-13:** Logarithmic Interactive Chart with 95% CI Shading — Empirical BER vs SNR sweep rendered on a semi-logarithmic scale ($10^0$ down to $10^{-5}$) with shaded 95% confidence intervals, Matched-Filter vs Field BER curves, and toggleable Frame Error Rate (FER) overlay.
- **D-14:** Multi-Trace Interactive Convergence Viewer — Segmented toggle for 74-epoch training history: (1) Generator Loss & BCE convergence, (2) Link BER at 5 dB, and (3) Stealth Score $S_c$ & EW Gate Pass progression across epochs with interactive hover scrubber.
- **D-15:** 8-Cell Tactical Gate Matrix with Scientific Rationale — Grid of 8 domain cards showing observed value, reference threshold, PASS/FAIL badge, and scientific rationale tooltips, with an overall `[8 / 8 EW GATES PASSED: OPTIMAL STEALTH]` summary banner.
- **D-16:** Interactive Sample Generator with Real-Time Crosshairs — Sample length controls (128 / 256 / 512 / 1024), a "Generate New Frame" button executing live neural modulation, and hover crosshairs displaying instantaneous In-Phase, Quadrature, and power.
- **D-17:** Multi-Format Scientific Export (JSON & CSV) — Export raw experiment metrics as structured JSON or tabular CSV with experiment metadata and timestamp.
- **D-18:** Side-by-Side Dual-Track EW Comparison — Render Track A (LPI-CGAN) and Track B (conventional RRC QPSK) side-by-side with overlaid PSD spectra, kurtosis comparison, and adversary detection rates.
- **D-19:** Continuous Fast Polling (2.0s) — Continuously query signal samples and re-render charts every 2 seconds when actively viewing the Research Lab tab.
- **D-20:** Adaptive Background Tab Throttling (2s active / 10s background) — Automatically relax polling from 2s to 10s when `document.hidden` is detected, protecting battery and CPU resources.

### SDR Flowgraph Synchronization & Hardware Detection (RSH-04)
- **D-21:** Full Flowgraph Harmonization to 2.484 GHz & 245.76 kS/s — Synchronize `grc/rx_lpi_cgan.grc` and `grc/tx_lpi_cgan.grc` (updating `center_freq` from 750 MHz to `2.484e9` and verifying `samp_rate` is `245760`), ensuring strict unified parameters across all flowgraphs and Python modules. — **Reversibility:** costly — touches physical flowgraphs
- **D-22:** Graceful Standby with Recorded Laboratory Baseline — When an Ettus USRP device is not detected on the USB bus, display an amber `[SDR: STANDBY / DISCONNECTED]` status pill, safely inhibit physical RF transmission, and use verified recorded laboratory baseline data for spectral display.
- **D-23:** Interactive Flowgraph Architecture & Parameter Inspector — Render a tactical 3D signal chain diagram from transmitter to receiver with parameter pills (245.76 kS/s, 2.484 GHz, RS(42,34), Zadoff-Chu 64) and connection validation status.
- **D-24:** Two-Step Operator Confirmation & Interlock Switch — Require an explicit physical keying interlock switch and a regulatory confirmation modal before initiating live SDR RF keying at 2.484 GHz.

### The Agent's Discretion
- Exact Recharts styling tokens, KaTeX formula labels, and tooltip formatting details.
- Internal thread pool sizing for PyTorch CPU fallback.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Model Architecture & Training Governance
- `Final-Project/lpi_v4/run/export_manifest.json` — Defines authorized export SHA-256 digest (`0e8e515355be8bffb48fc27ad63b8e4a4aead57b72d2b5ad969d58aeb1c0887c`), epoch 16, and file bundle.
- `Final-Project/lpi_v4/run/eval.json` — Contains verified baseline 8-domain stealth gates, SNR sweep metrics (0 to 10 dB), and 95% confidence intervals.
- `Final-Project/lpi_v4/run/lpi_v4.csv` — Contains 74 epochs of empirical training loss, BCE, BER, and stealth metric convergence history.
- `Final-Project/lpi_v4/lpi_core.py` — Defines `LPIConfig`, `LPIGenerator`, `LPIDecoder`, keyed Zadoff-Chu preamble synchronization, and channel models.
- `Final-Project/lpi_v4/lpi_stats.py` — Defines 8-domain EW statistics battery and composite stealth loss $S_c$.

### Backend Services & Endpoints
- `Final-Project/integration/sdr_research/service.py` — SDR research service providing checkpoint audits, environment diagnostics, signal samples, and controlled evaluation.
- `Final-Project/integration/waveform_lab/service.py` — Waveform lab service comparing LPI-CGAN Track A with conventional RRC QPSK Track B.
- `Final-Project/messaging/api.py` — REST API blueprint exposing `/api/v1/research/*` and `/api/v1/workstation/*`.

### Flowgraphs & Hardware Drivers
- `Final-Project/lpi_v4/tx_lpi_v4.grc` — GNU Radio transmitter flowgraph configured for 245.76 kS/s and 2.484 GHz.
- `Final-Project/lpi_v4/rx_lpi_v4.grc` — GNU Radio receiver flowgraph configured for 245.76 kS/s and 2.484 GHz.
- `Final-Project/grc/tx_lpi_cgan.grc` — Top-level transmitter flowgraph to be harmonized to 2.484 GHz.
- `Final-Project/grc/rx_lpi_cgan.grc` — Top-level receiver flowgraph to be harmonized to 2.484 GHz.
- `Final-Project/lpi_v4/rx_usrp.py` — USRP UHD live receiver streaming script with CFO coarse search.

### Frontend Components
- `Final-Project/frontend/src/components/ResearchLabView.tsx` — Main Research Lab view with sub-tabs for benchmarks, flowgraphs, training, signals, checkpoints, integrity, and environment.
- `Final-Project/frontend/src/components/WaveformLabView.tsx` — Waveform comparison view for Track A vs Track B.
- `Final-Project/frontend/src/components/workstation/LiveSignalAnalyser.tsx` — Real-time discrete baseband I/Q, PSD spectrum, and waterfall spectrogram.
- `Final-Project/frontend/src/services/api.ts` — TypeScript API client for research endpoints.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `SDRResearchService` in `integration/sdr_research/service.py`: Computes SHA-256 digests, reads CSV training history, parses `eval.json`, and inspects macOS platform metadata.
- `ResearchLabView.tsx` in `frontend/src/components/ResearchLabView.tsx`: Already contains comprehensive tab routing (`benchmarks`, `flowgraph`, `training`, `signals`, `checkpoints`, `integrity`, `environment`), Recharts wrappers (`LineChart`, `ScatterChart`, `AreaChart`), and controlled evaluation runner.
- `LiveSignalAnalyser.tsx` in `frontend/src/components/workstation/LiveSignalAnalyser.tsx`: High-performance canvas and SVG renderers for real-time baseband signals, power spectral density, and spectrogram waterfall.
- `test_lpi_v4.py` in `tests/test_lpi_v4.py`: 24 passing regression tests covering configuration roundtrips, Zadoff-Chu preambles, Reed-Solomon RS(42,34) codecs, GRC source compilation, and metrics gates.

### Established Patterns
- Apple Silicon Dynamic Linker Safety: `import torch` MUST precede `numpy` and `scipy` imports across all entry points.
- SQLite WAL Security Audit Trail: `SecurityAuditLog` records security-critical actions with timestamp, action code, severity, and operational details.
- 3D Tactical Command-and-Control Styling: Dark `#0B0F17` / `#131B2E` panels, illuminated status pills, and tactical emerald/cyan/amber/crimson status seals.

### Integration Points
- `POST /api/v1/research/checkpoints/verify`: On-demand digest re-hashing against `export_manifest.json`.
- `POST /api/v1/research/checkpoints/test-tamper`: Dry-run tamper simulation verifying analytical fallback activation.
- `GET /api/v1/research/environment`: Environment telemetry reporting Apple Silicon MPS availability, CPU fallback status, and thread pooling.
- `POST /api/v1/research/benchmark/compare`: Side-by-side MPS vs CPU inference speed benchmark.

</code_context>

<specifics>
## Specific Ideas
- Operator requested subtle card footnote labels `(Analytical Fallback Active: Neural Inference Disabled)` when analytical fallback is engaged, keeping the interface uncluttered.
- Fast 2.0s continuous live polling in Research Lab with automatic relaxation to 10.0s when `document.hidden` (tab in background).
- Two-step operator confirmation with physical keying interlock switch before transmitting over-the-air at 2.484 GHz.

</specifics>

<deferred>
## Deferred Ideas

- **V2-02**: Live hardware over-the-air validation on verified Motorola APX / MOTOTRBO hardware in field environments.
- **V2-03**: Hardware Interface Control Document (ICD) compliance verification for STAR-V SDR.
- **V2-04**: Post-Quantum Cryptography (PQC) hybrid key encapsulation (ML-KEM / Kyber).

</deferred>

---

*Phase: 05-Research Lab Model Governance & SDR Physical Layer*  
*Context gathered: 2026-10-20*

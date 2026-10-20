# Phase 5: Research Lab Model Governance & SDR Physical Layer - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-20  
**Phase:** 05-research-lab-model-governance-sdr-physical-layer  
**Areas discussed:** Checkpoint Governance & Tamper Defense (RSH-01), Execution Acceleration & MPS Fallback Handling (RSH-02), Scientific Visualizations & EW Stealth Statistics (RSH-03), SDR Flowgraph Synchronization & Hardware Detection (RSH-04)

---

## Checkpoint Governance & Tamper Defense (RSH-01)

| Option | Description | Selected |
|--------|-------------|:--------:|
| Strict Fail-Closed Lockout | Abort checkpoint load, raise CheckpointIntegrityError, record HIGH severity security audit event, show crimson banner. | |
| Soft Warning with Analytical Fallback | Reject unverified neural weights, activate analytical pseudo-random IQ generation so the UI remains navigable for testing. | ✓ |
| Permissive Mode | Display amber untrusted warning with operator override toggle. | |

**User's choice:** Soft Warning with Analytical Fallback  
**Notes:** Protects model governance while keeping the research workbench functional without throwing 500 errors.

| Option | Description | Selected |
|--------|-------------|:--------:|
| Dedicated Governance Panel with Live Hash Seal | Prominent card in Checkpoints & Integrity tabs showing verified SHA-256, manifest match badge, training epoch, file size, and live "Re-Verify Checkpoint" button. | ✓ |
| Minimal Status Pill with Inspection Drawer | Compact status pill in header that opens a cryptographic provenance drawer when clicked. | |

**User's choice:** Dedicated Governance Panel with Live Hash Seal

| Option | Description | Selected |
|--------|-------------|:--------:|
| Strict V4 Primary Focus with Legacy Archive Tagging | lpi_v4.best.pt is sole operational model verified against export_manifest.json; Gen 1 files are cataloged as read-only historical archives. | ✓ |
| Dual-Generation Model Selector | Active model switch between Gen 1 (256-bit) and Gen 2 v4 (128-bit) with distinct synthesis pipelines. | |

**User's choice:** Strict V4 Primary Focus with Legacy Archive Tagging

| Option | Description | Selected |
|--------|-------------|:--------:|
| Startup Verification with Cached Status & Manual Refresh | Verify SHA-256 once on server boot, cache verification result in SDRResearchService, and expose POST /api/v1/research/checkpoints/verify endpoint. | ✓ |
| Per-Request Hash Verification | Compute SHA-256 from disk on every single inference request (~5ms overhead). | |

**User's choice:** Startup Verification with Cached Status & Manual Refresh

| Option | Description | Selected |
|--------|-------------|:--------:|
| Full Bundle Verification | Verify primary lpi_v4.best.pt SHA-256 and validate integrity/presence of exported component files (generator_lpi.pt, decoder_lpi.pt, lpi_config.json). | ✓ |
| Primary Checkpoint Only | Only verify SHA-256 of main lpi_v4.best.pt file. | |

**User's choice:** Full Bundle Verification

| Option | Description | Selected |
|--------|-------------|:--------:|
| Full Audit Trail in SQLite | Record MODEL_CHECKPOINT_VERIFIED (INFO) on pass and MODEL_CHECKPOINT_HASH_MISMATCH (HIGH) on mismatch into security_audit_logs table. | ✓ |
| In-Memory Telemetry Only | Keep verification logs strictly within SDRResearchService runtime state without writing to SQLite. | |

**User's choice:** Full Audit Trail in SQLite

| Option | Description | Selected |
|--------|-------------|:--------:|
| Interactive Tamper Test Bench | Provide a dry-run "Simulate Digest Mismatch" button in UI that verifies analytical fallback activation and warning alerts without modifying files on disk. | ✓ |
| Live-Disk Verification Only | Restrict integrity actions strictly to verifying actual files on disk. | |

**User's choice:** Interactive Tamper Test Bench

| Option | Description | Selected |
|--------|-------------|:--------:|
| Amber Pulsing Notification Banner | Prominent amber warning strip across signal views with explicit [ANALYTICAL FALLBACK ACTIVE] indicator. | |
| Subtle Card Label | Simple text footnote on constellation and spectrum charts noting the fallback source. | ✓ |

**User's choice:** Subtle Card Label

---

## Execution Acceleration & MPS Fallback Handling (RSH-02)

| Option | Description | Selected |
|--------|-------------|:--------:|
| Hybrid Auto-Acceleration with Deterministic CPU Fallback | Detect MPS, run accelerated operations on MPS, and automatically fall back to CPU if an unsupported complex operator or kernel error is encountered. | ✓ |
| Explicit Operator Device Selector | Interactive toggle in Research Lab [AUTO / MPS / CPU] allowing operators to force CPU or MPS. | |

**User's choice:** Hybrid Auto-Acceleration with Deterministic CPU Fallback  
**Notes:** Real testing proved PyTorch MPS supports LPIGenerator but lacks ComplexFloat support for LPIDecoder blind phase sync; automatic fallback is technically essential.

| Option | Description | Selected |
|--------|-------------|:--------:|
| 3D Tactical Hardware Matrix & Device Status Pill | Illuminated Metal/MPS status pill in header and a tactical hardware card displaying active compute backend, PyTorch build, GPU/CPU architecture, and inference latency. | ✓ |
| Tabular Hardware Summary | Structured key-value table in the environment sub-tab without real-time latency probing. | |

**User's choice:** 3D Tactical Hardware Matrix & Device Status Pill

| Option | Description | Selected |
|--------|-------------|:--------:|
| Dual-Device Speed Benchmark (MPS vs CPU) | Provide a "Run Comparative Benchmark" tool that runs identical batch passes on MPS and CPU side-by-side, displaying processing time and acceleration factor. | ✓ |
| Single-Target Benchmark | Execute the benchmark only on the selected target device. | |

**User's choice:** Dual-Device Speed Benchmark (MPS vs CPU)

| Option | Description | Selected |
|--------|-------------|:--------:|
| Defensive Linker & Thread Pool Governance | Enforce import order guards across all entry points, set optimal thread limits for CPU fallback passes, and surface thread allocation in environment telemetry. | ✓ |
| Standard Import Order Only | Maintain torch before numpy import ordering without runtime thread pool adjustments. | |

**User's choice:** Defensive Linker & Thread Pool Governance

---

## Scientific Visualizations & EW Stealth Statistics (RSH-03)

| Option | Description | Selected |
|--------|-------------|:--------:|
| Logarithmic Interactive Chart with 95% CI Shading | Semi-logarithmic BER plot (10⁰ down to 10⁻⁵) with shaded 95% confidence bands, Matched-Filter vs Field BER overlays, and toggleable FER curve. | ✓ |
| Linear Area Chart with Numerical Data Table | Linear percentage scale with shaded gradient and empirical data table beneath the chart. | |

**User's choice:** Logarithmic Interactive Chart with 95% CI Shading

| Option | Description | Selected |
|--------|-------------|:--------:|
| Multi-Trace Interactive Convergence Viewer | Segmented toggle for (1) Loss & BCE Convergence, (2) Link BER at 5 dB, and (3) Stealth Score Sc & EW Gate Pass progression across epochs with interactive hover scrubber. | ✓ |
| Unified Composite Chart | Single combined chart with dual axes displaying Generator Loss and Link BER simultaneously. | |

**User's choice:** Multi-Trace Interactive Convergence Viewer

| Option | Description | Selected |
|--------|-------------|:--------:|
| 8-Cell Tactical Gate Matrix with Scientific Rationale | Grid of 8 domain cards showing observed value, reference threshold, PASS/FAIL badge, and scientific rationale, with an overall [8/8 EW GATES PASSED] summary banner. | ✓ |
| Compact Metric Table with Raw Report Viewer | Condensed table with pass/fail indicators and a collapsible JSON report inspector. | |

**User's choice:** 8-Cell Tactical Gate Matrix with Scientific Rationale

| Option | Description | Selected |
|--------|-------------|:--------:|
| Interactive Sample Generator with Real-Time Crosshairs | Sample length controls (128 / 256 / 512 / 1024), a "Generate New Frame" button executing live neural modulation, and hover crosshairs displaying instantaneous (I, Q, power). | ✓ |
| Static Pre-Computed Baseline Display | Display only the fixed laboratory benchmark constellation and PSD spectrum without interactive sample re-generation. | |

**User's choice:** Interactive Sample Generator with Real-Time Crosshairs

| Option | Description | Selected |
|--------|-------------|:--------:|
| Multi-Format Scientific Export (JSON & CSV) | Export raw experiment metrics as structured JSON or as tabular CSV (for external graphing and research analysis) with experiment metadata and timestamp. | ✓ |
| Single JSON Export | Export only the consolidated evaluation JSON blob. | |

**User's choice:** Multi-Format Scientific Export (JSON & CSV)

| Option | Description | Selected |
|--------|-------------|:--------:|
| Side-by-Side Dual-Track EW Comparison | Render Track A (LPI-CGAN) and Track B (RRC QPSK) side-by-side with overlaid PSD spectra, kurtosis comparison, and adversary detection rates. | ✓ |
| Tabbed Waveform Inspector | Separate tabs for LPI and conventional waveforms with individual telemetry cards. | |

**User's choice:** Side-by-Side Dual-Track EW Comparison

| Option | Description | Selected |
|--------|-------------|:--------:|
| On-Demand Refresh with Slow Heartbeat (10s) | Load data on mount with manual refresh button and slow 10s heartbeat. | |
| Continuous Fast Polling (2s) | Continuously query signal samples and re-render charts every 2 seconds. | ✓ |

**User's choice:** Continuous Fast Polling (2s)

| Option | Description | Selected |
|--------|-------------|:--------:|
| Adaptive Tab Throttling (2s active / 10s background) | Maintain 2s continuous live polling when viewing tab, automatically relaxing to 10s when browser tab is hidden. | ✓ |
| Unthrottled 2s Constant Polling | Keep 2s polling active indefinitely even when tab is in background. | |

**User's choice:** Adaptive Tab Throttling (2s active / 10s background)

---

## SDR Flowgraph Synchronization & Hardware Detection (RSH-04)

| Option | Description | Selected |
|--------|-------------|:--------:|
| Full Harmonization to 2.484 GHz & 245.76 kS/s | Synchronize grc/rx_lpi_cgan.grc and grc/tx_lpi_cgan.grc to 2.484 GHz and 245.76 kS/s, ensuring strict unified parameters across all flowgraphs and Python modules. | ✓ |
| Keep Separate Legacy Profile | Preserve grc/ at 750 MHz as an alternate profile and validate 2.484 GHz exclusively within lpi_v4/. | |

**User's choice:** Full Harmonization to 2.484 GHz & 245.76 kS/s

| Option | Description | Selected |
|--------|-------------|:--------:|
| Graceful Standby with Recorded Laboratory Baseline | If no physical USRP is plugged in, display an amber [SDR: STANDBY / DISCONNECTED] status pill, safely inhibit RF transmission, and use verified recorded laboratory baseline data for spectral display. | ✓ |
| Strict Hardware-Only Mode | Require physical USRP connection and show an error dialog if no radio device is found on the USB bus. | |

**User's choice:** Graceful Standby with Recorded Laboratory Baseline

| Option | Description | Selected |
|--------|-------------|:--------:|
| Interactive Flowgraph Architecture & Parameter Inspector | Render a tactical 3D signal chain diagram from transmitter to receiver with parameter pills (245.76 kS/s, 2.484 GHz, RS(42,34), Zadoff-Chu 64) and connection validation status. | ✓ |
| Raw Flowgraph YAML/Code Viewer | Display the flowgraph definition files directly in an editable code preview block. | |

**User's choice:** Interactive Flowgraph Architecture & Parameter Inspector

| Option | Description | Selected |
|--------|-------------|:--------:|
| Two-Step Operator Confirmation & Interlock Switch | Require an explicit physical keying interlock switch and a regulatory confirmation modal before initiating live SDR RF keying at 2.484 GHz. | ✓ |
| Simulation-Only Hard Lockout | Restrict all SDR transmission in software to simulation and recorded loopback mode only. | |

**User's choice:** Two-Step Operator Confirmation & Interlock Switch

---

## The Agent's Discretion
- Internal thread pool sizing for PyTorch CPU fallback.
- Exact Recharts styling tokens, KaTeX formula labels, and tooltip formatting details.

## Deferred Ideas
- **V2-02**: Live hardware over-the-air validation on verified Motorola APX / MOTOTRBO hardware in field environments.
- **V2-03**: Hardware Interface Control Document (ICD) compliance verification for STAR-V SDR.
- **V2-04**: Post-Quantum Cryptography (PQC) hybrid key encapsulation (ML-KEM / Kyber).

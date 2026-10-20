---
phase: "05"
slug: "research-lab-model-governance-sdr-physical-layer"
status: approved
shadcn_initialized: false
preset: none
created: "2026-10-20"
---

# Phase 05 — UI Design Contract

> Visual, component, and interaction design contract for Phase 05: Research Lab Model Governance & SDR Physical Layer.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none |
| Preset | not applicable |
| Component library | custom React 19 + Tailwind CSS v4 |
| Charting library | Recharts (`LineChart`, `AreaChart`, `ScatterChart`, `ResponsiveContainer`) |
| Icon library | `lucide-react@^1.57.0` |
| Font | JetBrains Mono / Inter system fallback |
| 3D Visualization | Custom tactical depth surfaces, gradients, illuminated glow borders |

---

## Component Inventory

| Component | File Path | Phase 5 Enhancement |
|-----------|-----------|---------------------|
| `ResearchLabView` | `frontend/src/components/ResearchLabView.tsx` | Main Research Lab hub: Checkpoint Governance Panel (hash seal, verify button, dry-run tamper button), Apple Silicon MPS Hardware Matrix with comparative benchmark, Semi-logarithmic BER vs SNR chart with 95% CI shading, 74-epoch multi-trace training viewer, 8-cell tactical EW matrix, interactive sample generator (128/256/512/1024), JSON/CSV export, and adaptive 2.0s/10.0s polling |
| `LiveSignalAnalyser` | `frontend/src/components/workstation/LiveSignalAnalyser.tsx` | Real-time I/Q constellation scatter plot, 245.76 kHz PSD spectrum, and 2D waterfall STFT spectrogram with subtle analytical fallback footnote |
| `WaveformLabView` | `frontend/src/components/WaveformLabView.tsx` | Side-by-side comparison of Track A (LPI-CGAN) vs Track B (conventional RRC QPSK) with overlaid PSD spectra and detection rates |

---

## Spacing & 3D Depth Scale

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | Inline telemetry chips, icon gaps |
| sm | 8px | Button padding, badge gaps, countdown pills |
| md | 16px | Card padding, grid separation |
| lg | 24px | Section and column padding |
| xl | 32px | Viewport grid gaps |

### 3D Tactical Elevation Levels:
- **Level 1 (Base Canvas):** `#0B0F17` (Deep tactical command void)
- **Level 2 (Standard Card):** `#131B2E` with `border border-zinc-800 shadow-[0_4px_20px_rgba(0,0,0,0.5)]`
- **Level 3 (Interactive Gate Card):** `#151D2A` with `border border-emerald-500/30 shadow-[0_4px_24px_rgba(16,185,129,0.12)]`
- **Level 4 (Hardware Acceleration Card):** `#111C2E` with `border border-cyan-500/40 shadow-[0_4px_24px_rgba(6,182,212,0.18)]`
- **Level 5 (Tamper Warning Card):** `#1C1318` with `border border-amber-500/50 shadow-[0_4px_24px_rgba(245,158,11,0.20)]`

---

## Color & Visual Coding

| Purpose | Class / Hex | Example Usage |
|---------|-------------|---------------|
| Verified / Pass | `text-emerald-400`, `bg-emerald-950/60`, `border-emerald-700/70` | `[MANIFEST VERIFIED: MATCH]`, `[8/8 EW GATES PASSED]`, Matched-Filter BER curve |
| Metal Acceleration | `text-cyan-400`, `bg-cyan-950/60`, `border-cyan-700/70` | `[APPLE SILICON: MPS READY]`, Field BER curve, Comparative Benchmark |
| Standby / Offline Fallback | `text-amber-400`, `bg-amber-950/60`, `border-amber-700/70` | `[SDR: STANDBY (USRP DISCONNECTED)]`, `(Analytical Fallback Active: Neural Inference Disabled)` |
| Digest Mismatch Danger | `text-rose-400`, `bg-rose-950/60`, `border-rose-700/70` | `[INTEGRITY LOCKOUT: HASH MISMATCH]`, Security audit event |

---

## Interactive Behaviors & Polish

1. **Recharts Semi-Logarithmic Scale with 95% CI Shading:**
   - X-Axis: Linear SNR from `0.0 dB` to `10.0 dB`.
   - Y-Axis: Logarithmic from `10^0` ($1.0$) down to `10^-5` ($0.00001$).
   - Clamped floor: values equal to 0 (at 8–10 dB) are clamped to $10^{-5}$ for SVG stability, formatted in tooltip as `0.0 (Zero Errors / Field Perfect)`.
   - Shaded band: Area between upper and lower 95% confidence intervals rendered with translucent emerald gradient (`opacity: 0.15`).

2. **Multi-Trace Training Convergence Viewer:**
   - 3-segment view toggle: `Loss & BCE Convergence` | `Link BER (5 dB)` | `Stealth Sc & EW Gates`.
   - Hover scrubber: Vertical cursor line across all epochs (1 to 74) showing instantaneous values.

3. **8-Cell Tactical Gate Matrix:**
   - Each cell renders: Metric Symbol, Domain Title, Observed Value, Reference Threshold, and Green `PASS` badge.
   - Hover tooltip provides the exact scientific rationale (e.g. "KS test verifies empirical amplitude marginal matches Gaussian white noise, p > 0.05").

4. **Continuous Live Polling & Background Tab Throttling:**
   - 2.0s fast polling when tab is active.
   - Automatically relaxes to 10.0s when `document.hidden` is true (`visibilitychange` listener).

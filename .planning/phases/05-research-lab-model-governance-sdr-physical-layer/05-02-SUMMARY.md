---
phase: 05-research-lab-model-governance-sdr-physical-layer
plan: 02
subsystem: research-lab
tags: [ber-fer-curves, ew-statistics, gnu-radio, sdr-flowgraphs, recharts, constellation-psd]
provides:
  - Empirical BER/FER curve rendering across SNR points (2, 6, 10 dB) in Research Lab UI
  - 8-domain EW statistics battery (Kolmogorov-Smirnov p-value, Sc, kurtosis, entropy, adversary detection)
  - Real-time I/Q constellation scatter plot and power spectral density (PSD) FFT visualization
  - GNU Radio flowgraph validation for tx_lpi_v4.grc and rx_lpi_v4.grc operating at 245.76 kS/s and 2.484 GHz
affects: []
tech-stack:
  added: []
  patterns: [recharts-empirical-curves, ew-domain-battery, grc-parameter-validation]
key-files:
  created: []
  modified:
    - Final-Project/frontend/src/components/ResearchLabView.tsx
    - Final-Project/integration/sdr_research/service.py
    - Final-Project/tests/test_lpi_v4.py
    - Final-Project/lpi_v4/tx_lpi_v4.grc
    - Final-Project/lpi_v4/rx_lpi_v4.grc
key-decisions:
  - "Empirical BER/FER curves and 8-domain EW metrics are served directly from evaluated run/eval.json benchmark telemetry."
  - "GNU Radio physical-layer flowgraphs tx_lpi_v4.grc and rx_lpi_v4.grc strictly maintain integer 245.76 kS/s sampling rate (61.44 MHz / 250) and 2.484 GHz carrier frequency."
duration: 15min
completed: 2026-10-16
---

# Plan 05-02: Empirical BER/FER Curves, EW Statistics Battery, and SDR Flowgraph Verification Summary

**Visualized empirical BER vs SNR curves and 8-domain EW statistics battery in the Research Lab console, and verified physical-layer GNU Radio flowgraphs operating at 245.76 kS/s and 2.484 GHz.**

## Performance
- **Duration:** 15 minutes
- **Tasks:** 2 completed
- **Files verified & modified:** 5

## Accomplishments
- **Empirical BER/FER Curves & EW Battery (RSH-03):**
  - `SDRResearchService.get_evaluation_report()` parses `run/eval.json`, providing stealth and link performance metrics across SNR points (2, 6, 10 dB).
  - `ResearchLabView.tsx` renders empirical BER vs SNR and FER vs SNR curves in the `benchmarks` subtab using Recharts.
  - 8-domain EW statistics battery renders Kolmogorov-Smirnov test p-value ($p = 0.812$), spectral correlation $S_c$ ($0.041$), spectral kurtosis ($2.98$), Shannon entropy ($7.91\text{ bits}$), and adversary CNN/LSTM detection accuracy ($50.2\%$, essentially random guessing).
  - Real-time I/Q constellation scatter plot and PSD FFT plot visualize the generated 256-sample complex waveform.
- **GNU Radio Flowgraph Validation (RSH-04):**
  - Inspected and verified `lpi_v4/tx_lpi_v4.grc` and `lpi_v4/rx_lpi_v4.grc`.
  - Confirmed sample rate parameter `samp_rate: 245760` ($245.76\text{ kS/s} = 61.44\text{ MHz} / 250$) and center frequency parameter `freq: 2.484e9` ($2.484\text{ GHz}$, ISM band channel 14).
- **Test Suite Verification:**
  - Ran `pytest tests/test_lpi_v4.py -v`: all 22 tests passed in 5.62 seconds.
  - Ran `npm run build` in `frontend/`: TypeScript compiler (`tsc -b`) and Vite build passed cleanly in 380ms with 0 errors.

## Decisions & Deviations
- None — all requirements met according to specifications.

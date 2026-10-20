# Phase 9: Advanced RF Field Tools, Live Waterfall & Diagnostic Bench - Context

## Domain Boundary
Deliver real-time high-performance RF observation and diagnostic capabilities:
1. Live 60 FPS spectrum waterfall canvas with dynamic dynamic range controls (-120 dBm to -20 dBm) and freeze frame inspection.
2. Binary PCAP packet capture stream with one-click export for Wireshark analysis with DLT_USER0 (LinkType 147) and Envelope v3 dissection.
3. Tactical RF Link Budget HUD computing Friis Free Space Path Loss (FSPL), antenna gains, received signal strength (Prx), and color-coded link margin health.

## Decisions

### WebGL / Canvas Spectrum Waterfall (FLD-01)
- D-01: HTML5 2D Canvas with direct `ImageData` byte buffer manipulation to guarantee 60 FPS without WebGL shader driver compatibility issues on Apple Silicon.
- D-02: Tactical Inferno / Viridis heat map gradient with dynamic dB range sliders (-120 dBm noise floor to -20 dBm peak).
- D-03: Dual-source feed supporting live `/api/v1/stream/spectrum` streaming API when backend is running, plus synthetic IQ burst generator when in offline demo mode.
- D-04: Interactive inspection controls including freeze frame, time-frequency scrub cursor, and peak power indicator line overlay.

### PCAP Frame Capture & Wireshark Export (FLD-02)
- D-05: Standard libpcap 2.4 format with `DLT_USER0` (LinkType 147) and microsecond timestamp resolution for out-of-the-box Wireshark opening.
- D-06: Dissected Envelope v3 tactical frames containing magic header (0x53484457), Sender/Receiver IDs, PQC ML-KEM-768 ciphertext, AES-256-GCM auth tag, Reed-Solomon parity, and RF RSSI/SNR metadata.
- D-07: In-memory circular ring buffer of last 500 frames with a 1-click "Export Wireshark (.pcap)" button in the Diagnostics drawer and Station Console.
- D-08: File naming convention `astra_tactical_{station}_{YYYYMMDD_HHMMSS}.pcap` with automated SHA-256 integrity seal toast notification.

### Tactical RF Link Budget HUD (FLD-03)
- D-09: Friis Free Space Path Loss (FSPL) + Two-Ray Ground Reflection propagation physics: FSPL(dB) = 20 log10(d) + 20 log10(f) + 32.44 with TX/RX antenna gains and thermal noise floor (-114 dBm at 1 MHz BW).
- D-10: One-click tactical band selector presets: VHF (144 MHz, 50W), UHF (433 MHz, 5W DMR), ISM (915 MHz, 1W LoRa/Mesh), L-Band (1.4 GHz, 2W airborne downlink).
- D-11: Floating glassmorphic HUD badge directly integrated on the 3D Link Topology + dedicated detailed math inspector card in Research Lab.
- D-12: Color-coded operational link margin rating: Green (>15 dB margin, Optimal), Yellow (6-15 dB, Marginal), Red (<6 dB, Fade Threat triggering auto-reroute).

## Specific Requirements & Patterns
- Fast memory allocation: Pre-allocated circular typed arrays (`Uint8ClampedArray`) for the waterfall canvas to prevent GC pressure.
- Wireshark dissector compatibility: Include simple Lua dissector script (`astra_dissector.lua`) in `docs/` or alongside the `.pcap` export for evaluators to paste into Wireshark if desired.
- Component integration: Mount Waterfall in `frontend/src/components/research/LiveSignalAnalyser.tsx` and `WaveformLabView.tsx`.
- PCAP endpoint: Add `/api/v1/diagnostics/pcap` in `messaging/api.py`.
- Link Budget component: Create `frontend/src/components/topology/LinkBudgetHUD.tsx`.

---
phase: "06"
slug: "multi-database-physical-isolation-dedicated-daemon-endpoints"
status: approved
shadcn_initialized: false
preset: none
created: "2026-10-20"
---

# Phase 06 — UI Design Contract

> Visual, component, and interaction design contract for Phase 06: Multi-Database Physical Isolation & Dedicated Daemon Endpoints.

---

## Design System

| Property | Value |
|---|---|
| Tool | none |
| Preset | not applicable |
| Component library | custom React 19 + Tailwind CSS v4 |
| Icon library | `lucide-react@^1.57.0` |
| Font | JetBrains Mono / Inter system fallback |
| 3D Visualization | Three.js / React Three Fiber (`LinkTopologyView`) |

---

## Component Inventory

| Component | File Path | Phase 6 Enhancement |
|---|---|---|
| `api.ts` | `frontend/src/services/api.ts` | Multi-endpoint client architecture supporting `alphaApi` (`http://localhost:5051/api/v1`) and `bravoApi` (`http://localhost:5052/api/v1`) with independent health ping and failover handling |
| `Header` | `frontend/src/components/Header.tsx` | Dedicated dual-daemon status HUD: `[● ALPHA :5051 • alpha.db]` (cyan) and `[● BRAVO :5052 • bravo.db]` (emerald), with red pulsing alert if either station drops offline |
| `StationConsoleColumn` | `frontend/src/components/StationConsoleColumn.tsx` | Station-specific daemon binding, physical DB identifier badge (`STORAGE: alpha.db (WAL)`), live connection pill, and air-gap composer lockout when station is offline |
| `MessagesView` | `frontend/src/components/MessagesView.tsx` | Decoupled dual-daemon polling loops (1.5s active / 5.0s background); failure of Bravo daemon does not disrupt Alpha's queue or UI responsiveness |
| `DiagnosticsView` | `frontend/src/components/DiagnosticsView.tsx` | Multi-database physical storage panel displaying file paths, byte sizes, WAL journal mode status, and independent connection pool metrics for `alpha.db` and `bravo.db` |

---

## Spacing & 3D Depth Scale

| Token | Value | Usage |
|---|---|---|
| xs | 4px | Inline telemetry chips, connection indicator dots |
| sm | 8px | Station pill padding, port badges |
| md | 16px | Card padding, station column header gap |
| lg | 24px | Station column container padding |
| xl | 32px | Viewport split-screen grid separation |

### 3D Tactical Elevation Levels:
- **Level 1 (Base Viewport):** `#0B0F17` (Deep tactical void)
- **Level 2 (Station Column):** `#111827` with `border border-zinc-800 shadow-[0_4px_24px_rgba(0,0,0,0.6)]`
- **Level 3 (Station Alpha Active):** `#131B2E` with `border border-cyan-500/40 shadow-[0_4px_24px_rgba(6,182,212,0.15)]`
- **Level 4 (Station Bravo Active):** `#122020` with `border border-emerald-500/40 shadow-[0_4px_24px_rgba(16,185,129,0.15)]`
- **Level 5 (Daemon Offline Warning):** `#1C1318` with `border border-rose-500/60 shadow-[0_4px_24px_rgba(239,68,68,0.25)] animate-pulse`

---

## Color & Visual Coding

- **Station Alpha Daemon (Port 5051):** Cyan (`#06B6D4`, `text-cyan-400`, `border-cyan-500/40`)
- **Station Bravo Daemon (Port 5052):** Emerald (`#10B981`, `text-emerald-400`, `border-emerald-500/40`)
- **Physical SQLite WAL Storage:** Slate/Zinc (`bg-zinc-800 text-zinc-300 font-mono text-xs`)
- **Peer Link Health Status:**
  - `CONNECTED` (green dot, latency display `12ms`)
  - `STANDBY / LOCAL ONLY` (amber dot)
  - `DAEMON OFFLINE / AIR-GAP` (rose red dot with pulsing ring)

---

## Interaction Contract

1. **Decoupled Failure States:** If the user terminates Station Bravo (`kill -9 PID`), Station Alpha's column remains completely interactive, displaying `ALPHA :5051 [ONLINE]`, while Station Bravo's column transitions to `BRAVO :5052 [DAEMON DISCONNECTED]`.
2. **Offline Outbox Routing:** Composing a message on Alpha addressed to offline Bravo queues the message into `alpha.db` with status `FAILED_RETRYABLE (TRANSPORT_OFFLINE)`.
3. **Automatic Reconnection:** Upon restarting Bravo, Alpha's worker automatically detects the peer route on next retry and delivers the pending message, updating Bravo's inbox and Alpha's verified receipt.

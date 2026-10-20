---
phase: "03"
slug: "fault-injection-offline-outages-client-re-sync"
status: approved
shadcn_initialized: false
preset: none
created: "2026-10-19"
---

# Phase 03 — UI Design Contract

> Visual, component, and interaction design contract for Phase 03: Fault Injection, Offline Outages & Client Re-Sync.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none |
| Preset | not applicable |
| Component library | custom React 19 + Tailwind CSS v4 |
| Icon library | `lucide-react@^1.57.0` |
| Font | JetBrains Mono / Inter system fallback |
| Audio System | Web Audio API Synthesized Audio (radio squelch noise burst & restore chime) |

---

## Component Inventory

| Component | File Path | Phase 3 Enhancement |
|-----------|-----------|---------------------|
| `ConnectivityView` | `frontend/src/components/ConnectivityView.tsx` | Tactical presets, single-shot armed fault buttons, worker crash/reclaim triggers, backoff profile toggle, global restore link button |
| `Header` | `frontend/src/components/Header.tsx` | Channel degradation indicator pill, outbox queue counter badge (`📦 N LOCAL QUEUED`), tactical audio toggle |
| `MessagesView` | `frontend/src/components/MessagesView.tsx` | Station banner degradation status, local IndexedDB outbox syncing, Web Locks sync coordination, dedup toast & card highlight |
| `StationConsoleColumn` | `frontend/src/components/StationConsoleColumn.tsx` | Distinct 3D Local Outbox cards with amber pulsing border, air-gap composer button adaptation, double-click lockout spinner, retry HUD badge |
| `MessageTelemetryDrawer` | `frontend/src/components/MessageTelemetryDrawer.tsx` | Dedicated `IDEMPOTENCY SEAL` chip, illuminated `WORKER LEASE RECLAIMED` timeline node, and active retry countdown HUD |
| `audioService` | `frontend/src/services/audioService.ts` | Synthesized tactical Web Audio radio squelch (~60ms) and clean link chime with user-interaction unlock |

---

## Spacing & 3D Depth Scale

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | Inline telemetry chips, icon gaps |
| sm | 8px | Button padding, badge gaps, countdown pills |
| md | 16px | Card padding, preset grid separation |
| lg | 24px | Section and column padding |
| xl | 32px | Viewport grid gaps |

### 3D Tactical Elevation Levels:
- **Level 1 (Base Canvas):** `#0B0F17` (Deep tactical void)
- **Level 2 (Standard Card):** `#131B2E` with `border border-zinc-800 shadow-[0_4px_20px_rgba(0,0,0,0.5)]`
- **Level 3 (Local Outbox / Impaired Card):** `#18181B` with `border border-amber-500/50 shadow-[0_4px_24px_rgba(245,158,11,0.2)] animate-pulse-slow`
- **Level 4 (Permanent Failure Card):** `#1C1917` with `border border-rose-500/60 shadow-[0_4px_24px_rgba(239,68,68,0.25)]`
- **Level 5 (Elevated Drawer / Overlays):** `#0B0F17/95` backdrop blur with `shadow-[-12px_0_35px_rgba(0,0,0,0.85)]`

---

## Typography

| Role | Size | Weight | Line Height |
|------|------|--------|-------------|
| Body | 14px | 400 | 1.5 |
| Label / Badge | 11px / 12px | 600 | 1.3 |
| Heading | 16px / 18px | 600 | 1.25 |
| Monospace Telemetry | 10px / 11px / 12px | 500 / 600 | 1.4 |

---

## Color & Visual Coding

| State / Meaning | Hex / Tailwind | Visual Semantics |
|-----------------|----------------|------------------|
| Nominal / Verified | `#10B981` (Emerald) | Verified ACK seals, online transport, clean link status |
| Degraded / Latency | `#F59E0B` (Amber) | Link impaired, packet loss, local outbox pending sync |
| Severed / Offline | `#EF4444` (Red / Rose) | Link severed, worker lease expired, permanent failure |
| Client Deduplicated | `#06B6D4` (Cyan) | Idempotent duplicate match, client idempotency seal |
| Tactical Neutral | `#71717A` (Zinc 500) | Timestamps, inactive steps, RF budget hints |

---

## Copywriting Contract

| Element | Copy |
|---------|------|
| Online Transmit CTA | `"Transmit Packet"` |
| Air-Gap Transmit CTA | `"Store Locally (Offline Outbox)"` |
| Link Impairment Pill (Impaired) | `"CHANNEL IMPAIRED [X% LOSS]"` |
| Link Impairment Pill (Severed) | `"LINK SEVERED / AIR-GAP"` |
| Link Restore Action | `"Restore Clean Link"` |
| Local Outbox Card Badge | `"LOCAL STORED (INDEXEDDB)"` |
| Local Outbox State Pill | `"PENDING SYNC"` |
| Header Outbox Counter | `"📦 N LOCAL QUEUED"` |
| Manual Outbox Flush CTA | `"Flush Local Outbox Now"` |
| Deduplication Toast | `"Deduplicated: Existing message record returned"` |
| Drawer Idempotency Seal | `"IDEMPOTENCY SEAL"` / `"DEDUPLICATION SAFE"` |
| Reclaimed Lease Timeline Node | `"WORKER LEASE RECLAIMED"` |
| Retry Telemetry HUD Badge | `"Attempt N/5 • Next in X.Xs [Backoff + Jitter]"` |
| Permanent Failure Badge | `"Retry Limit Exhausted [5/5]"` |
| Permanent Failure Override | `"Force Re-Queue Transmission"` |

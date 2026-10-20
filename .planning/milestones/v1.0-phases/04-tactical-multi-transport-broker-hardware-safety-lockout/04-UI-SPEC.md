---
phase: "04"
slug: "tactical-multi-transport-broker-hardware-safety-lockout"
status: approved
shadcn_initialized: false
preset: none
created: "2026-10-19"
---

# Phase 04 — UI Design Contract

> Visual, component, and interaction design contract for Phase 04: Tactical Multi-Transport Broker & Hardware Safety Lockout.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none |
| Preset | not applicable |
| Component library | custom React 19 + Tailwind CSS v4 |
| Icon library | `lucide-react@^1.57.0` |
| Font | JetBrains Mono / Inter system fallback |
| 3D Visualization | Three.js / React Three Fiber (`LinkTopologyView`) |

---

## Component Inventory

| Component | File Path | Phase 4 Enhancement |
|-----------|-----------|---------------------|
| `DevicesView` | `frontend/src/components/DevicesView.tsx` | Active transport selector with Auto-Failover toggle, Tactical Relay Nodes Telemetry panel (battery gauges, temperature, queue depth), and interactive STAR-V Lockout Dossier trigger |
| `StarVLockoutDossierModal` | `frontend/src/components/StarVLockoutDossierModal.tsx` | Slide-over/modal with red hazard theme, 4 ICD prerequisites checklist, and live test bench buttons (`Test Soft Refusal` & `Test Hard Command Lockout`) |
| `LinkTopologyView` | `frontend/src/components/topology/LinkTopologyView.tsx` | 3D visual relay node markers, path lines between stations and intermediate relays, and battery failsafe cutoff indicators |
| `StationConsoleColumn` | `frontend/src/components/StationConsoleColumn.tsx` | Quick composer live DMR burst counter HUD (`[DMR Bursts: N chunks • XXX B wire budget]`) when Motorola is active |
| `MessageTelemetryDrawer` | `frontend/src/components/MessageTelemetryDrawer.tsx` | Illuminated crimson STAR-V Lockout Blocked seal (`STARV_SAFETY_LOCKOUT_BLOCKED`) and DMR multi-chunk transmission breakdown details |

---

## Spacing & 3D Depth Scale

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | Inline telemetry chips, icon gaps |
| sm | 8px | Button padding, badge gaps, countdown pills |
| md | 16px | Card padding, relay grid separation |
| lg | 24px | Section and column padding |
| xl | 32px | Viewport grid gaps |

### 3D Tactical Elevation Levels:
- **Level 1 (Base Canvas):** `#0B0F17` (Deep tactical void)
- **Level 2 (Standard Card):** `#131B2E` with `border border-zinc-800 shadow-[0_4px_20px_rgba(0,0,0,0.5)]`
- **Level 3 (Relay Node Card):** `#151D2A` with `border border-zinc-700/80 shadow-[0_4px_24px_rgba(6,182,212,0.15)]`
- **Level 4 (STAR-V Lockout Danger Card):** `#1C1318` with `border border-rose-500/60 shadow-[0_4px_24px_rgba(239,68,68,0.25)]`
- **Level 5 (Elevated Modal / Drawer):** `#0B0F17/95` backdrop blur with `shadow-[-12px_0_35px_rgba(0,0,0,0.85)]`

---

## Color & Visual Coding

| State / Meaning | Hex / Tailwind | Visual Semantics |
|-----------------|----------------|------------------|
| Nominal / Verified | `#10B981` (Emerald) | Verified transports, battery > 20%, clean link status |
| Warning / Critical Battery | `#F59E0B` (Amber) | Relay battery $\le 20\%$, storage $\ge 80\%$, route failover active |
| Hazard / Safety Lockout | `#EF4444` (Red / Rose) | STAR-V safety lockout, battery $\le 5\%$, relay cutoff |
| Tactical Active Route | `#06B6D4` (Cyan) | Pinned active transport, DMR burst HUD badge |
| Radio Neutral | `#71717A` (Zinc 500) | Timestamps, inactive transports, protocol specs |

---

## Copywriting Contract

| Element | Copy |
|---------|------|
| Active Transport Pill | `"ACTIVE ROUTE: [TRANSPORT_NAME]"` |
| Auto-Failover Switch (On) | `"AUTO-FAILOVER: ENABLED"` |
| Auto-Failover Switch (Off) | `"AUTO-FAILOVER: DISABLED (STRICT PINNING)"` |
| Route Unavailable Pill | `"ROUTE_UNAVAILABLE (HOLDING IN QUEUE)"` |
| DMR Burst Counter Badge | `"DMR: N Bursts (XXX B Wire Budget)"` |
| STAR-V Card Lockout Badge | `"PERMANENT SAFETY LOCKOUT ENFORCED"` |
| STAR-V Dossier Modal Title | `"STAR-V Mk III Tactical SDR — Hardware Safety Dossier"` |
| STAR-V Lockout Soft Test CTA | `"Simulate Soft Refusal (send)"` |
| STAR-V Lockout Hard Test CTA | `"Simulate Hard Command Lockout (command_transmit)"` |
| Relay Autonomous Cutoff Badge | `"AUTONOMOUS CUTOFF: BATTERY CRITICAL (<= 5%)"` / `"STORAGE FULL (>= 98%)"` |
| Aerial Relay Isolation Badge | `"[FLIGHT SAFETY ISOLATION: ACTIVE]"` |
| Relay Forward Counter Badge | `"FORWARDED: N PACKETS"` |

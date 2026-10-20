---
phase: "07"
slug: "post-quantum-hybrid-cryptography-ml-kem-kyber-aes-256-gcm"
status: approved
shadcn_initialized: false
preset: none
created: "2026-10-20"
---

# Phase 07 — UI Design Contract

> Visual, component, and interaction design contract for Phase 07: Post-Quantum Hybrid Cryptography (ML-KEM / Kyber + AES-256-GCM).

---

## Design System

| Property | Value |
|---|---|
| Tool | none |
| Preset | not applicable |
| Component library | custom React 19 + Tailwind CSS v4 |
| Icon library | `lucide-react@^1.57.0` (ShieldCheck, ShieldAlert, Key, Lock, Cpu, RefreshCw, AlertTriangle, Radio) |
| Font | JetBrains Mono / Inter system fallback |
| Styling Theme | Tactical Dark Obsidian (`#0B0F17`) with illuminated Cyan (`#06b6d4`), Amber (`#f59e0b`), and Emerald (`#10b981`) accents |

---

## Component Inventory

| Component | File Path | Phase 7 Enhancement |
|---|---|---|
| `types/index.ts` | `frontend/src/types/index.ts` | Extended `Message` interface with `envelope_version`, `pqc_scheme`, `pqc_verified`, `pqc_downgrade_warning`; added `KeyringInfo`, `PQCKeyExchangeParams`, `RotateKeysResponse` |
| `api.ts` | `frontend/src/services/api.ts` | Added `getKeyringStatus()`, `rotateKeys()`, `zeroizeKeyring()`, and `simulateTamperTest()` methods bound to Station Alpha and Station Bravo daemons |
| `MessageTelemetryDrawer` | `frontend/src/components/MessageTelemetryDrawer.tsx` | 3D tactical COMSEC card with illuminated cyan `[PQC SECURED: ML-KEM-768 + Ephemeral X25519]` seal, encapsulation parameter grid, and amber downgrade warning box |
| `StationConsoleColumn` | `frontend/src/components/StationConsoleColumn.tsx` | Message card cyan PQC shield pill / amber downgrade alert, and composer live DMR burst counter HUD accounting for 1150B header overhead |
| `MessagesView` | `frontend/src/components/MessagesView.tsx` | Message card list rendering cyan PQC seal badge and amber classical fallback warnings across dual station feeds |
| `Header` | `frontend/src/components/Header.tsx` | Top-level illuminated cyan `[PQC READY: ML-KEM-768]` status pill showing COMSEC operational readiness |
| `DiagnosticsView` | `frontend/src/components/DiagnosticsView.tsx` | Dedicated Keyring & COMSEC Inspector card with local fingerprints, peer public keys, and interactive "Rotate Keys", "Tamper Test", and "Emergency Zeroize" buttons |

---

## Visual Design Contracts & Styling Specifications

### 1. Illuminated Cyan PQC Seal (`MessageTelemetryDrawer.tsx`)
```tsx
// Tactical 3D Card Container
<div className="rounded-xl border border-cyan-500/40 bg-gradient-to-b from-cyan-950/30 to-slate-900/60 p-4 shadow-[0_0_20px_rgba(6,182,212,0.25)] backdrop-blur-md">
  <div className="flex items-center justify-between pb-3 border-b border-cyan-500/20">
    <div className="flex items-center space-x-2">
      <ShieldCheck className="w-5 h-5 text-cyan-400 drop-shadow-[0_0_8px_rgba(6,182,212,0.8)]" />
      <span className="text-xs font-mono font-bold tracking-wider text-cyan-300">
        PQC SECURED (ML-KEM-768)
      </span>
    </div>
    <span className="px-2 py-0.5 text-[10px] font-mono rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
      ENVELOPE v3
    </span>
  </div>
  {/* Parameter Grid: KEM, Ephemeral X25519, HKDF, AES-256-GCM, AAD */}
</div>
```

### 2. Message Card Badges (`MessagesView.tsx` / `StationConsoleColumn.tsx`)
- **PQC Secured:** Compact badge `[PQC SECURED]` with cyan border `border-cyan-500/30`, background `bg-cyan-950/40`, and text `text-cyan-300`.
- **Classical v2 Fallback:** Amber caution badge `[CLASSICAL V2: NOT QUANTUM RESISTANT]` with `border-amber-500/40`, `bg-amber-950/40`, `text-amber-400`.

### 3. Live Composer DMR Burst Counter HUD (`StationConsoleColumn.tsx`)
- Formula:
  `rawBytes = new TextEncoder().encode(composerText).length`
  `envelopeBytes = rawBytes + 1150` (Envelope v3)
  `dmrChunks = Math.max(1, Math.ceil(envelopeBytes / 276))`
  `dmrWireBudget = dmrChunks * 280`
- Badge text: `[DMR: 5 Bursts (1400 B Wire Budget • PQC Hybrid Encapsulation)]` in cyan.

### 4. Header Cryptographic Readiness Pill (`Header.tsx`)
- Pill: `[PQC READY: ML-KEM-768]` in cyan lock icon with soft pulsing glow when daemon keyrings are active.

### 5. Diagnostics Keyring & COMSEC Inspector Card (`DiagnosticsView.tsx`)
- Station Local Fingerprints: ML-KEM-768 Public Key SHA-256 (64 hex characters, monospace truncated), X25519 Public Key (32 bytes hex).
- Peer Key Sync Table: Peer Station ID, Public Key Preview, Discovery Status (`REST DISCOVERED` in green).
- Operator Actions:
  - `Rotate Keypairs`: Invokes `POST /api/v1/crypto/rotate-keys` with confirmation toast.
  - `Simulate PQC Tamper Test`: Dispatches corrupted ciphertext to peer and displays result: `[TAMPER REJECTED: HTTP 422 CRYPTO_AUTHENTICATION_FAILED Verified]`.
  - `Emergency Zeroize`: Dangerous action with red border and verification modal.

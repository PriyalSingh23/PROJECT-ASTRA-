# Phase 7: Post-Quantum Hybrid Cryptography (ML-KEM / Kyber + AES-256-GCM) - Context

**Gathered:** 2026-10-20  
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 7 hardens the tactical communications platform against quantum cryptanalytic attacks by introducing a hybrid post-quantum cryptographic subsystem combining NIST FIPS 203 ML-KEM-768 (Kyber) with ephemeral X25519 key agreement to derive symmetric AES-256-GCM session keys for a new Envelope v3 format. It provides automatic public key discovery across physically isolated station endpoints, transparent DMR burst chunking, backward-compatible fallback negotiation for legacy v2 envelopes with security downgrade alerting, and illuminated cyan "PQC SECURED (ML-KEM-768)" tactical seals across the React console and message telemetry drawer.

</domain>

<decisions>
## Implementation Decisions

### 1. Station Keyring Architecture & Public Key Distribution
- **D-01:** **Dedicated Persistent Keyring on Disk.** Stations generate long-term cryptographic identity keypairs on initial startup if not present (`Final-Project/data/keys/alpha.keyring` and `Final-Project/data/keys/bravo.keyring`), containing ML-KEM-768 seed/keypair and X25519 identity keypair, with public keys mirrored in the SQLite `endpoints` table (`Endpoint.public_key_pqc`, `Endpoint.public_key_x25519`).
  — **Reversibility:** costly — Affects station boot sequences, database schema, and disk storage locations.
- **D-02:** **Automatic REST Public Key Discovery.** Stations dynamically discover and synchronize peer public keys via `GET /api/v1/endpoints/public-keys` (and health status probes), caching peer public keys in their local SQLite `endpoints` table so messages can be encrypted without manual pre-provisioning.
  — **Reversibility:** costly — Defines inter-daemon API contracts for public key publication and ingestion.
- **D-03:** **Self-Contained FIPS 203 ML-KEM-768 Engine.** Implement a clean, self-contained, pure-Python NIST FIPS 203 ML-KEM-768 module in `Final-Project/messaging/mlkem768.py` (and `messaging/crypto_pqc.py`) validated against NIST Known Answer Tests (KAT), with zero external C-compiler dependencies to guarantee 100% stability on Apple Silicon macOS without linker collisions.
  — **Reversibility:** one-way — Forms the cryptographic core engine for all subsequent post-quantum operations.
- **D-04:** **Operator Key Rotation & Zeroization API.** Expose explicit REST endpoints `POST /api/v1/crypto/rotate-keys` (generates fresh keypairs, saves to disk, updates SQLite, logs security event) and `POST /api/v1/crypto/zeroize` (emergency cryptographic purge zeroizing memory and disk keyrings), logging `PQC_KEY_ROTATED` and `PQC_KEYRING_ZEROIZED` to `SecurityAuditLog`.
  — **Reversibility:** costly — Adds security lifecycle operations and audit trail integration.

### 2. Envelope v3 Wire Overhead & Tactical Link Chunking
- **D-05:** **Strict Binary Framing for Envelope v3.** Wire format layout is:
  `[0x03 (1B version)][0x01 (1B scheme: ML-KEM-768 + Ephemeral X25519)][32B ephemeral X25519 PK][1088B ML-KEM-768 ciphertext][12B AES-GCM nonce][16B AES-GCM tag][variable ciphertext]`.
  Total encapsulation header overhead is exactly 1150 bytes, eliminating JSON base64 encoding expansion.
  — **Reversibility:** one-way — Published wire-format specification for all cross-daemon and tactical link transport.
- **D-06:** **NIST/IETF Hybrid HKDF-SHA256 Derivation.** Symmetric session key is derived as:
  $SS_{hybrid} = SS_{X25519} \parallel SS_{MLKEM}$ (64 bytes)
  $K_{session} = \text{HKDF-SHA256}(ikm=SS_{hybrid}, salt=b"\text{SHADOWCOMM-PQC-v3}", info=b"\text{ML-KEM-768/X25519/AES-256-GCM}", length=32)$.
  Ensures that breaking one algorithm (e.g. discrete logs) does not compromise confidentiality if lattice assumptions hold, and vice-versa.
  — **Reversibility:** one-way — Cryptographic key derivation standard across all SHADOWCOMM nodes.
- **D-07:** **Full Per-Message Ephemeral Encapsulation & Transparent DMR Chunking.** Every message is independently encrypted with a fresh ephemeral X25519 keypair and fresh ML-KEM encapsulation for forward secrecy. Over DMR links with 280-byte burst ceilings, the ~1250-byte envelope is transparently fragmented into ~5 bursts by the existing chunker (`<HH>` framing), with StationConsoleColumn displaying `[DMR: 5 Bursts (1400 B Wire Budget • PQC Hybrid Encapsulation)]`.
  — **Reversibility:** reversible — Leverages existing Phase 4 transparent frame fragmentation and UI burst HUD.
- **D-08:** **Strict Anti-Replay Header Binding (AAD).** The AES-256-GCM cipher cryptographically authenticates Associated Authenticated Data (AAD):
  `AAD = version (0x03) || scheme_id (0x01) || sender_endpoint_id || recipient_endpoint_id || message_id`.
  Any tampering with routing headers or attempts to replay intercepted envelopes between different endpoints will fail GCM authentication.
  — **Reversibility:** one-way — Enforces end-to-end cryptographic integrity and anti-replay defense.

### 3. Backward Compatibility & Legacy v2 Fallback Policy
- **D-09:** **Dual-Stack Ingest Auto-Negotiation with Security Flagging.** Receiving nodes parse the first envelope byte. If `0x03`, decrypt via PQC hybrid engine and set `pqc_verified=True`. If `0x02`, decrypt via `crypto_v2` and set `pqc_downgrade_warning=True`, recording `SecurityAuditLog(action="PQC_DOWNGRADE_FALLBACK", severity="MEDIUM")` and `MessageEvent(event_type="PQC_DOWNGRADE_ACCEPTED")`.
  — **Reversibility:** costly — Inbound dispatch pipeline and database event recording.
- **D-10:** **PQC-Preferred Outbound Encryption with Graceful Fallback.** Sender defaults to Envelope v3. If recipient public key is unknown and cannot be discovered via peer discovery probe, gracefully fall back to Envelope v2 with an audit log warning `OUTBOUND_CLASSICAL_FALLBACK`.
  — **Reversibility:** reversible — Outbound dispatch policy before transport transmission.
- **D-11:** **Dedicated Cryptographic Schema Columns on Message.** Add `envelope_version` (Integer, default 3), `pqc_scheme` (String, nullable), `pqc_verified` (Boolean, default False), and `pqc_downgrade_warning` (Boolean, default False) to `messages` table in `alpha.db` and `bravo.db`.
  — **Reversibility:** costly — Requires SQLite schema updates and model synchronization.
- **D-12:** **Immediate Rejection of Tampered Envelopes with Security Incident Logging.** If cryptographic verification fails (invalid tag, bad KEM ciphertext, corrupted header), immediately abort, reject ingest with HTTP 422 `CRYPTO_AUTHENTICATION_FAILED`, and record high-severity `SecurityAuditLog(action="PQC_TAMPER_DETECTED", severity="HIGH")` and `MessageEvent(event_type="CRYPTO_TAMPER_DETECTED")`.
  — **Reversibility:** one-way — Zero tolerance for corrupted or maliciously altered ciphertexts.

### 4. UI COMSEC Drawer & Visual Cryptographic Indicators
- **D-13:** **Dual-Tier COMSEC Indicators.**
  1. Message cards in `MessagesView` / `StationConsoleColumn` display a glowing cyan pill badge `[PQC SECURED (ML-KEM-768)]` for v3 messages.
  2. `MessageTelemetryDrawer.tsx` renders a 3D tactical COMSEC card featuring:
     - Illuminated cyan seal `[PQC SECURED: ML-KEM-768 + Ephemeral X25519]` (`shadow-[0_0_15px_rgba(6,182,212,0.35)]`)
     - Ciphertext encapsulation block size: `1088 bytes`
     - Ephemeral X25519 public key (truncated hex)
     - KDF: `HKDF-SHA256 (Salt: SHADOWCOMM-PQC-v3)`
     - Symmetric Cipher: `AES-256-GCM (128-bit Tag Verified)`
  — **Reversibility:** reversible — UI styling and telemetry presentation.
- **D-14:** **Illuminated Amber Downgrade Alert.** Messages received as classical v2 display an amber warning badge `[CLASSICAL V2: NOT QUANTUM RESISTANT]` on message cards, with an alert box in `MessageTelemetryDrawer` explaining the lack of lattice-based post-quantum protection.
  — **Reversibility:** reversible — UI conditional badge styling.
- **D-15:** **Header Cryptographic Readiness Pill.** `Header.tsx` includes a top-level COMSEC indicator: `[PQC READY: ML-KEM-768]` in cyan when keyrings are loaded, shifting to amber `[COMSEC: ZEROIZED]` or red `[KEYRING UNLOADED]` if keys are missing.
  — **Reversibility:** reversible — Header HUD component extension.
- **D-16:** **Interactive COMSEC Inspector Card in DiagnosticsView.** `DiagnosticsView.tsx` features a dedicated Keyring & Cryptographic Inspector showing local station key fingerprints (ML-KEM-768 & X25519), peer public keys, and operational controls ("Rotate Keys", "Simulate Tamper Test", "Emergency Zeroize").
  — **Reversibility:** reversible — Diagnostic instrumentation panel.

### the agent's Discretion
- Module filenames: `messaging/mlkem768.py` for FIPS 203 implementation and `messaging/crypto_pqc.py` for hybrid orchestration.
- Keyring directory: `Final-Project/data/keys/` created automatically if absent.
- Key serialization: Armored base64 strings in API payloads and SQLite `endpoints` columns.
- Test bench: Unit test suite in `tests/test_pqc_crypto.py` covering NIST KAT vectors, hybrid encapsulation, tamper detection, and fallback negotiation.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Standards & Specifications
- NIST FIPS 203 — *Module-Lattice-Based Key-Encapsulation Mechanism Standard (ML-KEM)* (August 2024). Defines ML-KEM-768 parameters: $k=3, \eta_1=2, \eta_2=2, d_u=10, d_v=4$, ciphertext size 1088 bytes, public key size 1184 bytes.
- RFC 9180 — *Hybrid Public Key Encryption (HPKE)* & draft-ietf-pquip-pqc-engineers-06 for hybrid KEM derivation patterns using HKDF-SHA256.
- `.planning/REQUIREMENTS.md` § 2 — Requirements `PQC-01`, `PQC-02`, `PQC-03`.
- `.planning/ROADMAP.md` § Phase 7 — Phase goals and acceptance criteria.

### Core Implementation Files
- `Final-Project/messaging/crypto_v2.py` — Baseline AES-256-GCM authenticated encryption (Envelope v2).
- `Final-Project/messaging/dispatch.py` — Dispatch router, envelope encoding (`_encode_envelope`), and DMR 280-byte chunker (`chunk_frame`).
- `Final-Project/messaging/models.py` — `Endpoint`, `Message`, `MessageEvent`, and `SecurityAuditLog` SQLite schema.
- `Final-Project/messaging/api.py` — Ingest routes (`/endpoints/incoming`, `/messages`), endpoint key management, and security audit logging.
- `Final-Project/messaging/transport.py` — Peer HTTP transport (`transmit_peer`) and impairment pipeline.
- `Final-Project/frontend/src/components/MessageTelemetryDrawer.tsx` — Message cryptographic telemetry, audit logs, and hardware safety seals.
- `Final-Project/frontend/src/components/StationConsoleColumn.tsx` — Tactical composer, DMR burst counter HUD, and message feed.
- `Final-Project/frontend/src/components/DiagnosticsView.tsx` — Diagnostics, database storage inspection, and system telemetry.
- `Final-Project/frontend/src/components/Header.tsx` — Station status bar, connection pills, and system HUD.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `cryptography.hazmat.primitives.asymmetric.x25519`: Native X25519 key exchange in `cryptography` 44.0.2.
- `cryptography.hazmat.primitives.kdf.hkdf.HKDF`: RFC 5869 HKDF-SHA256 key derivation.
- `Crypto.Cipher.AES`: PyCryptodome AES-256-GCM cipher for fast authenticated encryption.
- `chunk_frame()` in `messaging/dispatch.py`: DMR Tier-II frame fragmentation (<HH> self-describing bursts).
- `MessageTelemetryDrawer.tsx`: Existing slide-over drawer with expandable sections, ready for COMSEC card insertion.

### Established Patterns
- Dynamic Linker Safety: `import torch` strictly before `numpy`/`scipy` across all Python entry points.
- Physical Multi-Database Isolation: `alpha.db` (5051) and `bravo.db` (5052) run as distinct daemons with local station identity checks (`IDENTITY_SPOOFING_BLOCKED`).
- SQLite WAL Concurrency: `PRAGMA busy_timeout=5000` before `PRAGMA journal_mode=WAL`.
- Security Audit Logging: Recording all high-severity security events to `SecurityAuditLog` table.

### Integration Points
- `messaging/crypto_pqc.py`: New module orchestrating ML-KEM-768 + X25519 + AES-256-GCM v3 envelopes.
- `messaging/mlkem768.py`: Self-contained FIPS 203 ML-KEM-768 key encapsulation implementation.
- `messaging/dispatch.py`: Update `_encode_envelope()` and `DispatchRouter` to encrypt with Envelope v3 before transport transmission.
- `messaging/api.py`: Update `POST /api/v1/endpoints/incoming` to decrypt v3 envelopes with fallback to v2, and expose `/endpoints/public-keys`, `/crypto/rotate-keys`, `/crypto/zeroize`, and `/crypto/test-tamper`.
- `frontend/src/services/api.ts`: API client extensions for public keys and crypto controls.
- `frontend/src/components/MessageTelemetryDrawer.tsx`: Illuminated cyan PQC seal and cryptographic parameters breakdown.
- `frontend/src/components/Header.tsx`: PQC readiness status badge.
- `frontend/src/components/DiagnosticsView.tsx`: Keyring management & COMSEC inspector.

</code_context>

<specifics>
## Specific Ideas

- **Illuminated Cyan Seal Styling:** Cyan glowing card (`border-cyan-500/40`, `bg-cyan-950/20`, text `text-cyan-400`, drop-shadow `shadow-[0_0_15px_rgba(6,182,212,0.35)]`) displaying a shield lock icon and `PQC SECURED (ML-KEM-768)`.
- **Amber Downgrade Warning:** When v2 envelope received, amber badge `[CLASSICAL V2: NOT QUANTUM RESISTANT]` (`border-amber-500/40`, `bg-amber-950/20`, `text-amber-400`) alerting operators to harvest-now-decrypt-later vulnerability.
- **Tamper Simulation Button:** A dry-run button in `DiagnosticsView` allowing operators to dispatch an intentionally corrupted PQC ciphertext to Station Bravo to observe real-time HTTP 422 rejection and `PQC_TAMPER_DETECTED` audit log generation.

</specifics>

<deferred>
## Deferred Ideas

- Post-Quantum State-Machine Signatures (ML-DSA / Dilithium) for digital signatures — Deferred to future milestone.
- Full Mesh Ad-Hoc Dynamic Bundle Routing across > 5 nodes (`MSH-01` to `MSH-04`) — Reserved for Phase 8.
- Advanced RF Field Tools & Live Spectrum Diagnostics (`FLD-01` to `FLD-03`) — Reserved for Phase 9.

</deferred>

---

*Phase: 07-post-quantum-hybrid-cryptography-ml-kem-kyber-aes-256-gcm*  
*Context gathered: 2026-10-20*

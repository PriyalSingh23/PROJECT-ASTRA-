# Phase 07: Post-Quantum Hybrid Cryptography (ML-KEM / Kyber + AES-256-GCM) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.  
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-20  
**Phase:** 07-post-quantum-hybrid-cryptography-ml-kem-kyber-aes-256-gcm  
**Areas discussed:** Station Keyring Architecture & Public Key Distribution, Envelope v3 Wire Overhead & Tactical Link Chunking, Backward Compatibility & Legacy v2 Fallback Policy, UI COMSEC Drawer & Visual Cryptographic Indicators  

---

## Station Keyring Architecture & Public Key Distribution

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated persistent keyring files on disk (e.g. data/keys/station.keyring) with public keys mirrored in the SQLite endpoints table | Isolated long-term key storage on disk with database lookup mirror | ✓ |
| Pure database storage | Store armored base64 private and public keys directly in the SQLite endpoints table | |
| Deterministic derivation from station secret seed in environment variables | Ephemeral runtime key derivation from single passphrase | |

| Option | Description | Selected |
|--------|-------------|----------|
| Automatic REST Public Key Discovery | Stations exchange public keys via GET /api/v1/endpoints/public-keys and cache in SQLite endpoints table | ✓ |
| Static Pre-Seeding | Public keys for known peers are pre-populated into database seeds at bootstrap | |
| Inline Self-Signed Key Announcement | First outgoing packet carries the sender's public key in an unencrypted header extension | |

| Option | Description | Selected |
|--------|-------------|----------|
| Self-contained FIPS 203 ML-KEM-768 module in messaging/mlkem768.py verified against official NIST KAT test vectors | Zero external C-compiler dependencies, 100% Apple Silicon safe | ✓ |
| Third-party package install | pip install pycrystals-kyber or pqcrypto | |
| NIST-compliant wire-compatible cryptographic simulation using SHA3/SHAKE-256 | Exact 1088-byte ciphertext framing using SHA3 primitives | |

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit Operator Rotation & Emergency Zeroization API | Expose POST /api/v1/crypto/rotate-keys and POST /api/v1/crypto/zeroize with security audit logging | ✓ |
| Fixed Key Lifecycle | Keyring generated on first boot and remains static unless manually purged from disk | |
| Automated 24-Hour Daemon Ephemeral Rollover | Daemon automatically generates fresh keypairs every 24 hours of uptime | |

**User's choice:** Dedicated disk keyring with SQLite mirror, automatic REST discovery, self-contained FIPS 203 ML-KEM module verified with NIST KAT, and explicit rotation/zeroization APIs.  
**Notes:** Avoids C-extension compiler errors on macOS `arm64`; ensures zero external dependencies.

---

## Envelope v3 Wire Overhead & Tactical Link Chunking

| Option | Description | Selected |
|--------|-------------|----------|
| Strict Binary Framing | [0x03 (1B)][SCHEME_ID (1B)][X25519_PK (32B)][MLKEM_CIPHERTEXT (1088B)][NONCE (12B)][TAG (16B)][CIPHERTEXT] | ✓ |
| JSON-Wrapped Base64 Container | Encapsulate PQC blocks inside a JSON metadata dictionary | |
| Compact TLV (Type-Length-Value) Binary Container | Tagged binary blocks allowing modular future post-quantum algorithm extensions | |

| Option | Description | Selected |
|--------|-------------|----------|
| NIST/IETF Hybrid HKDF-SHA256 | HKDF-SHA256(ikm = SS_X25519 || SS_MLKEM, salt = b'SHADOWCOMM-PQC-v3', info = b'ML-KEM-768/X25519/AES-256-GCM') | ✓ |
| XOR Blend Derivation | SHA256(SS_X25519 XOR SS_MLKEM) | |
| Cascaded Layered Encryption | Encrypt plaintext with ML-KEM session key first, then encrypt inner envelope with X25519 session key | |

| Option | Description | Selected |
|--------|-------------|----------|
| Full Per-Message Ephemeral Encapsulation | Every message carries fresh ephemeral KEM encapsulation for maximum forward secrecy; DMR chunker transparently splits into ~5 bursts with HUD telemetry | ✓ |
| Ephemeral Session Key Caching | First message encapsulates full hybrid KEM; subsequent messages to the same peer within 15 min reuse cached symmetric key | |
| Adaptive Payload Pre-Compression | Compress text payloads with zlib before PQC encryption | |

| Option | Description | Selected |
|--------|-------------|----------|
| Strict Anti-Replay Header Binding | Authenticate version, scheme ID, sender_endpoint_id, recipient_endpoint_id, and message_id as GCM Associated Data (AAD) | ✓ |
| Full Envelope Metadata Binding | Authenticate all routing metadata (including incident_id, priority, and timestamps) as GCM AAD | |
| Protocol-Only Binding | Authenticate only version byte (0x03) and scheme ID (0x01) as GCM AAD | |

**User's choice:** Strict binary framing (1150B header), HKDF-SHA256 hybrid derivation, full per-message forward secrecy with DMR chunker integration, and strict anti-replay AAD binding.  
**Notes:** Provides maximum cryptographic rigor and forward secrecy while leveraging existing Phase 4 DMR burst chunking.

---

## Backward Compatibility & Legacy v2 Fallback Policy

| Option | Description | Selected |
|--------|-------------|----------|
| Dual-Stack Auto-Negotiation with Security Flagging | Decrypt v3 as PQC-secured, auto-fallback to v2 with a security audit event and amber downgrade banner | ✓ |
| Strict Security Interlock | Reject classical v2 envelopes with PQC_DOWNGRADE_REJECTED unless station has an explicit legacy toggle enabled | |
| Peer-Specific Legacy Allowlist | Only permit v2 fallback if sender endpoint is marked is_legacy_only in the database | |

| Option | Description | Selected |
|--------|-------------|----------|
| PQC-Preferred with Graceful Fallback | Default to v3 PQC hybrid encryption; if recipient PQC key is absent after discovery probe, fallback to v2 with audit warning | ✓ |
| Strict PQC Mandate | Always send v3; if recipient public key is unknown, hold message in durable queue with ROUTE_PQC_UNAVAILABLE | |
| Operator Configurable Mode | System-wide setting in UI/API (PQC_STRICT vs PQC_OPPORTUNISTIC) defaulting to PQC_STRICT | |

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit Schema Columns on Message | Add envelope_version, pqc_scheme, pqc_verified, and pqc_downgrade_warning directly on Message model | ✓ |
| Unified JSON Metadata Field | Store all cryptographic parameters inside a crypto_metadata JSON column on Message | |
| Event Timeline Only | Keep Message schema unchanged and infer cryptographic parameters from MessageEvents in SQLite | |

| Option | Description | Selected |
|--------|-------------|----------|
| Immediate Rejection with Security Audit Logging | Reject ingest with HTTP 422 CRYPTO_AUTHENTICATION_FAILED and record high-severity SecurityAuditLog (PQC_TAMPER_DETECTED) | ✓ |
| Quarantine Ingestion | Ingest the corrupted bundle into the database in a locked QUARANTINED state with an illuminated crimson tamper seal | |
| Silent RF Drop | Discard packet silently without acknowledgement to simulate military RF COMSEC sanitization | |

**User's choice:** Dual-stack auto-negotiation, PQC-preferred outbound, explicit SQLite schema columns, and immediate HTTP 422 rejection for tampered envelopes with high-severity audit logging.  
**Notes:** Fulfills requirement PQC-02 for backward-compatible fallback while guaranteeing tamper defense.

---

## UI COMSEC Drawer & Visual Cryptographic Indicators

| Option | Description | Selected |
|--------|-------------|----------|
| Dual-Tier COMSEC Presentation | Compact illuminated cyan badge on message cards + rich 3D tactical COMSEC card with encapsulation breakdown in MessageTelemetryDrawer | ✓ |
| Telemetry Drawer Only | Keep message list compact; render full PQC seal and KEM parameters exclusively inside the side drawer | |
| Modal Cryptographic Inspector | Clicking the PQC badge opens an interactive inspector modal with raw hex dump of KEM ciphertext and ephemeral keys | |

| Option | Description | Selected |
|--------|-------------|----------|
| Illuminated Amber Downgrade Alert | Display amber [CLASSICAL V2: NOT QUANTUM RESISTANT] badge on message card and detailed downgrade explanation in drawer | ✓ |
| Crimson Security Hazard Banner | High-visibility red alert [SECURITY DOWNGRADE: CLASSICAL GCM] warning operators of potential harvest-now-decrypt-later risk | |
| Neutral Monochrome Tag | Subtle gray [LEGACY V2] pill keeping the interface visual noise low | |

| Option | Description | Selected |
|--------|-------------|----------|
| Header Cryptographic Readiness Pill | Dedicated illuminated cyan [PQC READY: ML-KEM-768] status indicator in Header.tsx showing real-time COMSEC readiness | ✓ |
| Integrated Station Badge | Append a small key icon with 'PQC' tag to existing station connection chips in Header.tsx | |
| Dedicated Diagnostics View Card | Confine COMSEC readiness details to DiagnosticsView and keep the top header focused on connection and storage | |

| Option | Description | Selected |
|--------|-------------|----------|
| Interactive COMSEC Inspector Card in DiagnosticsView | Display key fingerprints, known peer keys, and operational controls (Rotate Keys, Simulate Tamper Test, Emergency Zeroize) | ✓ |
| Read-Only Keyring Telemetry | Display station public key fingerprints and active scheme details without mutation controls | |
| Header-Triggered COMSEC Modal | Clicking the Header PQC pill opens an interactive tactical key management dialog | |

**User's choice:** Dual-tier visual seals (message cards and drawer), illuminated amber downgrade alerts, header COMSEC readiness pill, and interactive DiagnosticsView COMSEC inspector card.  
**Notes:** Fulfills requirement PQC-03 with rich 3D depth and operator-accessible controls.

---

## the agent's Discretion

- Self-contained pure-Python implementation in `messaging/mlkem768.py` ensuring zero external C-dependencies.
- Keyring directory: `Final-Project/data/keys/` created automatically on startup.
- Key serialization: Armored base64 strings in API payloads and SQLite `endpoints` columns.
- Test bench: Unit test suite in `tests/test_pqc_crypto.py` covering NIST KAT vectors, hybrid encapsulation, tamper detection, and fallback negotiation.

## Deferred Ideas

- Post-Quantum State-Machine Signatures (ML-DSA / Dilithium) for digital signatures — Deferred to future milestone.
- Full Mesh Ad-Hoc Dynamic Bundle Routing across > 5 nodes (`MSH-01` to `MSH-04`) — Reserved for Phase 8.
- Advanced RF Field Tools & Live Spectrum Diagnostics (`FLD-01` to `FLD-03`) — Reserved for Phase 9.

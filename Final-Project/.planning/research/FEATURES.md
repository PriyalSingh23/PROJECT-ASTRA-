# Features Research: Tactical Communications & LPI Platform

**Domain:** Tactical Store-and-Forward Messaging & Neural Spread-Spectrum Physical Layer  
**Researched:** 2026-10-16  
**Confidence:** HIGH  

---

## 1. Feature Landscape

### Table Stakes (Users Expect These)

| Feature | Why Expected | Complexity | Implementation Notes |
|---|---|:---:|---|
| **Persistent Outbox & Inbox** | Operational messages must survive process crashes, link drops, and station power cycles. | MEDIUM | SQLite WAL tables (`messages`, `inbox`) with foreign key constraints and transactional integrity. |
| **Atomic Worker Leasing** | Prevents race conditions and duplicate transmissions across concurrent threads or restarted processes. | MEDIUM | SQL `UPDATE messages SET status='IN_TRANSIT', worker_lease_id=... WHERE status='QUEUED'`. |
| **Idempotency Deduplication** | Unstable links cause repeated submissions; duplicate payloads must be rejected immediately. | LOW | `client_idempotency_key` unique indexing in `messages` table. |
| **Durable Signed ACKs** | Senders must receive verifiable proof of delivery, not speculative optimistic status updates. | MEDIUM | Recipient creates cryptographic receipt in `acknowledgements` table, returning signed ACK. |
| **Exponential Retry Backoff** | Intermittent links require structured retry spacing to avoid flooding congested channels. | LOW | Configurable retry policy with exponential backoff and jitter (`retry_policy.py`). |
| **Dual-Station Side-by-Side Console** | Operator needs immediate visibility into both Alpha (sender) and Bravo (recipient) status on one screen. | MEDIUM | React 19 two-column layout showing real-time outbox/inbox and link impairment controls. |

### Differentiators (Competitive Advantage)

| Feature | Value Proposition | Complexity | Implementation Notes |
|---|---|:---:|---|
| **Isolated Dual-DB Architecture** | Proves endpoints cannot cheat via shared memory or shared tables in simulated verification. | HIGH | Independent SQLite files (`alpha.db` and `bravo.db`) communicating solely over HTTP / transport. |
| **AES-256-GCM v2 Envelope** | Fresh 96-bit nonces per packet prevent keystream reuse attacks and guarantee payload authenticity. | MEDIUM | Versioned header `0x02` + 12-byte nonce + ciphertext + 16-byte MAC tag (`crypto_v2.py`). |
| **Neural LPI Spread-Spectrum** | Modulates payload into covert, noise-like baseband waveforms using learned generative codebooks. | HIGH | PyTorch `LPIGenerator` + `LPIDecoder` with Zadoff-Chu preambles and RS(42,34) FEC. |
| **8-Domain EW Statistics** | Empirical verification of covertness against electronic warfare detectors (KS Gaussianity, kurtosis). | HIGH | Automated battery in `lpi_stats.py` calculating detection evasion margins. |
| **Tactical Safety Lockouts** | Prevents unverified software from triggering physical RF emissions on unauthorized radios. | LOW | Hardcoded `LOCKED_OUT` state on STAR-V adapter until vendor ICD verification. |
| **Browser IndexedDB Outbox** | Preserves drafts in client browser storage when network connection to backend server drops. | MEDIUM | Client `shadowcomm_outbox_db` with automatic re-sync upon HTTP connection restoration. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Better Approach |
|---|---|---|---|
| **Fabricated RF Receipts** | Creates a flashy demo showing simulated transmissions as physical over-the-air links. | Fraudulent and scientifically invalid; masks real physical channel impairments. | Strict capability declaration: clearly label simulated vs physical USRP RF links. |
| **Live STAR-V RF Transmission** | Tactical radio integration looks impressive in presentations. | Violates frequency regulations and risks equipment damage without vendor ICD. | Permanent software safety lockout (`LOCKED_OUT`) until ICD is officially verified. |
| **Shared In-Memory State in Tests** | Simpler to write tests where Alpha and Bravo share single database session. | Mask concurrency bugs, false ACK receipts, and cache leakage. | Isolated SQLite databases communicating strictly over HTTP endpoints and transport links. |
| **Marketing Invisibility Claims** | Sounds compelling to claim "undetectable" communications. | Physically impossible; all RF emissions are detectable given sufficient radiometric SNR. | Present empirical BER vs SNR sweeps and EW KS-test statistics objectively. |

---

## 2. Feature Dependencies

```
[Isolated Dual-DB Architecture]
    └──requires──> [Persistent SQLite WAL Engine]
                       └──requires──> [Deterministic State Machine]

[Dual-Station Side-by-Side Console]
    └──requires──> [REST API /api/v1/messages]
                       └──requires──> [Atomic Worker Leasing]

[AES-256-GCM v2 Envelope]
    └──enhances──> [LPI-CGAN Neural Transceiver]
                       └──enhances──> [Durable Signed ACKs]

[STAR-V Safety Lockout] ──conflicts──> [Live RF Transmission]
```

---

*Refreshed: 2026-10-16*

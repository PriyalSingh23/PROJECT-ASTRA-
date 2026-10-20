# Stack Research: Tactical Communications & LPI Platform

**Domain:** Tactical Store-and-Forward Messaging & Neural Spread-Spectrum Physical Layer  
**Researched:** 2026-10-16  
**Confidence:** HIGH (Derived from verified brownfield repository and 55 passing tests)  

---

## 1. Core Technology Stack Recommendations

### Backend & API Service
- **Flask 3.x:** Lightweight, deterministic WSGI REST framework. Ideal for embedded and edge radio controllers where FastAPI's heavy async event loops can introduce thread-safety edge cases with synchronous C/C++ SDR drivers (UHD).
- **SQLAlchemy 2.0 (ORM):** Provides type-safe schema mapping, connection pooling, and atomic conditional updates (`UPDATE ... WHERE status = 'QUEUED'`) essential for distributed worker leasing.
- **SQLite 3 with WAL Mode:** 
  - Essential pragmas: `PRAGMA journal_mode=WAL;`, `PRAGMA synchronous=NORMAL;`, `PRAGMA busy_timeout=5000;`.
  - Enables concurrent multi-threaded reads while worker process executes atomic lease transactions.

### Frontend Tactical Console
- **React 19.2.8 + TypeScript 6.0:** High-throughput reactive rendering for real-time status updates and dual-station telemetry.
- **Vite 8.3.4:** Sub-second HMR and deterministic production bundling (`dist/` directory served directly by Flask).
- **Tailwind CSS v4.3.3:** Utility-first styling with zero runtime CSS-in-JS overhead; dark tactical theme tailored for field visibility.
- **IndexedDB (`idb` wrapper):** Durable client-side offline outbox buffering (`shadowcomm_outbox_db`) ensuring messages drafted during UI severance persist across browser reloads.
- **Recharts 2.x:** Canvas/SVG charting for 75-epoch training loss curves, BER vs SNR sweeps, and baseband IQ constellations.

### Security & Cryptography
- **PyCryptodome (AES-256-GCM v2):** Authenticated encryption with fresh 96-bit cryptographically secure nonces (`os.urandom(12)`) and 128-bit authentication tags.
- **PBKDF2-HMAC-SHA256:** Password hashing with 100,000 iterations and 16-byte random salt.
- **reedsolo (Reed-Solomon RS(42,34)):** Forward error correction for tactical radio frames, correcting up to 4 symbol errors per 42-symbol block.

### Digital Signal Processing & Physical Layer
- **PyTorch 2.2+:** Dynamic neural network graph execution (`LPIGenerator`, `LPIDecoder`) with Apple Metal (MPS) acceleration and CPU fallback.
- **NumPy 1.24+ & SciPy 1.10+:** Complex IQ array manipulation, Zadoff-Chu sequence generation, Kolmogorov-Smirnov Gaussianity tests, and kurtosis calculations.
- **Ettus UHD Driver:** Hardware abstraction layer for USRP B200/B210 software-defined radios.

---

## 2. What NOT to Use (and Why)

| Technology | Why Avoided | Recommended Alternative |
|---|---|---|
| **Fixed-Counter AES-CTR** | Reusing a static counter across multiple packets results in the two-time pad vulnerability, exposing plaintext payloads to passive interceptors. | Versioned `AES-256-GCM` with fresh 96-bit nonce per packet (`messaging/crypto_v2.py`). |
| **Port 5000 / Port 5001** | Port 5000 is claimed by macOS Monterey+ AirPlay Receiver; Port 5001 hosts legacy unmaintained prototypes. | Canonical port **5050** for all backend API and frontend distribution. |
| **Heavy Distributed Message Brokers (RabbitMQ / Kafka)** | Tactical edge and field deployments lack cluster infrastructure, ZooKeeper/etcd nodes, and reliable high-speed links. | Local persistent SQLite WAL database with store-and-forward worker leasing. |
| **Unauthenticated Plaintext Radio Frames** | Raw frames are vulnerable to spoofing, replay attacks, and man-in-the-middle tampering in contested RF environments. | CRC-8 integrity checksum + authenticated cryptographic envelope with signed ACK receipts. |

---

*Refreshed: 2026-10-16*

# Technology Stack

**Analysis Date:** 2026-10-16  
**System:** SHADOWCOMM — Reliable Communications & Research Platform  
**Repository:** `https://github.com/PriyalSingh23/Final-Project`  

---

## 1. Languages

**Primary:**
- **Python 3.11 / 3.12** — Core backend services, machine learning models, digital signal processing, cryptographic framing, and test harnesses (`messaging/`, `lpi_v4/`, `integration/`, `tests/`)
- **TypeScript 6.0 / JavaScript (ES2022)** — Modern web application frontend (`frontend/src/`)

**Secondary:**
- **GNU Radio Flowgraphs (GRC / XML / Python)** — Software Defined Radio flowgraphs for RF transmit and receive chains (`rx_lpi_cgan.grc`, `TESTbench.grc`, `lpi_v4/tx_lpi_v4.grc`, `lpi_v4/rx_lpi_v4.grc`)
- **Bash / Shell (`.sh`)** — Automated setup, development server lifecycle management, and graceful shutdown on macOS (`scripts/setup_macos.sh`, `scripts/dev.sh`, `scripts/stop_dev.sh`)

---

## 2. Runtime & Execution Environment

**Environment:**
- **CPython 3.12.9** on macOS (Darwin / Apple Silicon `arm64`), utilizing Apple Metal Performance Shaders (`torch.backends.mps.is_available() == True`) with CPU fallback.
- **Node.js v24.22.0 & npm 11.19.1** for building and serving the React 19 web interface (`frontend/`).

**Package Managers & Lockfiles:**
- Python: `pip` (`requirements.txt`), Radioconda / Conda environment for GNU Radio and UHD bindings.
- Node.js: `npm` with deterministic `package-lock.json` (`frontend/package-lock.json`).

---

## 3. Frameworks & Libraries

**Frontend (`frontend/`):**
- **React 19.2.8** — Component-driven reactive UI architecture.
- **Vite 8.3.4** — Fast frontend build tool and development server.
- **Tailwind CSS v4.3.3** (`@tailwindcss/vite`) — Utility-first typography, restrained palette, and responsive styling.
- **Lucide React 1.57.0** — Accessible tactical icon system.
- **Recharts 2.x** — Interactive charting library for 75-epoch training curves, BER vs SNR sweeps, PSD spectra, and baseband IQ constellations.
- **IndexedDB (`idb` wrapper)** — Client-side persistent offline outbox (`frontend/src/services/outboxDb.ts`).

**Backend (`messaging/`):**
- **Flask 3.x** — REST API backend (`messaging/api.py`), serving versioned `/api/v1` routes and pre-compiled React static assets (`messaging/server.py`).
- **SQLAlchemy 2.0 (ORM)** — Declarative database persistence, atomic conditional leasing, and connection pool management (`messaging/models.py`, `messaging/db.py`).
- **SQLite 3 with WAL Mode** — Durable local ACID transactions, 5000ms busy timeout, and foreign key cascades.

**Machine Learning & Digital Signal Processing (`lpi_v4/`):**
- **PyTorch (torch >= 2.2.0)** — Deep learning models (`LPIGenerator`, `LPIDecoder`, `Warden`), custom loss functions, matrix operations, and differentiable signal processing (`lpi_v4/lpi_core.py`, `lpi_v4/lpi_train.py`).
- **NumPy (>= 1.24.0)** — Complex IQ baseband representation, Zadoff-Chu preambles, and cross-correlation arrays.
- **SciPy (>= 1.10.0)** — Kolmogorov-Smirnov Gaussianity tests, kurtosis calculations, and frequency domain filtering (`lpi_v4/lpi_stats.py`).

**Security & Cryptography:**
- **PyCryptodome** — Versioned `AES-256-GCM` authenticated encryption with fresh 96-bit random nonces (`messaging/crypto_v2.py`) and PBKDF2-HMAC-SHA256 password hashing with 100,000 iterations (`messaging/auth_service.py`).
- **Reed-Solomon (`reedsolo`)** — Forward error correction ($RS(42,34)$ in Gen 2 v4, $RS(255,223)$ in Gen 1).

**Testing:**
- **pytest (>= 7.4.0)** — Comprehensive 55-test suite covering unit tests, deterministic 1,050-message outage simulations, and PyTorch research validation (`tests/`).

---

## 4. Key Dependencies

| Package | Version | Layer | Role / Purpose |
|---|---|---|---|
| `torch` | $\ge 2.2.0$ | Core ML | Neural generator & decoder, MPS hardware acceleration |
| `sqlalchemy` | $\ge 2.0$ | Database | Message queue, lease concurrency, audit log schemas |
| `pycryptodome`| $\ge 3.20$ | Security | Versioned AES-256-GCM v2, PBKDF2 password hashing |
| `reedsolo` | $\ge 1.7$ | DSP/FEC | Reed-Solomon RS(42,34) forward error correction |
| `flask` | $\ge 3.0$ | Server | REST API routing, static frontend distribution |
| `react` | 19.2.8 | Frontend | Component rendering, state management |
| `vite` | 8.3.4 | Frontend | ESModule dev server, production bundling |
| `recharts` | $\ge 2.15$ | Frontend | Scientific charting (BER curves, training history) |
| `lucide-react`| 1.57.0 | Frontend | UI iconography |

---

## 5. Configuration & Environment Variables

| Variable | Default Value | Description |
|---|---|---|
| `SHADOWCOMM_SECRET_KEY` | *(Validated)* | Flask session secret; prevents dev fallback in production. |
| `SHADOWCOMM_AES_KEY` | *(Validated)* | Cryptographic key for authenticated message envelope. |
| `SHADOWCOMM_CORS_ORIGINS`| `127.0.0.1:5050, 5173` | Explicit whitelist of browser origins permitted for CORS. |
| `SHADOWCOMM_REQUIRE_AUTH`| `false` | When `true`, enforces token authentication on message submission. |
| `DB_PATH` | `shadowcomm_messaging.db` | Local SQLite database file location. |
| `PORT` | `5050` | Primary backend and web console listening port. |

---

## 6. Platform Requirements

**Development & Execution:**
- **macOS:** Darwin on Apple Silicon (M1/M2/M3/M4) or Intel x86_64.
- **Port Allocation:** Port 5050 (Canonical Backend & React UI), Port 5173 (Optional Vite Dev).
- **Port Collisions Avoided:** Port 5000 is reserved by macOS AirPlay Receiver; Port 5001 legacy interface has been decommissioned.
- **Hardware Acceleration:** Apple Metal (MPS) detected automatically for PyTorch inference.

---

*Stack analysis refreshed: 2026-10-16*

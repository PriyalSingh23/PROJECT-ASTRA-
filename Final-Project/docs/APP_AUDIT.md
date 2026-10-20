# SHADOWCOMM — Application & Architectural Audit

**Document Version:** 1.0.0  
**Date:** October 2026  
**Auditor:** Antigravity Engineering Pair  
**Project Path:** `/Users/sabhay/Downloads/PROJECT 13OCT/Final-Project`  
**Active Git Branch:** `main` (commit `05e959e`)  
**Git Remote:** `https://github.com/PriyalSingh23/Final-Project.git`  
**Working Tree Status:** Clean  

---

## 1. Executive Summary

This audit assesses the repository structure, server entry points, frontend implementations, research pipelines, and security configurations to prepare the codebase for a professional product rebuild as **SHADOWCOMM** ("Reliable communications and research platform").

Key findings:
1. **Frontend Root Cause**: The previous `TemplateNotFound: index.html` failure occurred because legacy `app.py` called `render_template("index.html")`, which by Flask convention searches only within a `templates/` subdirectory. In the original repository, `index.html` was situated at the repository root. Copying `index.html` into `templates/` was a temporary workaround.
2. **macOS Port Collision**: macOS Monterey and later reserve port 5000 for Apple's AirPlay Receiver (`ControlCenter`). Attempting to bind `0.0.0.0:5000` failed with `Address already in use`. The port had to be adjusted to 5001 or 5050.
3. **Dual Backend Fragment**: Two backend servers existed concurrently:
   - Legacy `app.py` (port 5001): Prototype script with hardcoded fake metrics, fake random spectrum in WebSocket, unauthenticated AES-128-CTR with static 0-counter, and dummy file outputs (`last_tx_waveform.npy`).
   - Enterprise `messaging/server.py` (port 5050): Production Flask server with SQLAlchemy WAL SQLite persistence, RBAC auth, versioned AES-256-GCM v2, background queue worker (`messaging/worker.py`), and REST API (`/api/v1`).
4. **Canonical Architecture Decision**:
   - Canonical Backend: Consolidated into a unified, modular Flask server integrating the reliable `/api/v1` messaging engine, PBKDF2/RBAC security, and a lazy-loaded `ResearchService` adapter that interfaces cleanly with `lpi_v4/`.
   - Canonical Frontend: A professional React 19 + TypeScript + Vite + Tailwind CSS application located in `frontend/`, providing a WhatsApp/Spotify-grade messaging layout, real Research Lab, and comprehensive Connectivity/Device monitoring.

---

## 2. Inventory & Entry Point Analysis

### 2.1. Server Entry Points

| File | Port | Framework | Purpose & Limitations | Recommendation |
|---|---|---|---|---|
| `app.py` | 5001 | Flask + Flask-SocketIO | Legacy prototype. Implements fake spectrum generator, hardcoded metrics, zero-counter AES-CTR, and writes files directly to disk. | Deprecate in favor of unified `server.py`. |
| `messaging/server.py` | 5050 | Flask (Blueprint `api_v1`) | Production offline messaging API, serving REST endpoints and dispatch UI. Uses SQLite WAL mode. | **Canonical backend entry point**. |
| `messaging/worker.py` | N/A | Python daemon | Background queue worker with atomic conditional lease acquisition and retry policy. | Retain as dedicated queue delivery daemon. |

### 2.2. Frontend Implementations

| Path | Tech Stack | Status | Issues / Strengths |
|---|---|---|---|
| `index.html` (root) | Plain HTML/CSS/JS | Legacy | Monolithic UI with artificial waveform canvas. Caused Flask `TemplateNotFound`. | Deprecated. |
| `templates/index.html` | Plain HTML/CSS/JS | Legacy | Untracked copy created to satisfy Flask's template loader. | Deprecated. |
| `messaging/templates/offline_messaging.html` | Plain HTML/Tailwind CDN | Operational | Functional prototype with IndexedDB outbox and 10 incident schemas, but monolithic HTML. | Reference for behavior. |
| `../SHADOWLINK-FIELD/frontend` | React 19, TS, Vite, Tailwind v4 | Scaffold | Unversioned folder outside git repo. Demonstrates modern component layout. | **Port and elevate into canonical `frontend/` within the repository**. |

---

## 3. Detailed Root Cause Analysis

### 3.1. Why Flask Failed to Find `index.html`
- In `app.py`, the application was initialized as:
  ```python
  app = Flask(__name__)
  ```
- By default in Flask, `template_folder` is initialized to `"templates"`, relative to the root module directory.
- The original repository placed `index.html` directly in `/Users/sabhay/Downloads/PROJECT 13OCT/Final-Project/index.html` without a `templates/` folder.
- When a user navigated to `http://localhost:5001/`, Flask raised `jinja2.exceptions.TemplateNotFound: index.html`.

### 3.2. Why Port 5000 Collided on macOS
- On macOS 12 (Monterey) through macOS 15+ (Sequoia), Apple binds port 5000 to the AirPlay Receiver service managed by `ControlCenter`:
  ```
  COMMAND     PID   USER   FD   TYPE             DEVICE SIZE/OFF NODE NAME
  ControlCe  4039 sabhay    8u  IPv4 0x389f6df6f9ca9d69      0t0  TCP *:commplex-main (LISTEN)
  ```
- Any web server attempting to bind `0.0.0.0:5000` receives `OSError: [Errno 48] Address already in use`.
- Resolution: Use explicit non-colliding ports: **5050** for backend REST API and **5173** for Vite development server (or serve static build from 5050 in production).

---

## 4. Scientific LPI-CGAN Research Subsystem

### 4.1. Core Physics & Implementations
- **Core Truth (`lpi_v4/lpi_core.py`)**: Defines `LPIConfig`, `LPIGenerator`, `LPIDecoder`, `Warden`, and `sync_and_correct`.
  - Spreading gain: $10 \log_{10}(8) = 9.03\text{ dB}$ (8 complex baseband samples per bit).
  - Frame length: 1,024 complex samples (128-bit frame + 160-sample keyed Zadoff-Chu pilot preamble).
  - Sample rate: $245,760\text{ samples/s}$ ($30.72\text{ kbps}$ net bit rate).
  - Error correction: Reed-Solomon $RS(42,34)$ + CRC-8 integrity checksum.
- **Model Checkpoints**:
  - `lpi_v4/run/lpi_v4.best.pt`: Evaluated at KS $p=0.865$, Kurtosis $2.991$, $0.0\%$ FER for $\text{SNR} \ge 2\text{ dB}$, 16/16 exact burst recoveries.
  - Exported TorchScript: `lpi_v4/run/lpi_v4_gen.pt` and `lpi_v4/run/lpi_v4_dec.pt` matching `export_manifest.json`.
- **GNU Radio Integration**:
  - Flowgraphs `tx_lpi_cgan.grc` and `rx_lpi_cgan.grc` regenerated via `lpi_v4/make_grc.py`.
  - USRP direct transceiver scripts: `tx_usrp.py` and `rx_usrp.py`.
- **Dynamic Linker Segfault Resolution**:
  - Fixed Apple Silicon OpenBLAS conflict (SIGSEGV 139) by enforcing `import torch` prior to `numpy` or `scipy` imports across all execution entry points.

---

## 5. Security & Authentication Audit

### 5.1. Identified Vulnerabilities & Mitigations
1. **Hardcoded Secrets in Legacy `app.py`**:
   - `_env_secret = "dev-insecure-shadowcomm-secret-key"`
   - `_env_aes_key = "0123456789abcdef"`
   - *Mitigation*: Replaced by PBKDF2 password hashing in `messaging/auth_service.py` and environment-based secret configuration via `.env.example`.
2. **Unauthenticated AES-CTR with 0-Counter**:
   - Legacy `app.py` used `Counter.new(128, initial_value=0)` without IV/nonce, resulting in keystream reuse across multiple messages.
   - *Mitigation*: Implemented versioned authenticated encryption in `messaging/crypto_v2.py` (`AES-256-GCM` with fresh 96-bit random nonces and 128-bit authentication tags).
3. **Permissive CORS**:
   - Unrestricted origins restricted to explicit whitelist (`http://127.0.0.1:5050`, `http://localhost:5050`, `http://127.0.0.1:5173`, `http://localhost:5173`).
4. **Brute-Force Lockout**:
   - 5 failed login attempts trigger a 15-minute account lockout with audit log logging.

---

## 6. Architecture & Implementation Plan for SHADOWCOMM

```
+-------------------------------------------------------------------------------+
|                             SHADOWCOMM FRONTEND                               |
|                React 19 + TypeScript + Vite + Tailwind CSS                    |
+-----------------------+-------------------------------+-----------------------+
|   MESSAGING CONSOLE   |         RESEARCH LAB          |  CONNECTIVITY/DEVICE  |
| - WhatsApp layout     | - Model Inventory & Metadata  | - Multi-tier Health   |
| - Left: Conv list     | - Empirical Eval Reports      | - Worker status       |
| - Center: History+Send| - Signal/Constellation Charts | - Radio Adapters      |
| - Right: Diagnostics  | - Controlled Run Triggers     | - Diagnostics         |
+-----------------------+-------------------------------+-----------------------+
                                    | (HTTP REST + SSE / Events)
                                    v
+-------------------------------------------------------------------------------+
|                              SHADOWCOMM BACKEND                               |
|                     Python / Flask (Port 5050) & SQLite WAL                   |
+-----------------------+-------------------------------+-----------------------+
|   MESSAGING ENGINE    |       SECURITY & AUTH         |   RESEARCH ADAPTER    |
| - Persistent Queue    | - PBKDF2 & RBAC               | - Lazy model loader   |
| - Idempotency & Dedup | - AES-256-GCM v2              | - Real lpi_v4 invoke  |
| - Delivery State Mach | - Session Lifecycles          | - Hardware detection  |
| - Receiver ACKs       | - Security Audit Log          | - macOS CPU/MPS check |
+-----------------------+-------------------------------+-----------------------+
            |                                                       |
            v                                                       v
+-----------------------+                       +-------------------------------+
|  BACKGROUND WORKER    |                       |    LPI-CGAN RESEARCH STACK    |
|  (messaging.worker)   |                       |    lpi_v4/ / checkpoints      |
+-----------------------+                       +-------------------------------+
```

---

## 7. Verification Checklist

- [x] Initial repository inspected and audit documented
- [x] Template error and port 5000 collision root causes identified
- [x] 55/55 automated tests passing cleanly
- [x] Canonical backend entry point defined (`messaging/server.py` on port 5050)
- [x] Canonical frontend defined (`frontend/` Vite React TS on port 5173)
- [x] Research assets protected and verified with empirical benchmarks

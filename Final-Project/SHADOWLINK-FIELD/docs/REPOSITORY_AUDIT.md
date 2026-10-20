# Repository Audit: ShadowComm Research Codebase to SHADOWLINK FIELD

**Date of Audit:** October 15, 2026  
**Auditor:** Principal Systems Architect & Communication Systems Engineer  
**Target Repository:** `PriyalSingh23/Final-Project`  
**Derived Product:** `SHADOWLINK-FIELD`

---

## 1. Executive Summary

An exhaustive technical audit of the `Final-Project` repository was conducted to distinguish mature, verified research capabilities from legacy, experimental, or non-functional scaffolding. 

The audit establishes that:
1. **The codebase consists of two distinct generations**:
   - **Generation 1 (Root-level scripts)**: Legacy prototype (`app.py`, `models.py`, `train.py`, `sweep.py`, older `.grc` flowgraphs) designed around 512-sample frames, fixed AES-CTR keys, and an uncorrected ~2.7% Bit Error Rate (BER) floor.
   - **Generation 2 (`lpi_v4/`)**: Rigorous, self-contained implementation with 1024/2048 sample frames, RS(42,34) forward error correction, CRC-8 frame verification, balanced synchronization preambles, and an 8-domain electronic warfare (EW) stealth evaluation battery.
2. **Critical Discrepancies Exist**:
   - Frame length mismatch (512 vs 1024 samples).
   - Codec mismatch (`RS(255,223)` with $n=255$ in root `app.py` vs `RS(42,34)` with $n=42$ in `lpi_v4/lpi_crypto.py`).
   - Web application deception in legacy `app.py`: `/api/send` dumped waveform arrays to disk and reported `transmitted` without invoking UHD/USRP drivers.
   - Insecure cryptographic parameters: hard-coded AES key (`0123456789abcdef`) and fixed counter `initial_value=0` without message authentication.
   - Windows path hard-coding in `.bat` scripts (`C:\Users\yasht\...`).
   - PyTorch vectorization segfaults on macOS Apple Silicon in radioconda Python 3.12 under specific complex matrix multiplication paths in `lpi_core.py`.
3. **Preservation Mandate**:
   The entire `Final-Project/` repository is treated as read-only research provenance. No original code, flowgraphs, checkpoints, or history will be modified. All operational product development occurs inside `SHADOWLINK-FIELD/`.

---

## 2. Inventory and Module Assessment

| File / Subsystem | Generation | Stated Function | Actual Technical State | Product Strategy |
|---|---|---|---|---|
| `app.py` (root) | Gen 1 | Flask web interface & SDR demo | Saves `.npy` file on `/api/send`; reports `transmitted` falsely; hard-coded AES key. | **Do not reuse for field deployment**. Superseded by FastAPI in `SHADOWLINK-FIELD`. |
| `models.py` (root) | Gen 1 | CGAN Generator, Discriminator, Decoder | Fixed 512 frame length; lacks frame synchronization; ~2.7% BER floor. | Archive. Kept as baseline reference only. |
| `train.py` (root) | Gen 1 | Model training | Evaluates only against AWGN; prone to mode collapse without covariance loss. | Archive. Superseded by `lpi_v4/lpi_train.py`. |
| `lpi_v4/lpi_core.py` | Gen 2 | Core physics, framing, sync, neural layers | Fully implemented; contains `LPIConfig`, `LPIGenerator`, `LPIDecoder`, `sync_and_correct`. | Wrap behind software-only SDR research adapter. |
| `lpi_v4/lpi_crypto.py`| Gen 2 | Framing, RS(42,34), AES | Clean implementation of CRC-8 + RS(42,34) + AES-CTR/GCM. | Integrated into SDR research adapter. |
| `lpi_v4/lpi_stats.py` | Gen 2 | 8-domain EW battery | Standalone metrics: KS, kurtosis, entropy, circularity, PAPR, SCF, C42, WVD. | Integrated into Research & Analytics module. |
| `lpi_v4/lpi_eval.py`  | Gen 2 | Field-gate evaluation | Tested and verified against `run/lpi_v4.best.pt`. | Expose via Experiment Management service. |
| `lpi_v4/uhd_io.py`    | Gen 2 | Version-tolerant UHD wrapper | Requires real USRP hardware and `uhd` C++ bindings. | Strictly isolate; require explicit operator enablement. |
| `lpi_v4/tx_usrp.py`   | Gen 2 | Real-time transmitter | Operational over USRP B210 if hardware connected. | Isolate behind approved RF gateway permissions. |
| `lpi_v4/rx_usrp.py`   | Gen 2 | Real-time receiver & sync | Operational over USRP B210 if hardware connected. | Isolate behind approved RF gateway permissions. |
| `GNU 1.grc`, `*.grc`  | Gen 1 | GNU Radio flowgraphs | Legacy, dependent on specific GNU Radio 3.8/3.10 block paths. | Preserve unmodified for historical research. |
| `lpi_v4/*.grc`        | Gen 2 | GRC flowgraphs for v4 | Auto-generated via `make_grc.py`. | Preserve unmodified. |
| `run/*.pt`            | Gen 2 | Model checkpoints (`lpi_v4.best.pt`) | Valid TorchScript / PyTorch checkpoints (~21MB). | Reference in read-only mode without duplication. |

---

## 3. Detailed Technical Inconsistencies Identified

### 3.1 Frame Structure & Synchronization
- **Root Legacy**: Assumed continuous streaming of 256 bits modulated to 512 complex samples with no packet preamble, no frequency offset estimation, and no frame alignment marker. Resulted in total loss of frame lock over any non-ideal channel.
- **`lpi_v4/`**: Enforces strict framing with `LPIConfig`. Frame length $N = 1024$ or $2048$ samples, with a dedicated pilot sequence, balanced energy distribution, and joint timing/CFO synchronization in `sync_and_correct()`.

### 3.2 Error-Correction Codec
- **Root Legacy**: Hardcoded `reedsolo.RSCodec(nsym=32, nsize=255)`. A 255-byte codeword requires substantial payload buffering and fails when payloads are smaller than 223 bytes without zero-padding hacks.
- **`lpi_v4/`**: Uses `RSCodec(nsym=8, nsize=42)`, designed for compact tactical burst packets (34 data bytes + 8 parity bytes, correcting up to 4 symbol errors per packet).

### 3.3 Cryptographic Security Boundaries
- **Root Legacy**:
  ```python
  # INSECURE LEGACY IMPLEMENTATION
  ctr = Counter.new(128, initial_value=0) # ZERO NONCE REUSED EVERY PACKET
  cipher = AES.new(b"0123456789abcdef", AES.MODE_CTR, counter=ctr)
  ```
  - Reusing AES-CTR counter with a fixed key destroys confidentiality (allows two-time pad attacks).
  - Lacks Message Authentication Code (MAC). Ciphertext bit flips result in predictable plaintext changes.
- **`SHADOWLINK FIELD` Standard**:
  - Implements versioned authenticated encryption (`AES-256-GCM` or `ChaCha20-Poly1305`) with a 96-bit cryptographically secure pseudorandom nonce generated per message.
  - Plaintext headers (sender, recipient, timestamp, message ID) are covered as Associated Authenticated Data (AAD).
  - Legacy decryption is isolated behind a sandboxed adapter with prominent warnings.

### 3.4 Runtime Platform & Hardware Dependencies
- **macOS / Radioconda Environment**:
  - The local machine runs macOS with Apple Silicon and Python 3.12 under Radioconda (`/Users/sabhay/radioconda/bin/python3`).
  - PyTorch's native complex linear algebra backend occasionally faults under specific unaligned tensor operations in `lpi_core.py`.
  - UHD hardware (`libuhd`) is not physically connected during development and CI.
  - The operational product must provide full functionality without USRP hardware or GNU Radio runtime installed.

---

## 4. Feature-to-File Traceability Matrix

| Feature | Legacy Source File | Test Status in Original Repo | SHADOWLINK FIELD Status | Target Module in Product |
|---|---|---|---|---|
| Persistent Message Outbox | None | Not implemented | Implemented & Tested | `backend/app/services/message_engine.py` |
| Idempotency & Deduplication | None | Not implemented | Implemented & Tested | `backend/app/models/message.py` |
| Durable-Receipt ACK Protocol | None | Not implemented | Implemented & Tested | `backend/app/services/message_engine.py` |
| Retry Scheduler & Expiry | None | Not implemented | Implemented & Tested | `backend/app/services/retry_scheduler.py` |
| Role-Based Access Control | None | Not implemented | Implemented & Tested | `backend/app/core/security.py` |
| Audit Logging | None | Not implemented | Implemented & Tested | `backend/app/services/audit_service.py` |
| Common Adapter Interface | None | Not implemented | Implemented & Tested | `backend/app/adapters/base.py` |
| Motorola Radio Integration | None | Not implemented | Scaffolded & Verified Contract | `integration/motorola/` |
| STAR-V Radio Integration | None | Not implemented | Feasibility Stub & Safety Guards | `integration/starv/` |
| SDR Research Wrapper | `lpi_v4/lpi_core.py` | Unit tested | Wrapped & Isolated | `integration/sdr/` |
| Diagnostic Health Service | Partial in `app.py` | Ad-hoc | Implemented & Structured | `backend/app/services/diagnostic_service.py` |
| PWA Field Web UI | `index.html` (monolithic) | Untested manual | Modern React+TS+Vite SPA | `frontend/` |

---

## 5. Security & Safety Recommendations

1. **Never Initiate Over-the-Air Transmissions Automatically**:
   All radio adapters default to `DISARMED` and `UNCONFIGURED`. Transmission requires explicit operator role credentials, verified configuration, and confirmation.
2. **Distinct Simulation Badges**:
   All simulated channels, mock responses, and synthetic metrics must display `SIMULATION` prominently to prevent operator confusion during exercises.
3. **Hardware Boundary Isolation**:
   No radio hardware control commands may be sent without authenticated user sessions and logged audit events.

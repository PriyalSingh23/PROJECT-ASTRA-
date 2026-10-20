# Pitfalls Research: Tactical Communications & LPI Platform

**Domain:** Tactical Store-and-Forward Messaging & Neural Spread-Spectrum Physical Layer  
**Researched:** 2026-10-16  
**Confidence:** HIGH  

---

## 1. Critical Pitfalls & Mitigation Strategies

### Pitfall 1: Shared In-Memory State in Multi-Endpoint Simulation

**What goes wrong:**  
In unit or integration tests, simulated endpoints (Alpha and Bravo) share a single SQLite database handle, global ORM session, or in-memory dictionary. Senders silently "deliver" messages by directly querying the receiver's database tables or memory structures without actually traversing the network or transport layer.

**Why it happens:**  
It is faster and less code to instantiate one Flask app or one SQLAlchemy session and pretend it represents multiple independent physical stations.

**How to avoid:**  
Enforce the Isolated Dual-Database Architecture: Station Alpha operates on `alpha.db` and Station Bravo operates on `bravo.db`. Endpoints communicate strictly via HTTP REST endpoints (`/api/v1/messages`) or decoupled transport links. No shared database handles or memory caches are permitted.

**Warning signs:**  
Delivery states update instantaneously with 0.0ms latency even when transport link drop rate is set to 100%.

**Phase to address:**  
Phase 1 (Milestone 1 — Dual-Station Messaging & Offline Recovery).

---

### Pitfall 2: Stream Cipher Keystream Reuse (Two-Time Pad Flaw)

**What goes wrong:**  
Encrypting multiple messages using the same symmetric key with a static or fixed initialization vector (IV/nonce) allows eavesdroppers to XOR ciphertexts together:
$$C_1 \oplus C_2 = (P_1 \oplus K) \oplus (P_2 \oplus K) = P_1 \oplus P_2$$
This completely exposes the underlying plaintext payloads to passive interception without knowing the key.

**Why it happens:**  
Legacy prototype code often hardcoded `initial_value=0` or reused static 16-byte nonce arrays across all message transmissions.

**How to avoid:**  
Implement versioned authenticated encryption (`AES-256-GCM v2` in `messaging/crypto_v2.py`). Enforce a fresh 96-bit cryptographically secure random nonce (`os.urandom(12)`) on every single transmission. Reject any frame that reuses a observed nonce.

**Warning signs:**  
Ciphertext headers starting with identical byte sequences across consecutive transmissions.

**Phase to address:**  
Phase 1 & Phase 2 (Cryptographic Review & Envelope Verification).

---

### Pitfall 3: macOS Port Collisions (Port 5000 AirPlay / Port 5001 Legacy)

**What goes wrong:**  
Flask applications attempting to bind to default port 5000 fail or silently route traffic to Apple's AirPlay Receiver daemon (`ControlCenter`). Binding to port 5001 triggers conflicts with orphaned legacy prototypes.

**Why it happens:**  
macOS Monterey (12+) claims port 5000 natively for system AirPlay services. Developers accustomed to Linux/Windows run into silent binding failures or 403 Forbidden responses.

**How to avoid:**  
Standardize on canonical port **5050** for the primary backend and React UI. Terminate all background processes on port 5001 and permanently decommission legacy prototypes.

**Warning signs:**  
Flask logs `Address already in use` or browser returns AirPlay audio stream error on `127.0.0.1:5000`.

**Phase to address:**  
Already remediated in Phase 0; maintained continuously via `scripts/dev.sh` and `scripts/stop_dev.sh`.

---

### Pitfall 4: OpenBLAS Dynamic Linker Collision (SIGSEGV 139)

**What goes wrong:**  
Running Python scripts on macOS (especially Apple Silicon `arm64`) crashes with an immediate segmentation fault (`Process finished with exit code 139`) when importing PyTorch and NumPy/SciPy.

**Why it happens:**  
Accelerate / OpenBLAS shared libraries loaded by NumPy conflict with PyTorch's internal vectorization libraries when NumPy is loaded first into the process symbol table.

**How to avoid:**  
Strictly enforce import ordering across all entry points: `import torch` must precede `import numpy` or `import scipy`.

**Warning signs:**  
Instant Python interpreter termination on launch without any Python traceback.

**Phase to address:**  
All phases (enforced in `server.py`, `worker.py`, `lpi_core.py`, and test harnesses).

---

### Pitfall 5: Simulating Physical RF and Reporting as Hardware Verification

**What goes wrong:**  
Engineering reports claim successful radio transmission and reception based entirely on synthetic in-memory Gaussian channel simulations, without testing real physical radio frequency hardware.

**Why it happens:**  
USRP SDR hardware is expensive, requires calibrated attenuators, RF licensing, and physical antennas. It is tempting to label a successful unit test as a "verified wireless deployment."

**How to avoid:**  
Enforce strict separation between simulated adapters and physical SDR drivers:
- Label all simulated transports with `SIMULATION_ONLY`.
- Require verified USRP IQ captures and spectrum analyzer measurements before claiming physical RF readiness.
- Keep STAR-V tactical radio in `LOCKED_OUT` state until official vendor ICD is verified.

**Warning signs:**  
Zero bit error rate (0% BER) reported over wireless links without any carrier frequency offset (CFO) or multipath fading.

**Phase to address:**  
Phase 3 & Phase 4 (Transport Interoperability & SDR Hardware Verification).

---

### Pitfall 6: Lost ACKs Causing Infinite Retries

**What goes wrong:**  
A message is successfully received and processed by the recipient, but the return acknowledgement packet is lost or corrupted in transit. The sender's worker assumes the message failed and retries infinitely, spamming the channel with duplicates.

**Why it happens:**  
Naive retry logic without max attempt thresholds, or recipient failing to recognize duplicate transmissions of an already-delivered message.

**How to avoid:**  
- Sender enforces max retry attempts (e.g., 5 attempts) with exponential backoff and jitter before transitioning to `FAILED`.
- Recipient recognizes duplicate `message_id`, immediately re-emits the existing signed ACK receipt from the `acknowledgements` table, and does not duplicate the payload in the inbox.

**Warning signs:**  
Exponential growth of inbox message counts for a single user action.

**Phase to address:**  
Phase 1 (Milestone 1 — Delivery Queue & ACK Reconciliation).

---

*Refreshed: 2026-10-16*

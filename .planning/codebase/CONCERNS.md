# Codebase Concerns

**Analysis Date:** 2026-10-19

## Tech Debt

**Single-Database Shared Storage vs Dual-Station Isolation:**
- Issue: Station Alpha and Station Bravo currently read and write to the same SQLite database file (`shadowcomm_messaging.db`), sharing table space and in-memory caches.
- Files: `Final-Project/messaging/db.py`, `Final-Project/messaging/server.py`, `Final-Project/messaging/worker.py`
- Impact: Cannot strictly prove isolation across simulated network links; potential for accidental in-memory state leakage between stations.
- Fix approach: Implement isolated dual-database architecture (`alpha.db` and `bravo.db`) communicating solely via network transports and REST APIs.

**Hardcoded Windows Paths in Tooling Configuration:**
- Issue: `pyrightconfig.json` hardcodes absolute Windows paths (`C:\Users\gspra\radioconda\python.exe` and `c:\Users\gspra\OneDrive\Desktop\LPI_CGAN`).
- Files: `Final-Project/pyrightconfig.json`
- Impact: Language servers, typecheckers, and IDE linters on macOS and Linux fail to resolve virtual environment packages or report false type errors.
- Fix approach: Replace absolute Windows paths with platform-agnostic virtual environment references (`.venv` or relative `./venv/bin/python`).

**Untracked / Legacy Root Scratch Scripts:**
- Issue: Legacy scratch files with spaces in filenames (`priyal gg.py`, `priyal gg.grc`, `priyalgg.py`) remain in the repository root.
- Files: `Final-Project/priyal gg.py`, `Final-Project/priyal gg.grc`, `Final-Project/priyalgg.py`
- Impact: Clutters workspace, causes script syntax errors in shell commands that omit quotation marks, and confuses new developers.
- Fix approach: Archive or remove legacy exploratory scripts into a dedicated `archive/` or `legacy/` directory.

---

## Known Bugs

**Dynamic Linker OpenBLAS Crash (SIGSEGV 139):**
- Symptoms: Python process terminates immediately with `Segmentation fault: 11` or exit code 139 on macOS Apple Silicon.
- Files: `Final-Project/tests/conftest.py`, `Final-Project/messaging/server.py`, `Final-Project/scripts/dev.sh`
- Trigger: Importing `numpy` or `scipy` before `torch` triggers dynamic symbol collision between Apple Accelerate / Metal and OpenBLAS.
- Workaround: Explicitly enforce `import torch` as the very first import before any numerical libraries across all entry points and test fixtures.

---

## Security Considerations

**Default Insecure Secret Key Fallback:**
- Risk: If `SHADOWCOMM_SECRET_KEY` is omitted from the environment, the server defaults to `"shadowcomm-dev-secret-key-offline-demo"`.
- Files: `Final-Project/messaging/server.py`, `Final-Project/messaging/ack_manager.py`
- Current mitigation: `auth_service.py` validates tokens using PBKDF2-HMAC-SHA256 with 100,000 iterations, but HMAC signatures for ACK receipts use the default key if unset.
- Recommendations: Enforce strict startup validation that refuses to start in non-development modes if `SHADOWCOMM_SECRET_KEY` is unset or equals the dev default.

**PyTorch Model Deserialization:**
- Risk: Untrusted `.pt` checkpoint loading can execute arbitrary code during `torch.load()`.
- Files: `Final-Project/lpi_v4/lpi_core.py`, `Final-Project/integration/lpi_cgan/adapter.py`
- Current mitigation: Models are validated against a SHA-256 digest in `export_manifest.json`.
- Recommendations: Set `weights_only=True` in `torch.load()` calls across all checkpoint ingestion points.

---

## Performance Bottlenecks

**SQLite Single-Writer Concurrency:**
- Problem: High write concurrency under heavy simulated packet bursts can encounter busy timeouts.
- Files: `Final-Project/messaging/db.py`, `Final-Project/messaging/worker.py`
- Cause: SQLite allows multiple concurrent readers in WAL mode, but only one write transaction at a time.
- Improvement path: Retain the 5000ms busy timeout, maintain short write transactions, and bundle bulk insertions where feasible.

---

## Fragile Areas

**STAR-V Radio Software Safety Lockout:**
- Files: `Final-Project/integration/starv/adapter.py`
- Why fragile: Physical transmission is inhibited purely by software guards (`StarVSafetyLockoutError`). Accidental alteration of the readiness flag could trigger unauthorized RF emissions.
- Safe modification: Hardware safety lockouts must remain hardcoded and validated by automated tests (`Final-Project/tests/integration/test_adapters.py`) until formal vendor ICD hardware verification.
- Test coverage: Covered by `test_starv_adapter_safety_lockout`.

**Motorola DMR 280-Byte Packet Ceiling:**
- Files: `Final-Project/integration/motorola/adapter.py`, `Final-Project/integration/motorola/hardware_bridge.py`
- Why fragile: MOTOTRBO TMS PDUs have a strict hardware payload limit of 280 bytes. Any message payload exceeding this ceiling without fragmentation causes silent transmission failure or transport rejection.
- Safe modification: Enforce payload size validation before passing payloads to the adapter.
- Test coverage: Covered by `test_motorola_adapter_capability_and_limits` and `test_tms_pdu_rejects_oversize`.

---

## Scaling Limits

**SQLite Message Queue Volume:**
- Current capacity: Validated up to 1,050 messages in deterministic stress testing with zero message loss.
- Limit: Performance degradation expected if table exceeds 50,000 active un-purged message records without indexing adjustments.
- Scaling path: Implement periodic archival or vacuuming of `DELIVERED` and `EXPIRED` records into historical tables.

---

## Dependencies at Risk

**Radioconda / GNU Radio Platform Lock:**
- Risk: GNU Radio 3.10 and UHD bindings require complex C++ libraries that differ significantly between macOS Homebrew, Radioconda, and Linux distros.
- Impact: Difficult to deploy consistently on standardized cloud CI/CD containers without containerized SDR environments.
- Migration plan: Maintain containerized Docker / Podman SDR build images with pre-compiled UHD and GNU Radio dependencies.

---

## Missing Critical Features

**Dual-Station Side-by-Side Live Operator Console:**
- Problem: Current React web interface shows a single unified view rather than simultaneous Station Alpha outbox and Station Bravo inbox panes.
- Blocks: Live visual demonstration of simultaneous transmission, reception, and ACK reconciliation on a single screen without switching tabs.

**Automated Frontend Unit / Integration Tests:**
- Problem: The React frontend has no automated Vitest / Jest test runner configured; only `oxlint` and TypeScript compilation (`tsc -b`).
- Blocks: Automated regression testing of browser IndexedDB outbox synchronization, Recharts spectrum updates, and tactical UI interactions.

---

## Test Coverage Gaps

**Browser Offline Outbox Synchronization (IndexedDB):**
- What's not tested: Offline message persistence in browser IndexedDB (`outboxDb.ts`) and automatic retry flush upon link restoration.
- Files: `Final-Project/frontend/src/services/outboxDb.ts`, `Final-Project/frontend/src/services/api.ts`
- Risk: Client messages could remain stuck in browser outbox if sync edge cases fail unnoticed.
- Priority: High

**Live SDR Physical Radio Hardware I/O:**
- What's not tested: Real over-the-air RF transmission on Ettus USRP B200/B210 SDR hardware (tested via simulated recorded IQ datasets).
- Files: `Final-Project/lpi_v4/tx_usrp.py`, `Final-Project/lpi_v4/rx_usrp.py`, `Final-Project/lpi_v4/uhd_io.py`
- Risk: Timing jitter, sample drops, or DAC underflows on physical hardware under varying system loads.
- Priority: Medium

---

*Concerns audit: 2026-10-19*

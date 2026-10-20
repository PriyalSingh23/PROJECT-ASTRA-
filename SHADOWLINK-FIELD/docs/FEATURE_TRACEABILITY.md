# Feature Traceability Matrix: SHADOWLINK FIELD

This document tracks every system requirement against its design specification, target source files, and test coverage.

| Req ID | Requirement Description | Design Specification | Implementation Path | Verification & Test Suite |
|---|---|---|---|---|
| **REQ-01** | **Durable Message Ingestion** | Incoming messages must be persisted to disk before network dispatch is acknowledged. | `backend/app/services/message_engine.py`<br>`backend/app/models/message.py` | `tests/unit/test_message_engine.py`<br>`tests/simulation/test_offline_flow.py` |
| **REQ-02** | **Client-Side Offline Outbox** | Browser client must store composed drafts and pending messages in IndexedDB across reloads. | `frontend/src/services/outboxDb.ts`<br>`frontend/src/services/syncManager.ts` | `tests/simulation/test_client_sync.py` |
| **REQ-03** | **Honest Delivery State Machine** | Strict 12-state transition engine. `DELIVERED` status requires cryptographic or durable ACK. | `backend/app/core/state_machine.py`<br>`backend/app/services/message_engine.py` | `tests/unit/test_state_machine.py` |
| **REQ-04** | **Receiver Deduplication** | Receiver inbox must reject duplicate transmissions and regenerate the canonical receipt. | `backend/app/services/message_engine.py`<br>`backend/app/models/inbox.py` | `tests/simulation/test_deduplication.py` |
| **REQ-05** | **Configurable Retry & Backoff** | Exponential backoff with random jitter; distinguish retryable vs permanent errors. | `backend/app/services/retry_scheduler.py` | `tests/unit/test_retry_policy.py` |
| **REQ-06** | **Message Expiry & TTL** | Deadlines are enforced; expired messages must not be delivered as current. | `backend/app/services/retry_scheduler.py` | `tests/unit/test_expiry.py` |
| **REQ-07** | **Atomic Worker Leasing** | Prevent concurrent workers from double-processing messages or colliding on database locks. | `backend/app/services/worker.py` | `tests/simulation/test_concurrency_race.py` |
| **REQ-08** | **Common Adapter Interface** | Unified contract (`ICommunicationAdapter`) for hardware and simulated channels. | `backend/app/adapters/base.py` | `tests/unit/test_adapter_contract.py` |
| **REQ-09** | **Simulated Transport Link** | Software-only channel with configurable delay, packet drop, ACK loss, and link cuts. | `backend/app/adapters/simulation.py` | `tests/simulation/test_transport_sim.py` |
| **REQ-10** | **Motorola Integration Module** | Device profiles for exact model, audio/PTT interoperability, documented digital API. | `integration/motorola/`<br>`backend/app/adapters/motorola.py` | `tests/integration/test_motorola_adapter.py` |
| **REQ-11** | **STAR-V Feasibility Stub** | Disabled safety stub preventing unauthorized hardware action without documentation. | `integration/starv/`<br>`backend/app/adapters/starv.py` | `tests/integration/test_starv_adapter.py` |
| **REQ-12** | **SDR Research Isolation** | Wrap `lpi_v4/` behind software research adapter without triggering RF hardware. | `integration/sdr/`<br>`backend/app/adapters/sdr.py` | `tests/integration/test_sdr_adapter.py` |
| **REQ-13** | **Role-Based Access Control** | Authenticated JWT sessions with `ADMIN`, `OPERATOR`, and `OBSERVER` permissions. | `backend/app/core/security.py`<br>`backend/app/api/auth.py` | `tests/unit/test_auth_rbac.py` |
| **REQ-14** | **Safe Audit Timeline** | Diagnostic events logged without plaintext payloads, passwords, or encryption keys. | `backend/app/services/audit_service.py`<br>`backend/app/models/audit.py` | `tests/unit/test_audit_safety.py` |
| **REQ-15** | **System Diagnostics & Health** | Structured non-transmitting self-tests of DB, queues, drivers, and adapters. | `backend/app/services/diagnostic_service.py`<br>`backend/app/api/diagnostics.py` | `tests/unit/test_diagnostics.py` |
| **REQ-16** | **Responsive PWA Field UI** | Accessible dark-theme UI with Dashboard, Message Center, Adapters, and Diagnostics. | `frontend/src/App.tsx`<br>`frontend/src/components/*` | Frontend build & component tests |

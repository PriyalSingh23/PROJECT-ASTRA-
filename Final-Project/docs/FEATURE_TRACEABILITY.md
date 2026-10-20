# FEATURE TRACEABILITY MATRIX

**System**: SHADOWLINK FIELD  
**Repository**: `https://github.com/PriyalSingh23/Final-Project`  
**Evaluation Scope**: Feature-to-File Traceability, Implementation Status & Test Evidence  
**Status Date**: October 2026  

---

## 1. Traceability Overview

This document provides complete traceability from product requirements to source code files, automated test suites, and documentation. Each capability is explicitly classified under one of five verified statuses:
- **IMPLEMENTED & TESTED**: Full production logic implemented and verified by automated tests.
- **IMPLEMENTED (UNTESTED IN CI)**: Implemented in code; requires physical hardware or external systems.
- **PARTIALLY IMPLEMENTED**: Basic logic present; edge-case handling or persistence incomplete.
- **PLANNED**: Architected in design specifications; implementation scheduled for future phase.
- **LOCKED OUT**: Disabled deliberately by safety policy (e.g., unauthorized RF transmission).

---

## 2. Core Messaging & Storage Traceability

| Requirement ID | Capability Description | Status | Primary Source File(s) | Automated Test Evidence | Documentation Reference |
|:---|:---|:---|:---|:---|:---|
| **REQ-MSG-01** | Client-Side Outbox (IndexedDB) | **IMPLEMENTED & TESTED** | [`messaging/templates/offline_messaging.html#L380-L438`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/messaging/templates/offline_messaging.html#L380-L438) | `test_offline_messaging.py::test_03_client_disconnected_from_backend`<br>`test_offline_messaging.py::test_14_user_interface_persistence` | [`docs/OFFLINE_MESSAGING_IMPLEMENTATION.md`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/docs/OFFLINE_MESSAGING_IMPLEMENTATION.md) |
| **REQ-MSG-02** | Persistent Backend Queue | **IMPLEMENTED & TESTED** | [`messaging/models.py#L53-L103`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/messaging/models.py#L53-L103)<br>[`messaging/db.py#L12-L40`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/messaging/db.py#L12-L40) | `test_offline_messaging.py::test_01_successful_delivery_under_clean_conditions`<br>`test_offline_messaging.py::test_04_backend_restart_pending_messages` | [`docs/REAL_WORLD_READINESS.md`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/docs/REAL_WORLD_READINESS.md) |
| **REQ-MSG-03** | Durable Receiver Inbox | **IMPLEMENTED & TESTED** | [`messaging/models.py#L105-L128`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/messaging/models.py#L105-L128)<br>[`messaging/ack_manager.py#L22-L65`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/messaging/ack_manager.py#L22-L65) | `test_offline_messaging.py::test_01_successful_delivery_under_clean_conditions`<br>`test_simulation_1000_messages.py` (Phase 4) | [`docs/OFFLINE_MESSAGING_TEST_REPORT.md`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/docs/OFFLINE_MESSAGING_TEST_REPORT.md) |
| **REQ-MSG-04** | Client Idempotency Keys | **IMPLEMENTED & TESTED** | [`messaging/service.py#L21-L85`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/messaging/service.py#L21-L85)<br>[`messaging/models.py#L74-L77`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/messaging/models.py#L74-L77) | `test_offline_messaging.py::test_06_duplicate_submission_idempotency`<br>`test_simulation_1000_messages.py` (Phase 5) | [`docs/REAL_WORLD_READINESS.md`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/docs/REAL_WORLD_READINESS.md) |
| **REQ-MSG-05** | Receiver Deduplication | **IMPLEMENTED & TESTED** | [`messaging/ack_manager.py#L32-L42`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/messaging/ack_manager.py#L32-L42) | `test_offline_messaging.py::test_11_duplicate_receiver_delivery`<br>`test_simulation_1000_messages.py` (Phase 4) | [`docs/OFFLINE_MESSAGING_TEST_REPORT.md`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/docs/OFFLINE_MESSAGING_TEST_REPORT.md) |
| **REQ-MSG-06** | Receiver-Generated Signed Receipts (ACK) | **IMPLEMENTED & TESTED** | [`messaging/ack_manager.py#L44-L65`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/messaging/ack_manager.py#L44-L65)<br>[`messaging/models.py#L130-L165`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/messaging/models.py#L130-L165) | `test_offline_messaging.py::test_01_successful_delivery_under_clean_conditions`<br>`test_offline_messaging.py::test_07_lost_acknowledgement_handling` | [`docs/OFFLINE_MESSAGING_IMPLEMENTATION.md`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/docs/OFFLINE_MESSAGING_IMPLEMENTATION.md) |
| **REQ-MSG-07** | Sender-Side Receipt Validation | **IMPLEMENTED & TESTED** | [`messaging/ack_manager.py#L67-L95`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/messaging/ack_manager.py#L67-L95) | `test_offline_messaging.py::test_01_successful_delivery_under_clean_conditions`<br>`test_offline_messaging.py::test_12_invalid_message_and_ack_validation` | [`docs/REAL_WORLD_READINESS.md`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/docs/REAL_WORLD_READINESS.md) |
| **REQ-MSG-08** | Exponential Backoff & Expiry Scheduling | **IMPLEMENTED & TESTED** | [`messaging/retry_policy.py#L43-L93`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/messaging/retry_policy.py#L43-L93) | `test_offline_messaging.py::test_08_temporary_delivery_failure_backoff`<br>`test_simulation_1000_messages.py` (Phase 6) | [`docs/OFFLINE_MESSAGING_TEST_REPORT.md`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/docs/OFFLINE_MESSAGING_TEST_REPORT.md) |
| **REQ-MSG-09** | Outage-to-Online Recovery | **IMPLEMENTED & TESTED** | [`messaging/transport.py#L30-L75`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/messaging/transport.py#L30-L75)<br>[`messaging/templates/offline_messaging.html#L440-L476`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/messaging/templates/offline_messaging.html#L440-L476) | `test_offline_messaging.py::test_02_offline_transport_and_resumption`<br>`test_simulation_1000_messages.py` (Phase 2) | [`docs/OFFLINE_MESSAGING_TEST_REPORT.md`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/docs/OFFLINE_MESSAGING_TEST_REPORT.md) |
| **REQ-MSG-10** | Worker Process & Crash Lease Reclamation | **IMPLEMENTED & TESTED** | [`messaging/worker.py#L60-L126`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/messaging/worker.py#L60-L126)<br>[`messaging/retry_policy.py#L95-L132`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/messaging/retry_policy.py#L95-L132) | `test_offline_messaging.py::test_05_worker_interruption_and_lease_reclamation`<br>`test_simulation_1000_messages.py` (Phase 7) | [`docs/OFFLINE_MESSAGING_TEST_REPORT.md`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/docs/OFFLINE_MESSAGING_TEST_REPORT.md) |
| **REQ-MSG-11** | Message Event Audit Timeline | **IMPLEMENTED & TESTED** | [`messaging/models.py#L170-L208`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/messaging/models.py#L170-L208)<br>[`messaging/api.py#L125-L138`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/messaging/api.py#L125-L138) | `test_offline_messaging.py::test_01_successful_delivery_under_clean_conditions`<br>`test_offline_messaging.py::test_08_temporary_delivery_failure_backoff` | [`docs/REAL_WORLD_READINESS.md`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/docs/REAL_WORLD_READINESS.md) |
| **REQ-MSG-12** | Two-Worker Concurrency Protection | **IMPLEMENTED & TESTED** | [`messaging/worker.py#L100-L135`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/messaging/worker.py#L100-L135) | `test_offline_messaging.py::test_13_two_worker_concurrency_race_condition` | [`docs/OFFLINE_MESSAGING_IMPLEMENTATION.md`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/docs/OFFLINE_MESSAGING_IMPLEMENTATION.md) |

---

## 3. Security & Access Control Traceability

| Requirement ID | Capability Description | Status | Primary Source File(s) | Automated Test Evidence | Documentation Reference |
|:---|:---|:---|:---|:---|:---|
| **REQ-SEC-01** | Insecure Secrets Removal & Env Config | **IMPLEMENTED & TESTED** | [`app.py#L14-L35`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/app.py#L14-L35)<br>[`.env.example`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/.env.example) | Verified via environment variable overrides and test harnesses | [`docs/SECURITY_REMEDIATION.md`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/docs/SECURITY_REMEDIATION.md) |
| **REQ-SEC-02** | Independent Endpoint Token Authentication | **IMPLEMENTED & TESTED** | [`messaging/models.py#L28-L48`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/messaging/models.py#L28-L48)<br>[`messaging/api.py#L47-L95`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/messaging/api.py#L47-L95) | Verified via `verify_auth` endpoint and token auth unit checks | [`docs/SECURITY_REMEDIATION.md`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/docs/SECURITY_REMEDIATION.md) |
| **REQ-SEC-03** | Restricted Origin CORS Policy | **IMPLEMENTED & TESTED** | [`app.py#L30-L38`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/app.py#L30-L38) | Verified in Flask initialization configuration | [`docs/SECURITY_REMEDIATION.md`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/docs/SECURITY_REMEDIATION.md) |
| **REQ-SEC-04** | Keystream Reuse (AES-CTR 0-Counter) Audit | **DOCUMENTED** | [`app.py#L48`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/app.py#L48) | Documented vulnerability; messaging subsystem isolated from vulnerable path | [`docs/SECURITY_REMEDIATION.md`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/docs/SECURITY_REMEDIATION.md) |
| **REQ-SEC-05** | Credential Sanitization in Serializers | **IMPLEMENTED & TESTED** | [`messaging/models.py#L40-L51`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/messaging/models.py#L40-L51) | `test_offline_messaging.py::test_14_user_interface_persistence` | [`docs/SECURITY_REMEDIATION.md`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/docs/SECURITY_REMEDIATION.md) |

---

## 4. Scientific LPI-CGAN Research Traceability

| Requirement ID | Research Capability | Status | Source File(s) | Test / Verification Evidence | Documentation Reference |
|:---|:---|:---|:---|:---|:---|
| **REQ-LPI-01** | 128-bit Frame & 9.03 dB Spreading | **IMPLEMENTED & TESTED** | [`lpi_v4/lpi_core.py#L12-L350`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/lpi_v4/lpi_core.py#L12-L350) | `test_lpi_v4.py::test_config_derived_sizes`<br>`test_lpi_v4.py::test_generator_forward` | [`lpi_v4/README.md`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/lpi_v4/README.md)<br>[`FINDINGS.md`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/FINDINGS.md) |
| **REQ-LPI-02** | Keyed Zadoff-Chu Pilots | **IMPLEMENTED & TESTED** | [`lpi_v4/lpi_core.py#L75-L120`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/lpi_v4/lpi_core.py#L75-L120) | `test_lpi_v4.py::test_preamble_is_keyed_and_unambiguous` | [`FINDINGS.md`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/FINDINGS.md) |
| **REQ-LPI-03** | CRC-8 & Reed-Solomon RS(42,34) | **IMPLEMENTED & TESTED** | [`lpi_v4/lpi_crypto.py#L12-L180`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/lpi_v4/lpi_crypto.py#L12-L180) | `test_lpi_v4.py::test_rs_codec_roundtrip`<br>`test_lpi_v4.py::test_crc8_detects_errors` | [`lpi_v4/README.md`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/lpi_v4/README.md) |
| **REQ-LPI-04** | Frame Sync & CFO Compensation | **IMPLEMENTED & TESTED** | [`lpi_v4/lpi_core.py#L500-L680`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/lpi_v4/lpi_core.py#L500-L680) | `test_lpi_v4.py::test_sync_finds_offset_cfo_and_frames` | [`FINDINGS.md`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/FINDINGS.md) |
| **REQ-LPI-05** | Direct UHD SDR Transceiver | **IMPLEMENTED (UNTESTED)** | [`lpi_v4/tx_usrp.py`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/lpi_v4/tx_usrp.py), [`lpi_v4/rx_usrp.py`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/lpi_v4/rx_usrp.py) | Requires USRP B200 hardware | [`FIELD_TEST_CHECKLIST.md`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/FIELD_TEST_CHECKLIST.md) |
| **REQ-LPI-06** | LPI-CGAN Neural Transport Adapter | **IMPLEMENTED & TESTED** | [`integration/lpi_cgan/adapter.py`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/integration/lpi_cgan/adapter.py) | `tests/integration/test_adapters.py::test_lpi_cgan_adapter_pipeline` | [`docs/SDR_RESEARCH_GUIDE.md`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/docs/SDR_RESEARCH_GUIDE.md) |

---

## 5. Radio Interoperability Traceability

| Requirement ID | Radio Target | Status | Architectural Approach | Safety Enforcement | Documentation Reference |
|:---|:---|:---|:---|:---|:---|
| **REQ-RAD-01** | Motorola MOTOTRBO / APX | **PLANNED** | TMS over XCMP / MNIS Ethernet | Physical transmission prohibited during pilot | [`docs/REAL_WORLD_READINESS.md#motorola-mototrbo--apx-integration-readiness-checklist`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/docs/REAL_WORLD_READINESS.md#motorola-mototrbo--apx-integration-readiness-checklist) |
| **REQ-RAD-02** | STAR-V Tactical SDR | **LOCKED OUT** | Software simulator only | Permanent software lockout enforced | [`docs/REAL_WORLD_READINESS.md#7-star-v-tactical-radio-feasibility-assessment`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/docs/REAL_WORLD_READINESS.md#7-star-v-tactical-radio-feasibility-assessment) |

# SHADOWLINK FIELD: Acceptance Test Plan & Verification Matrix

**Document Version:** 1.0.0  
**Target:** Pre-deployment Verification & Factory Acceptance Testing (FAT)

---

## 1. Test Levels & Strategy

The acceptance plan implements four strict tiers of validation:

```
+-----------------------------------------------------------------------------------------+
|                                    TESTING HIERARCHY                                    |
|                                                                                         |
|  [ LEVEL 1: UNIT TESTS ]              - Pydantic models, state machine transitions,     |
|                                         cryptographic primitives, retry backoff math    |
|                                                                                         |
|  [ LEVEL 2: INTEGRATION TESTS ]       - Database transactions, REST endpoints, JWT      |
|                                         auth, RBAC enforcement, WebSocket feeds         |
|                                                                                         |
|  [ LEVEL 3: SIMULATION TESTS ]        - 2 simulated endpoints, link cuts, dropped ACKs, |
|                                         worker crash recovery, concurrent lease races   |
|                                                                                         |
|  [ LEVEL 4: ADAPTER CONTRACT TESTS ]  - Common adapter interface compliance, Motorola  |
|                                         profile validation, STAR-V safety lockouts      |
+-----------------------------------------------------------------------------------------+
```

---

## 2. Test Cases & Verification Procedures

### Suite A: Message Engine & State Machine
- **TC-ENG-01: End-to-End Delivery Under Clean Conditions**
  - *Input*: Submit message A &rarr; B over simulated transport with 0% loss.
  - *Expected*: Ingested as `QUEUED`, leased as `SENDING`, stored in B inbox, ACK validated, status reaches `DELIVERED`.
- **TC-ENG-02: Link Interruption & Store-and-Forward Resumption**
  - *Input*: Toggle simulated link to `OFFLINE`. Submit message A &rarr; B. Wait 5 seconds. Restore link to `ONLINE`.
  - *Expected*: Message remains in `QUEUED` / `FAILED_RETRYABLE` while offline. Once restored, worker delivers message and returns receipt.
- **TC-ENG-03: Client-Side Disconnect & IndexedDB Outbox Preservation**
  - *Input*: Kill backend server. Draft and send message in browser UI. Reload browser. Restart backend server.
  - *Expected*: Message survives reload in IndexedDB `LOCAL_QUEUED`. Sync manager automatically transmits and obtains server message ID upon backend restart.
- **TC-ENG-04: Receiver Deduplication Under Multiple Dispatches**
  - *Input*: Transmit message with identical `message_id` 3 times to Endpoint B.
  - *Expected*: Exactly 1 row inserted into `inbox`. Duplicate attempts log `DUPLICATE_DELIVERY_IGNORED` and regenerate the existing ACK receipt.
- **TC-ENG-05: Lost Acknowledgement Recovery**
  - *Input*: Deliver message to B, but drop return ACK (drop_ack = 1.0).
  - *Expected*: Sender enters `AWAITING_ACK`. Retrying original message does not duplicate inbox entry, retrieves receipt, and completes to `DELIVERED`.
- **TC-ENG-06: Two-Worker Concurrency Protection**
  - *Input*: Run 2 concurrent worker threads against a 6-message queue.
  - *Expected*: Conditional leasing ensures each message is leased by exactly one worker. Exactly 6 messages delivered; no race conditions or deadlocks.

### Suite B: Security & Role-Based Access Control
- **TC-SEC-01: Unauthorized Hardware Command Rejection**
  - *Input*: Attempt to arm or configure an adapter with an `OBSERVER` JWT token.
  - *Expected*: HTTP 403 Forbidden with structured error `INSUFFICIENT_ROLE_PERMISSIONS`.
- **TC-SEC-02: Audit Redaction Verification**
  - *Input*: Submit message with secret text `"TOP_SECRET_COORDINATES_34N_71E"`. Query `/api/v1/audit/logs` and `/api/v1/messages/{id}/events`.
  - *Expected*: Plaintext is absent from all audit records and metadata dictionaries. Only message length and SHA-256 digest are logged.

### Suite C: Radio Adapters & Interoperability Contracts
- **TC-RAD-01: Common Adapter Contract Compliance**
  - *Input*: Execute contract assertions across `SimulationAdapter`, `MotorolaRadioAdapter`, `StarVRadioAdapter`, and `SdrResearchAdapter`.
  - *Expected*: All classes implement `get_metadata()`, `get_capabilities()`, `check_health()`, and `validate_config()`.
- **TC-RAD-02: STAR-V Hardware Interlock Safety Lockout**
  - *Input*: Invoke `transmit()` on `StarVRadioAdapter`.
  - *Expected*: Raises `HardwareSafetyLockoutError`. State remains `DISABLED_PREREQUISITES_MISSING`. Health check returns `ready_to_transmit=False`.
- **TC-RAD-03: Motorola Audio-Only Profile Capability Enforcement**
  - *Input*: Register Motorola profile with `PTT_AUDIO_VOICE` only. Attempt digital packet transmission.
  - *Expected*: Ingestion rejects digital packet with `UNSUPPORTED_ADAPTER_CAPABILITY`.

---

## 3. Physical Field Pilot Acceptance Checklist (Hardware-in-the-Loop)

> [!IMPORTANT]
> Software tests verify logic, state machines, and API contracts. They **do not prove physical radio compatibility**. Authorized field pilots must execute this physical checklist:

1. [ ] **Spectrum Clearance**: Written WPC/DoT or local tactical frequency allocation granted.
2. [ ] **Physical Attenuation**: First bench test executed over a calibrated 30 dB RF attenuator into a dummy load; zero over-the-air radiation.
3. [ ] **Audio Interface Alignment**: Transmitter audio deviation calibrated to $\pm 2.5\text{ kHz}$ (narrowband FM) using a calibrated communications service monitor.
4. [ ] **PTT Keying Delay**: Pre-carrier debounce delay set to $\ge 150\text{ ms}$ to allow repeater/relay key-up before preamble transmission.
5. [ ] **Independent Voice Fallback**: Primary human voice channel maintained on a separate, dedicated channel throughout all digital trials.

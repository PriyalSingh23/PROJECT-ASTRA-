# Motorola Radio Integration Specification: SHADOWLINK FIELD

**Document Version:** 1.0.0  
**Status:** Architecture Specified & Simulated Adapter Contract Verified  
**Target Environments:** MOTOTRBO Digital (DMR Tier II), APX Mission Critical (P25 Phase 1/2), Analogue Conventional

---

## 1. Scope & Operating Philosophy

Motorola Solutions produces diverse radio architectures spanning consumer business radios, MOTOTRBO DMR trunked systems, and mission-critical ASTRO 25 (P25) platforms. **SHADOWLINK FIELD does not treat "Motorola" as a single homogenous protocol.**

Instead, the platform provides a configurable **Device Profile** that requires field engineers to record and verify the exact model, firmware version, and approved physical interface prior to operation.

```
+-----------------------------------------------------------------------------------------+
|                                SHADOWLINK FIELD CORE                                    |
|                                                                                         |
|  +-----------------------------------------------------------------------------------+  |
|  |             Common Adapter Interface (ICommunicationAdapter)                      |  |
|  +-----------------------------------------+-----------------------------------------+  |
+--------------------------------------------|--------------------------------------------+
                                             |
+--------------------------------------------v--------------------------------------------+
|                         MOTOROLA ADAPTER (MotorolaRadioAdapter)                         |
|                                                                                         |
|  [ Configured Profile: MOTOTRBO XPR 7550e / APX 8000 / CM300d ]                         |
|                                                                                         |
|  +----------------------------------+     +------------------------------------------+  |
|  |     AUDIO & PTT INTERFACE        |     |      DOCUMENTED DATA INTERFACE           |  |
|  |  - Hardware GPIO / Accessory Port|     |  - Motorola MNIS / DDMS Gateway          |  |
|  |  - Tone / PTT Keying Line        |     |  - XCMP IP Packet Gateway                |  |
|  |  - Analogue Audio In / Out       |     |  - Short Data Service (TMS / Text)       |  |
|  +----------------------------------+     +------------------------------------------+  |
+-----------------------------------------------------------------------------------------+
```

---

## 2. Device Profile Data Schema

Every connected Motorola radio must be registered with an explicit profile:

```json
{
  "profile_id": "moto-prof-xpr7550e-01",
  "manufacturer": "Motorola Solutions",
  "product_family": "MOTOTRBO",
  "model_number": "AAH56RDN9WA1AN",
  "model_display_name": "XPR 7550e VHF DMR Portable",
  "hardware_revision": "Rev 2.4",
  "firmware_version": "R02.10.10.0001",
  "system_type": "DMR_DIGITAL",
  "interface_type": "ACCESSORY_GPIO_PTT_AND_USB_DATA",
  "supported_capabilities": [
    "PTT_AUDIO_VOICE",
    "SHORT_DATA_TMS",
    "HARDWARE_ACK"
  ],
  "required_vendor_gateway": "Motorola MNIS v2.10.0 (Optional for IP Data)",
  "deployment_owner": "Incident Commander Task Force Alpha",
  "approval_status": "APPROVED_FIELD_PILOT",
  "test_status": "VERIFIED_BENCH_TEST"
}
```

---

## 3. Supported Interface Paths

### Path A: Audio / PTT Accessory Interoperability (Universal Fallback)
- **Physical Connection**: Motorola 16-pin / 26-pin rear accessory connector (mobile) or multi-pin side connector (portable).
- **Control Lines**:
  - `PTT` (Push-To-Talk active-low GPIO input).
  - `EXT_MIC` (Transmitter audio input, 600 ohm balanced/unbalanced).
  - `RX_AUDIO` (Receiver discriminator or de-emphasized audio).
  - `COR` / `CARRIER_DETECT` (Channel activity indicator).
- **Semantics**: Operator voice or pre-recorded tactical audio dispatch. **The application strictly labels this as Operator Audio/PTT Interoperability and never represents analogue audio as arbitrary binary data or custom digital waveforms.**

### Path B: Documented Digital Data Interface (TMS / IP over DMR)
- **Supported Standards**: ETSI TS 102 361-1/2/3 DMR Tier II Conventional.
- **Data Capabilities**: Text Messaging Service (TMS) payloads up to 140 UTF-16 / ASCII characters per burst.
- **Requirements**: Requires Motorola MOTOTRBO Network Interface Service (MNIS) or official USB XCMP data cable.
- **Honest Delivery**: Delivery is updated to `DELIVERED` only if the radio returns an over-the-air Layer 2/3 Data Acknowledgement.

---

## 4. Strict Implementation Rules

1. **No Fictional Success**: If the radio returns an error or no ACK within the timeout window (default 12 seconds), the status transitions to `FAILED_RETRYABLE` or `FAILED_FINAL`. It is never falsely marked delivered.
2. **No Undocumented Command Inventions**: The adapter communicates strictly over documented protocol frames. It does not attempt to exploit undocumented programming modes.
3. **Firmware Integrity**: The software does not attempt to overwrite codeplugs, flash firmware, or modify cryptographic key memory.
4. **Clear UI Indicator**: In the SHADOWLINK FIELD UI, the adapter displays `MOTOROLA [MODEL] (SIMULATION)` until authenticated hardware drivers and connections are confirmed.

---

## 5. Acceptance Test Verification

The acceptance suite in `tests/integration/test_motorola_adapter.py` verifies:
- Profile schema validation and missing parameter rejection.
- Capability discovery restricting digital dispatch on audio-only configurations.
- PTT toggle assertions and timeouts.
- Channel busy detection and collision backoff.
- Return ACK parsing and error classification.
- Graceful reconnection after cable disconnection.

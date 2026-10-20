# MOTOROLA MOTOTRBO / APX INTEGRATION READINESS ASSESSMENT

**Manufacturer**: Motorola Solutions  
**Target Product Lines**: MOTOTRBO Digital Two-Way Radio (XPR 7000e / DP4000e series) & APX P25  
**Interface Specification Reference**: Motorola Application Services Developer Documentation (June 2026)  
**Status**: Adapter Architecture Implemented (Simulation & Contract Tests Verified)  

---

## 1. Supported Capabilities & Operating Constraints

Based on official Motorola application-services documentation, MOTOTRBO devices support a defined set of digital data services when operating on digital DMR channels:

| Supported Feature | Interface Protocol | Operational Parameters | SHADOWLINK Adapter Status |
|:---|:---|:---|:---|
| **Text Messaging Service (TMS)** | XCMP / IP Peripheral / MNIS | Max 280 bytes per DMR text message burst | **IMPLEMENTED & TESTED** (`integration/motorola/`) |
| **Location Reporting (LRRP)** | UDP / IP over DMR | GPS latitude, longitude, speed, heading | Supported in data schema |
| **Telemetry I/O** | XCMP GPIO commands | Remote relay trip, sensor status monitoring | Supported in adapter contract |
| **Device Discovery (ARS)** | Automatic Registration Service | Broadcasts radio power-up/online presence | Integrated into presence tracking |
| **Raw Packet Data** | UDP / IP over DMR | Small packet transport over DMR CAI | Supported with fragmentation warning |

### 1.1. Physical DMR Constraint: The 280-Byte Burst Limit
In standard DMR Tier II conventional or IP Site Connect channels, digital text messages cannot exceed **280 bytes** per transmission burst. Payloads exceeding this limit must be fragmented or rejected. The SHADOWLINK Motorola adapter enforces this limit automatically:
```python
if len(payload_bytes) > 280:
    return {"success": False, "error_code": "PAYLOAD_TOO_LARGE"}
```

---

## 2. Hardware Deployment Profiles

### Profile A: Direct Radio Connection (USB Accessory Cable)
- **Use Case**: Mobile field gateway or vehicle command terminal.
- **Connection**: Motorola PMKN4012 (or equivalent) rear accessory USB cable connected directly to the edge computer.
- **Driver**: Appears as a CDC-ECM virtual Ethernet or virtual serial COM port running XCMP.

### Profile B: Network Application Interface (MNIS / DDMS)
- **Use Case**: Fixed incident command base with repeater network.
- **Connection**: Motorola Network Interface Service (MNIS) Windows/Linux service running over IP connected to MOTOTRBO repeaters (MTR3000 / SLR 5000 / SLR 8000).

---

## 3. Operator Readiness Checklist

Before activating real Motorola radio transmissions:
- [ ] Radio CAI (Common Air Interface) Network ID and Radio ID assigned in CPS.
- [ ] Target digital channel configured for "IP Data" in Motorola CPS / Radio Management.
- [ ] Valid radio station license covering the operational frequencies and emissions designator.
- [ ] Approved Motorola Developer Program agreement and authenticated licensing key installed.

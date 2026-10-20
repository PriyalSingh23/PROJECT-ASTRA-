# RELAY NODE OPERATIONAL GUIDE & MOBILE RELAY ARCHITECTURE

**System**: SHADOWLINK Relay Management Subsystem (`integration/relay_nodes/`)  
**Scope**: Stationary, Portable Ground, Vehicle, and Aerial Relay Nodes  
**Status**: Field Pilot Operational Document  

---

## 1. Relay Node Concept of Operations (CONOPS)

In challenged terrain (valleys, dense urban structures, collapsed infrastructure), direct peer-to-peer communication between field teams is often obstructed. SHADOWLINK uses **Relay Nodes** as store-and-forward intermediaries:

```mermaid
flowchart LR
    A["Forward Node A\n(Search & Rescue Team)"] <-->|Local Wi-Fi / UHF| R["Portable Ground Relay\n(Ridge / High Ground)"]
    R <-->|Point-to-Point Link| B["Command Base B\n(Operations Center)"]
```

---

## 2. Relay Node Categories

| Node Category | Description | Primary Power Source | Deployment Location |
|:---|:---|:---|:---|
| **`PORTABLE_GROUND`** | Man-portable tactical transit case (IP67) containing edge gateway and battery | Internal LiFePO4 battery (12-24h) | Elevated terrain, rooftops, vehicle hoods |
| **`FIXED_GATEWAY`** | Semi-permanent base station gateway | AC mains with UPS backup | Incident Command Post (ICP) |
| **`VEHICLE_GATEWAY`** | Vehicle-mounted mobile gateway | 12V/24V vehicle electrical system | Response trucks, mobile command vehicles |
| **`AERIAL_PAYLOAD_SIMULATED`** | Tethered balloon or drone-mounted networking payload | Tethered DC power or flight pack | Aerial altitude extension (Simulation only) |

---

## 3. Telemetry & Failsafe Policies

Every relay node autonomously tracks vital telemetry:
- **Battery Percentage (`battery_percentage`)**:
  - When battery drops below **5%**, the relay halts store-and-forward message ingestion to preserve its remaining power for graceful shutdown.
- **Internal Temperature (`temperature_celsius`)**:
  - Monitored to detect overheating inside sealed tactical transit cases.
- **Storage Consumption (`storage_used_pct`)**:
  - When persistent database/disk storage exceeds **98%**, ingestion is paused to prevent filesystem corruption.
- **Safety Independence**:
  - The relay communications service is **strictly isolated from vehicle and flight control systems**. A software crash or communications blackout can never compromise vehicular steering, engine control, or drone flight safety.

---

## 4. Setting Up a Portable Ground Relay in the Field

### Step 1: Hardware Checklist
- [ ] 1x Apple Silicon Mac mini / MacBook / Linux edge computer (e.g. Raspberry Pi 5).
- [ ] 1x Portable 100Wh+ USB-PD / 12V battery power bank.
- [ ] 1x High-gain 2.4 GHz / 5.8 GHz Wi-Fi access point or Ethernet switch.

### Step 2: Power-Up & Relay Service Launch
```bash
cd "/Users/sabhay/Downloads/PROJECT 13OCT/Final-Project"

# Start the SHADOWLINK gateway bound to all network interfaces
export SHADOWCOMM_HOST="0.0.0.0"
export SHADOWCOMM_PORT="5050"
python3 -m messaging.server --host 0.0.0.0 --port 5050 &

# Start the background delivery worker
python3 -m messaging.worker --interval 1.0 &
```

### Step 3: Inspect Relay Health
Access the operations dashboard or query the REST API:
```bash
curl http://127.0.0.1:5050/api/v1/relays
```
Example response:
```json
[
  {
    "node_id": "relay-ground-01",
    "display_name": "Portable Ground Relay Alpha",
    "node_type": "PORTABLE_GROUND",
    "status": "ONLINE",
    "battery_percentage": 94.5,
    "temperature_celsius": 31.2,
    "storage_used_pct": 15.4,
    "connected_endpoints": ["endpoint-a", "endpoint-b"]
  }
]
```

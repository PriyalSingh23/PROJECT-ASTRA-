# SHADOWLINK FIELD: Field Deployment Guide & Hardware Profiles

**Document Version:** 1.0.0  
**Target Audiences:** Systems Architects, Network Engineers, Field Operations Leads

---

## 1. Deployment Profiles

SHADOWLINK FIELD supports three distinct operational deployment configurations:

```
+-----------------------------------------------------------------------------------------+
|                                    DEPLOYMENT TIERS                                     |
|                                                                                         |
|  [ PROFILE A: DEVELOPER ]        [ PROFILE B: FIELD GATEWAY ]   [ PROFILE C: OPS CENTER]|
|  - macOS / Linux Workstation     - Hardened Edge Computer       - Data Center / Cloud   |
|  - SQLite (WAL Mode)             - Rugged Laptop / Pi 4 (8GB)   - Multi-Node PostgreSQL |
|  - Simulated Transports          - Radio Hardware Interfaces    - TLS 1.3 / OAuth2 / OIDC|
|  - Zero Hardware Required        - Fully Autonomous Offline     - Centralized Auditing  |
+-----------------------------------------------------------------------------------------+
```

---

## 2. Profile B: Autonomous Local Field Gateway

Designed for tactical vehicles, disaster response forward command posts, and remote industrial facilities.

### 2.1 Hardware Requirements
- **Edge Processor**: Quad-core x86_64 or ARM64 (e.g., Intel N100, Core i5, or Raspberry Pi 4 Model B with 8 GB RAM). *Do not deploy on 1 GB or 2 GB models due to memory constraints when running complex FEC and neural model evaluation.*
- **Storage**: Minimum 64 GB NVMe or industrial High-Endurance microSD/eMMC with power-loss protection (pFail).
- **Power**: 12V / 24V DC vehicular power with battery buffer (UPS) to withstand engine cranking voltage drops.
- **Interconnects**:
  - Isolated USB soundcard interface with hardware PTT relay (e.g., SignaLink USB, RIM Lite, or Digirig Mobile).
  - High-speed FTDI USB-to-Serial converter for radio CAT and data lines.
  - Gigabit Ethernet port providing local Wi-Fi bubble access for responders.

### 2.2 Systemd Service Configuration
On Linux edge gateways, the service runs autonomously and restarts on power failure:

```ini
[Unit]
Description=SHADOWLINK FIELD Gateway Service
After=network.target

[Service]
Type=simple
User=fieldops
WorkingDirectory=/opt/shadowlink-field/backend
ExecStart=/usr/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
Environment=SHADOWLINK_ENV=production
Environment=SHADOWLINK_DB_URL=sqlite:////var/lib/shadowlink/shadowlink.db

[Install]
WantedBy=multi-user.target
```

```ini
[Unit]
Description=SHADOWLINK FIELD Background Queue Worker
After=shadowlink-gateway.service

[Service]
Type=simple
User=fieldops
WorkingDirectory=/opt/shadowlink-field/backend
ExecStart=/usr/bin/python3 -m app.services.worker --interval 1.0
Restart=always
RestartSec=5
Environment=SHADOWLINK_ENV=production
Environment=SHADOWLINK_DB_URL=sqlite:////var/lib/shadowlink/shadowlink.db

[Install]
WantedBy=multi-user.target
```

---

## 3. Power Interruption & Recovery Procedures

In tactical deployments, ungraceful power loss (generator refueling, battery exhaustion) is an inevitable operational reality.

### Automated Recovery Mechanism
1. **SQLite WAL Recovery**: On startup, SQLite automatically replays the Write-Ahead Log (`-wal`) and checkpoint journal, guaranteeing zero database file corruption.
2. **Stale Lease Reclamation**: If a worker process was abruptly terminated during a dispatch, the recovery service discovers messages in `SENDING` whose lease has elapsed (`lease_expires_at < utcnow()`). These are transitioned back to `FAILED_RETRYABLE` and queued for re-dispatch.
3. **Client-Side Resynchronization**: Client devices retain their pending outboxes in IndexedDB and re-sync without operator intervention once the gateway boots.

---

## 4. Safe Operator Shutdown

To shut down a field gateway safely:
```bash
# 1. Stop background worker to allow active dispatches to finish
sudo systemctl stop shadowlink-worker

# 2. Stop API server
sudo systemctl stop shadowlink-gateway

# 3. Flush disk writes and sync
sync
sudo poweroff
```

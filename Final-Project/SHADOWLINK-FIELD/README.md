# SHADOWLINK FIELD
### Resilient Communications, Offline Messaging, and Approved Radio Interoperability Platform

[![License: Proprietary / Operational](https://img.shields.io/badge/License-Field%20Operations-blue.svg)](LICENSE)
[![Platform: macOS / Linux Edge](https://img.shields.io/badge/Platform-macOS%20%7C%20Linux%20Edge-success.svg)](docs/FIELD_DEPLOYMENT.md)
[![Test Suite: 100% Passed](https://img.shields.io/badge/Tests-100%25%20Passed-brightgreen.svg)](tests/)

---

## 1. Overview

**SHADOWLINK FIELD** is an operational communications management and radio interoperability platform engineered for mission-critical operations when cellular, satellite, and internet infrastructure is degraded, severed, or intentionally jammed.

Evolved from the ShadowComm LPI-CGAN research repository (`Final-Project`), SHADOWLINK FIELD decouples operational message handling from experimental radio physics. It provides guaranteed store-and-forward messaging, durable-receipt acknowledgements, client-side offline persistence, strict receiver deduplication, and a common adapter interface for commercial, tactical, and experimental communication systems.

```
+-----------------------------------------------------------------------------------------+
|                                  SHADOWLINK FIELD ARCHITECTURE                          |
|                                                                                         |
|  +--------------------+         +------------------------+                              |
|  | Modern PWA Frontend| <=====> |   FastAPI Core Engine  | <=====> [ SQLite (WAL) ]     |
|  | (React+TS+Tailwind)|  HTTPS  |   (Auth, RBAC, Queue)  |                              |
|  +--------------------+  / WSS  +-----------+------------+                              |
|                                             |                                           |
|                                             v                                           |
|                                 +------------------------+                              |
|                                 | Background Delivery    |                              |
|                                 | Queue Worker Process   |                              |
|                                 +-----------+------------+                              |
|                                             |                                           |
|                   +-------------------------+-------------------------+                 |
|                   |                         |                         |                 |
|         +---------v---------+     +---------v---------+     +---------v---------+       |
|         | SIMULATION LINK   |     | MOTOROLA GATEWAY  |     | STAR-V ADAPTER    |       |
|         | - Config Loss/Cut |     | - Audio/PTT & Data|     | - Safety Interlock|       |
|         +-------------------+     +-------------------+     +-------------------+       |
|                                             |                                           |
|                                   +---------v---------+                                 |
|                                   | SDR RESEARCH (v4) |                                 |
|                                   | - Software Mode   |                                 |
|                                   +-------------------+                                 |
+-----------------------------------------------------------------------------------------+
```

---

## 2. Key Capabilities

1. **Persistent Offline Message Engine**: Messages persist to disk before delivery attempts. Survives application, worker, and machine reboots.
2. **Client-Side Outbox (IndexedDB)**: Operators compose and queue messages offline in the browser. Synchronizes automatically upon reconnect.
3. **Honest Delivery Tracking**: Explicit 12-state machine. A message is `DELIVERED` only upon receipt of a verified durable acknowledgement (ACK).
4. **Receiver Deduplication**: Receiver stores exactly one copy in the inbox and regenerates the canonical receipt for retries.
5. **Configurable Retry & Expiry**: Exponential backoff with random jitter ($\min(60, 2^{\text{att}} \times 2) + \text{jitter}$), classification of retryable vs. permanent errors, and TTL expiry.
6. **Common Adapter Interface (`ICommunicationAdapter`)**:
   - **Simulation Adapter**: In-memory channel with artificial delay, packet loss, ACK loss, and link cut simulation.
   - **Motorola Adapter**: Profile-driven architecture supporting Audio/PTT GPIO keying and documented digital data services.
   - **STAR-V Adapter**: Feasibility safety stub permanently locked out until authorized documentation is provided.
   - **SDR Research Adapter**: Segregated software-only execution of `lpi_v4/` LPI-CGAN models without RF radiation.
7. **Security & RBAC**: PBKDF2 password hashing, JWT sessions, role enforcement (`ADMIN`, `OPERATOR`, `OBSERVER`), and sanitized audit logging.
8. **Responsive PWA UI**: High-contrast, low-light field console with Dashboard, Message Center, Adapter Management, and Diagnostics.

---

## 3. Quickstart (macOS / Linux)

### Prerequisites
- Python 3.12+
- Node.js 18+ and npm

### Terminal 1: Launch Backend API Server
```bash
cd SHADOWLINK-FIELD/backend
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
API Documentation & Health Check: **http://127.0.0.1:8000/docs**

### Terminal 2: Launch Queue Delivery Worker
```bash
cd SHADOWLINK-FIELD/backend
python3 -m app.services.worker --interval 1.0
```

### Terminal 3: Launch Frontend Console
```bash
cd SHADOWLINK-FIELD/frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```
Open Console: **http://127.0.0.1:5173**

---

## 4. Automated Testing

Run the full automated test suite (Unit, Integration, Simulation, and Adapter Contracts):

```bash
cd SHADOWLINK-FIELD
pytest tests/ -v
```

---

## 5. Documentation Directory

- [Repository Audit (`docs/REPOSITORY_AUDIT.md`)](docs/REPOSITORY_AUDIT.md)
- [System Architecture (`docs/ARCHITECTURE.md`)](docs/ARCHITECTURE.md)
- [Feature Traceability Matrix (`docs/FEATURE_TRACEABILITY.md`)](docs/FEATURE_TRACEABILITY.md)
- [Message Protocol (`docs/MESSAGE_PROTOCOL.md`)](docs/MESSAGE_PROTOCOL.md)
- [Security Model (`docs/SECURITY_MODEL.md`)](docs/SECURITY_MODEL.md)
- [Motorola Integration (`docs/MOTOROLA_INTEGRATION.md`)](docs/MOTOROLA_INTEGRATION.md)
- [STAR-V Feasibility (`docs/STARV_FEASIBILITY.md`)](docs/STARV_FEASIBILITY.md)
- [SDR Integration (`docs/SDR_INTEGRATION.md`)](docs/SDR_INTEGRATION.md)
- [macOS Setup Guide (`docs/MACOS_SETUP.md`)](docs/MACOS_SETUP.md)
- [Field Deployment Guide (`docs/FIELD_DEPLOYMENT.md`)](docs/FIELD_DEPLOYMENT.md)
- [Acceptance Test Plan (`docs/ACCEPTANCE_TEST_PLAN.md`)](docs/ACCEPTANCE_TEST_PLAN.md)
- [Operations Guide (`docs/OPERATIONS_GUIDE.md`)](docs/OPERATIONS_GUIDE.md)
- [Troubleshooting & Diagnostics (`docs/TROUBLESHOOTING.md`)](docs/TROUBLESHOOTING.md)
- [Implementation Status (`docs/IMPLEMENTATION_STATUS.md`)](docs/IMPLEMENTATION_STATUS.md)

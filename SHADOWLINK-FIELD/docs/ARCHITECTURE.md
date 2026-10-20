# SHADOWLINK FIELD: Architectural Specification

## 1. System Vision & Objectives

**SHADOWLINK FIELD** is a resilient communication, offline messaging, and radio interoperability management platform. It addresses the practical challenge of coordinating emergency response, industrial field teams, and tactical personnel when cellular and satellite networks are degraded, intermittent, or completely severed.

The platform treats radio hardware as an external, capability-constrained service accessed strictly via approved, authenticated adapters. It provides dependable message persistence, honest delivery state tracking, end-to-end auditability, and diagnostics without assuming guaranteed RF propagation or permanent network availability.

---

## 2. Global Architecture Diagram

```
+---------------------------------------------------------------------------------------------------+
|                                     OPERATOR CLIENT TIER                                          |
|                                                                                                   |
|  +---------------------------------------------------------------------------------------------+  |
|  |                React 18 / TypeScript / Vite / Tailwind CSS / PWA Shell                      |  |
|  |                                                                                             |  |
|  |  +-------------------+  +-------------------+  +-------------------+  +-------------------+ |  |
|  |  | Dashboard Console |  |  Message Center   |  | Gateway & Devices |  | Audit & Analytics | |  |
|  |  +-------------------+  +-------------------+  +-------------------+  +-------------------+ |  |
|  |                                                                                             |  |
|  |  +---------------------------------------------------------------------------------------+  |  |
|  |  |                     Client Local Outbox & Sync Manager (IndexedDB)                    |  |  |
|  |  +---------------------------------------------------------------------------------------+  |  |
|  +---------------------------------------------------------------------------------------------+  |
+-----------------------------------------------|---------------------------------------------------+
                                                | HTTPS / REST / WebSockets
+-----------------------------------------------v---------------------------------------------------+
|                                      BACKEND CORE SERVICE (FastAPI)                                |
|                                                                                                   |
|  +---------------------------------------------------------------------------------------------+  |
|  | REST Routing & Middleware: CORS, Request Tracing, Rate Limiting, JWT Auth & RBAC Check      |  |
|  +---------------------------------------------------------------------------------------------+  |
|                                                                                                   |
|  +---------------------+  +---------------------+  +---------------------+  +------------------+  |
|  |  Identity & Auth    |  |   Message Engine    |  |   Delivery Queue    |  | Audit & Events   |  |
|  | (Users, Roles, Keys)|  | (Idempotency, Acks) |  | (Backoff, Retries)  |  | (Safe Metadata)  |  |
|  +---------------------+  +---------------------+  +---------------------+  +------------------+  |
|                                                                                                   |
|  +---------------------------------------------------------------------------------------------+  |
|  |                        Persistence Tier: SQLAlchemy 2.0 (SQLite / PostgreSQL)               |  |
|  |     [Users] [Devices] [Messages] [Inbox] [DeliveryAttempts] [Acknowledgements] [AuditLogs]   |  |
|  +---------------------------------------------------------------------------------------------+  |
|                                                                                                   |
|  +---------------------------------------------------------------------------------------------+  |
|  |                             COMMON ADAPTER INTERFACE (ICommunicationAdapter)                 |  |
|  |   - Capability Discovery  - Health Checks  - Config Validation  - Structured Error Reporting|  |
|  +---------------------------------------------------------------------------------------------+  |
+--------------------|----------------------------|---------------------------|---------------------+
                     |                            |                           |
+--------------------v------+     +---------------v-----------+     +---------v---------------------+
|   SIMULATION ADAPTER      |     | MOTOROLA GATEWAY ADAPTER  |     |   STAR-V GATEWAY ADAPTER      |
|  - In-memory delay/loss   |     |  - Exact Profile Config   |     |  - Disabled Feasibility Stub  |
|  - Deterministic faults   |     |  - PTT/Audio Interop      |     |  - Prerequisite Safety Checks |
|  - Channel degradation    |     |  - Documented Data APIs   |     |  - Hardware Guard Interlocks  |
+---------------------------+     +---------------------------+     +-------------------------------+
                                                  |
                                  +---------------v-----------+
                                  |    SDR RESEARCH ADAPTER   |
                                  |  - LPI-CGAN Neural Models |
                                  |  - Software Research Mode |
                                  |  - Isolated USRP Path     |
                                  +---------------------------+
```

---

## 3. Layered Design

### 3.1 Client Tier (Frontend)
- **Framework**: React 18 with TypeScript and Vite for rapid, deterministic packaging.
- **Styling**: Tailwind CSS with an accessible, high-contrast dark theme optimized for low-light field conditions.
- **Offline Durability**: Local state managed in IndexedDB. Outgoing drafts and queued dispatches are committed to disk before network requests are attempted.
- **Live State Updates**: Real-time message status, queue statistics, and adapter health updates stream over WebSockets with automatic reconnection.

### 3.2 Service Tier (Backend)
- **Framework**: FastAPI (Python 3.12) running under Uvicorn.
- **Data Validation**: Pydantic v2 schemas providing strict input sanitization, type enforcement, and payload bounds checking.
- **Database Layer**: SQLAlchemy 2.0 ORM configured with SQLite Write-Ahead Logging (`PRAGMA journal_mode=WAL`) and 5000ms busy timeout for local edge single-node gateways, completely compatible with PostgreSQL for centralized operations.
- **Background Tasks**: Delivery workers execute out-of-band to prevent blocking HTTP endpoints during slow radio dispatches or backoff waits.

---

## 4. Common Adapter Interface (`ICommunicationAdapter`)

All communications hardware and virtual links must implement `ICommunicationAdapter`:

```python
class ICommunicationAdapter(ABC):
    @abstractmethod
    def get_metadata(self) -> AdapterMetadata:
        """Returns identity, version, vendor, and transport category."""
        ...

    @abstractmethod
    def get_capabilities(self) -> List[AdapterCapability]:
        """Discovers supported capabilities (e.g., PTT_AUDIO, DIGITAL_DATA, ACK_CONFIRMATION)."""
        ...

    @abstractmethod
    async def check_health(self) -> AdapterHealthReport:
        """Runs non-transmitting self-test and reports component readiness."""
        ...

    @abstractmethod
    async def validate_config(self, config: Dict[str, Any]) -> ValidationResult:
        """Validates configuration parameters prior to arming or connection."""
        ...

    @abstractmethod
    async def transmit(self, message: OutgoingMessagePayload) -> TransmissionResult:
        """Attempts message transmission according to adapter capabilities."""
        ...

    @abstractmethod
    async def cancel(self, correlation_id: str) -> CancellationResult:
        """Safely terminates in-flight operations if supported."""
        ...
```

### Capability Discovery Protocol
An adapter declares its exact operational envelope. The UI queries these capabilities dynamically:
- `PTT_AUDIO_VOICE`: The UI shows operator PTT status and audio controls, but hides digital packet composition.
- `DIGITAL_PACKET_DATA`: The UI enables text, telemetry, and structured status reports.
- `HARDWARE_ACK`: The engine expects and validates link-layer acknowledgements.
- `NO_ACK_SIMPLEX`: The engine informs the operator that delivery cannot be automatically confirmed.

---

## 5. Security & Authentication Architecture

1. **Role-Based Access Control (RBAC)**:
   - `ADMIN`: User management, device configuration, adapter arming, audit export.
   - `OPERATOR`: Message composition, transport selection, manual retry, PTT voice coordination.
   - `OBSERVER`: Read-only dashboard view, delivery tracking, report viewing.
2. **Session Security**:
   - Cryptographically signed JWT tokens with 15-minute expirations and automatic refresh tokens.
   - Passwords hashed using Argon2id or PBKDF2-HMAC-SHA256 with 600,000 iterations.
3. **Audit Log Safeguards**:
   - Diagnostic event streams strictly redact message payloads, secret keys, password hashes, and tokens.
   - Every system configuration change, adapter connection, and transmission is permanently logged with user ID, device ID, and timestamp.
4. **Transport Isolation**:
   - Experimental SDR code cannot trigger USRP transmissions unless specifically armed by an `ADMIN` role with confirmed regulatory authorization.

---

## 6. Deployment Profiles

- **Profile A: Developer (macOS / Linux)**:
  - Local FastAPI backend + SQLite in WAL mode.
  - Vite dev server or statically served SPA.
  - Simulated transport links for 100% hardware-free test execution.
- **Profile B: Local Field Gateway (Edge Linux / Raspberry Pi 4 / Toughbook)**:
  - Docker Compose or native Systemd unit.
  - Dedicated persistent SQLite / PostgreSQL database.
  - Connected radio accessory interfaces (e.g., audio/PTT USB interface, serial CAT control).
  - Web interface accessible to field laptops over a hardened local Wi-Fi / Ethernet bubble.
- **Profile C: Managed Multi-User Operations Center**:
  - Multi-node high-availability deployment behind reverse proxy with TLS 1.3.
  - Centralized PostgreSQL and distributed Redis queue.
  - Centralized audit ingestion and disaster recovery replication.

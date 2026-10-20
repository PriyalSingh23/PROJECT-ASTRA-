# SHADOWLINK FIELD: Standard Operating Procedures (SOP)

**Manual Reference:** SOP-SLF-01  
**Target:** Radio Operators, Incident Dispatchers, Field Technicians

---

## 1. Operating Procedures

### 1.1 Logging In & Verifying System Readiness
1. Open the local gateway URL in your browser: `http://<gateway-ip>:8000` or `http://localhost:5173`.
2. Sign in using your operator credentials:
   - Default Field Admin: `admin` / `FieldOps@2026!`
   - Default Operator: `operator` / `TacticalOps@2026!`
3. Verify the **Dashboard Header**:
   - Gateway Health: **GREEN / READY**
   - Active Adapter: Ensure the intended transport is active (e.g. `SIMULATION (ONLINE)` or `MOTOROLA GATEWAY`).
   - If an adapter shows **AMBER / UNCONFIGURED** or **RED / LOCKOUT**, contact your technical administrator.

### 1.2 Composing & Sending a Message
1. Navigate to the **Message Center**.
2. Select the **Destination Endpoint** from the dropdown menu (e.g., `Endpoint Bravo - Incident Command`).
3. Set the **Operational Priority**:
   - `Routine (1)`: Non-time-critical status and log reports.
   - `Standard (2)`: General operational messages.
   - `Priority (3)`: Urgent tactical updates.
   - `Flash (5)`: Life-safety or emergency incident declarations.
4. Enter your message text. Keep tactical messages concise to minimize RF channel occupancy.
5. Click **DURABLY ENQUEUE & SEND**.
6. **Delivery Verification**:
   - The message immediately shows as `LOCAL_QUEUED` &rarr; `QUEUED`.
   - Once the background worker dispatches across the link, it transitions to `SENDING`.
   - The message reaches `DELIVERED` **only after the receiver stores the packet and returns a durable receipt**.
   - If an ACK is delayed, the status shows `AWAITING_ACK`.

### 1.3 Handling Failed Messages & Retries
- If the transport link is interrupted, the message automatically enters `FAILED_RETRYABLE` and schedules exponential backoff retries.
- To force an immediate retry (e.g., when you know line-of-sight has been re-established), click the **RETRY** button on the message card.
- To cancel an unneeded pending message, click **CANCEL**.

### 1.4 Inspecting Audit Events
1. Click **TIMELINE** on any message card.
2. Review the immutable audit history:
   - Enqueue timestamp
   - Worker lease acquisition
   - Transmission attempt number and transport state
   - Receiver inbox commit confirmation
   - ACK arrival timestamp

---

## 2. Emergency Outage Operations

When all satellite, microwave, and cellular connections fail:
1. **Local Operation Continues Uninterrupted**: The local gateway operates completely independently of the public internet.
2. **Local Mesh/Wi-Fi Access**: Responders within range of the vehicle or command post can access the web application over local Wi-Fi or Ethernet.
3. **Store-and-Forward**: If the receiving radio station is out of range, messages remain securely stored in the local SQLite queue and will deliver automatically once communications are restored.

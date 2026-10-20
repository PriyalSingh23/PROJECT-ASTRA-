# Phase 3: Fault Injection, Offline Outages & Client Re-Sync - Context

**Gathered:** 2026-10-19  
**Status:** Ready for planning  

<domain>
## Phase Boundary

Phase 3 validates and delivers store-and-forward resilience across severed connections, latency, packet drops, client IndexedDB syncing, duplicate submission prevention, and worker crash recovery. 

This phase covers:
- Dynamic RF channel impairment injection (outage toggle, latency, packet drop, ACK loss, single-shot fault arming) via UI and REST API.
- Browser offline outbox in IndexedDB (`shadowcomm_outbox_db`) with automatic background sync, manual flush triggers, and multi-tab Web Lock coordination.
- Strict client idempotency (`client_idempotency_key`) deduplication, rapid multi-click protection, and seamless reconciliation.
- Worker lease reclamation, crash simulation, exponential backoff telemetry HUD with countdowns, and permanent retry limit exhaustion overrides.

New capabilities outside fault injection, offline persistence, idempotency, and retry recovery belong in subsequent phases (Phase 4: Multi-Transport Broker, Phase 5: SDR Layer).
</domain>

<decisions>
## Implementation Decisions

### 1. Fault Injection & Channel Impairment Controls (FLT-01)
- **D-01:** Tactical Quick-Select Presets in ConnectivityView — Provide quick-select preset buttons ("Nominal Clear Link", "Urban EW Jamming [30% Drops]", "Severed Air-Gap Outage", "GEO Satellite [800ms Latency]") alongside fine-tuning sliders for latency, message drop rate, and ACK drop rate.
- **D-02:** Illuminated 3D Status Pill in Navigation Header & Station Banners — Render an illuminated 3D status pill (Amber "CHANNEL IMPAIRED [25% LOSS]" or Red "LINK SEVERED") in `Header.tsx` and `MessagesView.tsx` station banners with a direct one-click shortcut to Connectivity controls.
- **D-03:** Quick Action Arming Buttons for Targeted Fault Injection — Provide quick action arming buttons in `ConnectivityView.tsx` ("Arm Drop Next Message", "Arm Drop Next ACK", "Arm Corrupt Next HMAC") displaying active armed chips until triggered by the next message transmission.
- **D-04:** Tactical One-Click Link Restoration — Global "Restore Clean Link" action available in both `ConnectivityView.tsx` and `MessagesView.tsx` header that instantly resets transport simulation to nominal 0ms latency and 0% drop conditions.
- **D-18:** Tactical Audio Cues & Radar Animation — Synthesized Web Audio radio squelch/beep on link sever/restore (toggleable in Header) plus glowing 3D radar sweep line.

### 2. Browser Offline Queue & IndexedDB Sync UX (FLT-02)
- **D-05:** Distinct 3D Local Outbox Card in Message Feed — Render locally buffered messages from browser IndexedDB (`shadowcomm_outbox_db`) with a distinct 3D card styling, amber pulsing border, physical IndexedDB storage badge, and "PENDING SYNC" indicator directly in the feed.
- **D-06:** Persistent Tactical Outbox Badge in Station Columns & Header — Provide a persistent tactical outbox badge (e.g. `📦 3 LOCAL QUEUED`) in `Header.tsx` and `StationConsoleColumn.tsx` headers displaying the count of unsynced messages with an instant click-to-flush trigger.
- **D-07:** Automatic Background Flush with Manual Flush Trigger Option — Automatically flush buffered IndexedDB messages in the background upon connection recovery with real-time state transitions (`LOCAL_PENDING` -> `QUEUED`), backed by a manual "Flush Local Outbox Now" CTA button.
- **D-08:** Air-Gap Composer Adaptation with Live RF Budget HUD — Keep the composer fully functional when disconnected; dynamically adapt the submit button label to "Store Locally (Offline Outbox)" and keep all RF Budget calculations (Raw Bytes, GCM Envelope, RS Codewords, Burst Airtime) live.
- **D-17:** Multi-Tab Web Lock & BroadcastChannel Sync Coordination — Multi-tab synchronization using Web Locks API (`navigator.locks.request('shadowcomm_outbox_sync')`) to elect a single flush leader tab, with secondary tabs updated via `BroadcastChannel` with zero race conditions.
- **D-19:** Dual Timestamp Display — Chronological ordering by original composition time, with both "Composed" and "Server Queued" microsecond timestamps rendered on cards and in the Telemetry Drawer.
- **D-21:** Explicit Storage Persistence & Safe Ceiling — Request `navigator.storage.persist()` on app boot, enforce a 500-message buffer limit, and trigger an amber alert when buffered messages exceed 400.

### 3. Idempotency & Duplicate Prevention Feedback (FLT-03)
- **D-09:** Tactical Toast & Card Highlight on Duplicate Submission — When a submission returns HTTP 200 (`is_new: false`), display a tactical confirmation toast ("Deduplicated: Existing record returned"), smoothly highlight the existing card with cyan glow, and prevent duplicate card insertion into the feed.
- **D-10:** Dedicated Idempotency Seal in Telemetry Drawer — Render a dedicated "IDEMPOTENCY SEAL" chip in `MessageTelemetryDrawer.tsx` displaying the `client_idempotency_key` UUID and a "DEDUPLICATION SAFE" integrity badge.
- **D-11:** Immediate Client-Side Debounce & Single-UUID Key Locking — Disable the Transmit CTA immediately upon click, display an animated spinner, and lock a single unique `client_idempotency_key` UUID per draft to eliminate accidental double-click race conditions.
- **D-12:** Seamless Offline Sync Idempotency Reconciliation — When flushing IndexedDB items, if the server already received the message earlier, seamlessly bind to the server record, remove the local IndexedDB item, and update UI state without throwing an error.

### 4. Worker Crash Recovery & Retry Visualization (FLT-04)
- **D-13:** Illuminated Timeline Node in MessageTelemetryDrawer — Render an illuminated stepped event node in the timeline labeled "WORKER LEASE RECLAIMED" with amber glow, previous worker ID, and expiration timeout.
- **D-14:** Active Retry Telemetry HUD — Render an active Retry Telemetry badge on message cards and drawer ("Attempt N/5 • Next retry in X.Xs [Backoff + Jitter]") with real-time countdown.
- **D-15:** Tactical Crash & Reclaim Controls in ConnectivityView — Expose "Simulate Worker Crash (Abort Lease)" and "Trigger Immediate Stale Lease Reclamation" buttons in `ConnectivityView.tsx`.
- **D-16:** Permanent Failure Re-Queue Action — Distinct Red 3D Card (`FAILED_PERMANENT`) with "Retry Limit Exhausted [5/5]" badge and a manual "Force Re-Queue Transmission" operator action.
- **D-20:** Dual-Profile Backoff Tuning — Expose a dual-profile preset toggle in `ConnectivityView.tsx` ("Demo Fast Retries: 0.5s base, 5s max" vs "Tactical Field: 2s base, 60s max") with live backoff HUD.
- **D-22:** Immediate Startup Scan & Recovery — Backend server/worker startup executes an instant startup sweep resetting stranded in-flight `SENDING` messages to `FAILED_RETRYABLE` for immediate dispatch.

### the agent's Discretion
- Exact styling details for the Web Audio synthesized squelch (frequency, duration ~60ms) and volume ceiling.
- Specific animation keyframes for the glowing radar sweep line in `ConnectivityView.tsx`.
- Exact CSS classes for the amber pulsing border on `LOCAL_PENDING` outbox cards.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Transport & Fault Simulation
- `Final-Project/messaging/transport.py` — `SimulatedTransport` class, online/offline toggling, latency, message/ACK drop rates, deterministic fault injection.
- `Final-Project/messaging/api.py` § `/sim/transport`, `/sim/fault` — REST endpoints for querying and updating simulation parameters.

### Retry Policy & Worker Crash Recovery
- `Final-Project/messaging/retry_policy.py` — `RetryPolicy.compute_next_attempt_at()`, `check_and_apply_expiry()`, and `reclaim_stale_leases()`.
- `Final-Project/messaging/worker.py` — `QueueWorker` lease acquisition, execution loop, and error handling.
- `Final-Project/messaging/state_machine.py` — `MessageState` enum and transition matrix.

### Client Storage & View Components
- `Final-Project/frontend/src/services/outboxDb.ts` — `OutboxDatabase` IndexedDB wrapper (`shadowcomm_outbox_db`, `local_messages`).
- `Final-Project/frontend/src/components/ConnectivityView.tsx` — Impairment simulator UI, network vector status cards.
- `Final-Project/frontend/src/components/MessagesView.tsx` — Adaptive dual-station console, polling loop, outbox submission flow.
- `Final-Project/frontend/src/components/MessageTelemetryDrawer.tsx` — Slide-out 4-stage event timeline and cryptographic seal chips.
- `Final-Project/frontend/src/components/StationConsoleColumn.tsx` — Column feed, quick composer, and tactical RF budget HUD.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `outboxDb` (`Final-Project/frontend/src/services/outboxDb.ts`): Fully implemented IndexedDB wrapper for `LocalOutboxItem` supporting `saveMessage`, `getAllMessages`, `updateSyncStatus`, and `deleteMessage`.
- `SimulatedTransport` (`Final-Project/messaging/transport.py`): Singleton transport supporting `set_online`, `set_latency`, `set_drop_rate`, `set_ack_drop_rate`, `drop_message`, `drop_ack`, `inject_fault`, and `get_status`.
- `RetryPolicy` (`Final-Project/messaging/retry_policy.py`): Implements exponential backoff calculation with jitter and stale lease reclamation across `SENDING` messages.
- `MessageTelemetryDrawer.tsx`: Ready to host the `WORKER_LEASE_RECLAIMED` node, retry attempt telemetry HUD, and idempotency seal chip.

### Established Patterns
- OpenBLAS Safety: macOS Apple Silicon requires `import torch` to precede `numpy` and `scipy` in Python files.
- Tactical C2 3D Aesthetic: Dark background (`#0B0F17`), directional shadows (`shadow-[0_4px_20px_rgba(...)]`), cyan/emerald station colorways, glowing telemetry pills.
- State Preservation: Parent `MessagesView.tsx` holds composer drafts to prevent wiping input across layout or network state shifts.

### Integration Points
- REST Endpoints:
  - `GET /api/v1/sim/transport` & `POST /api/v1/sim/transport`
  - `POST /api/v1/sim/fault`
  - `POST /api/v1/messages` (with `client_idempotency_key` returning 201 for new, 200 for idempotent duplicate)
  - `POST /api/v1/worker/reclaim` (triggering stale lease reclamation)
- Frontend Services:
  - `api.updateSimTransport()` & `api.injectFault()` in `Final-Project/frontend/src/services/api.ts`
  - `outboxDb` in `Final-Project/frontend/src/services/outboxDb.ts`
</code_context>

<specifics>
## Specific Ideas
- "Tactical Audio Squelch": Synthesize a subtle 60ms click/chirp using `window.AudioContext` on link sever/restore so operators get instant sensory feedback.
- "Radar Sweep": A linear-gradient radar sweep across the Virtual RF Transport card when active.
- "Double-click Lockout": Button immediately disables and enters submitting spinner, guaranteeing only one network call per user click.
</specifics>

<deferred>
## Deferred Ideas
- Multi-hop ad-hoc mesh routing protocol across > 5 mobile endpoints (Deferred to v2, V2-01).
- Live hardware over-the-air RF broadcast on physical Motorola APX radios (Deferred to v2, V2-02).
- Post-Quantum Cryptography (ML-KEM / Kyber) hybrid key encapsulation (Deferred to v2, V2-04).
</deferred>

---

*Phase: 03-fault-injection-offline-outages-client-re-sync*  
*Context gathered: 2026-10-19*  

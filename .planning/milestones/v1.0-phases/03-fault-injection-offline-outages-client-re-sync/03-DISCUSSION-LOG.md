# Phase 3: Fault Injection, Offline Outages & Client Re-Sync - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-19  
**Phase:** 03-fault-injection-offline-outages-client-re-sync  
**Areas discussed:** Fault Injection & Channel Impairment Controls, Browser Offline Queue & IndexedDB Sync UX, Idempotency & Duplicate Prevention Feedback, Worker Crash Recovery & Retry Visualization, Multi-Tab Concurrency, Tactical Audio/Visual Telemetry, Timestamp Reconciliation, Backoff Tuning, IndexedDB Quotas, Server Reboot Recovery  

---

## 1. Impairment Presets & Sliders (FLT-01)

| Option | Description | Selected |
|---|---|:---:|
| Tactical Quick-Select Presets | Presets ("Nominal Clear Link", "Urban EW Jamming [30% Drops]", "Severed Air-Gap Outage", "GEO Satellite [800ms Latency]") with fine-tuning sliders | ✓ |
| Granular Sliders Only | Keep existing manual sliders for latency and drop probabilities without preset buttons | |
| Dynamic Fluctuating Profiles | Automated background fluctuation simulating moving vehicles | |

**User's choice:** Tactical Quick-Select Presets with fine-tuning sliders.  
**Notes:** Provides rapid demonstration capability while allowing granular control.

---

## 2. Degraded Channel Alerting in Console (FLT-01)

| Option | Description | Selected |
|---|---|:---:|
| Illuminated 3D Status Pill | Header & Station Banners (Amber "CHANNEL IMPAIRED [25% LOSS]" or Red "LINK SEVERED") with one-click shortcut to Connectivity controls | ✓ |
| Modal Alert Dialog | Pop up a warning dialog whenever an operator attempts to transmit while degraded | |
| Subtle RF Budget HUD Note | Display status only inside StationConsoleColumn RF budget telemetry line | |

**User's choice:** Illuminated 3D Status Pill in Header & Station Banners.  
**Notes:** Gives immediate operator awareness without interrupting workflow.

---

## 3. Targeted Single-Shot Fault Injection (FLT-01)

| Option | Description | Selected |
|---|---|:---:|
| Quick Action Arming Buttons | ConnectivityView ("Arm Drop Next Message", "Arm Drop Next ACK", "Arm Corrupt Next HMAC") showing active armed state chips | ✓ |
| Composer Test Flags | Toggle directly inside StationConsoleColumn quick composer | |
| Automated Chaos Injector | Toggleable background chaos monkey that randomly injects intermittent drops | |

**User's choice:** Quick Action Arming Buttons in ConnectivityView.  
**Notes:** Clean separation of testing tools while showing clear armed feedback.

---

## 4. One-Click Link Restoration (FLT-01)

| Option | Description | Selected |
|---|---|:---:|
| Tactical "Restore Clean Link" Button | Global button in ConnectivityView and MessagesView header resetting to 0ms / 0% drop | ✓ |
| Dedicated Reset Control in ConnectivityView Only | Strict isolation to Connectivity tab | |
| Auto-Recovery Timer | Automatically recovers to nominal state after configurable duration | |

**User's choice:** Tactical "Restore Clean Link" button in both views.  
**Notes:** Rapid reset saves time during demos and testing.

---

## 5. Local Outbox Card Presentation (FLT-02)

| Option | Description | Selected |
|---|---|:---:|
| Distinct 3D "LOCAL OUTBOX" Card | Amber pulsing border, physical IndexedDB storage badge, and "PENDING SYNC" indicator in feed | ✓ |
| Standard Outbox Card | Subtle clock icon and state pill labeled "OFFLINE QUEUED" | |
| Separate Dedicated "Offline Drawer" | Isolates locally buffered messages from main feed | |

**User's choice:** Distinct 3D "LOCAL OUTBOX" Card directly in the feed.  
**Notes:** Maintains full chronological context while visually differentiating local browser storage from server SQLite storage.

---

## 6. Local Outbox Counter & Alerting (FLT-02)

| Option | Description | Selected |
|---|---|:---:|
| Persistent Tactical Outbox Badge | Header & Station Columns (e.g. "📦 3 LOCAL QUEUED") with instant click-to-flush trigger | ✓ |
| Toast Notification | Popping up only when offline messages are added or flushed | |
| Composer-Only Indicator | Shows pending local outbox count next to transmit button only | |

**User's choice:** Persistent Tactical Outbox Badge with instant click-to-flush.  
**Notes:** Clear visual accountability for offline buffered data.

---

## 7. Offline Queue Flush Strategy (FLT-02)

| Option | Description | Selected |
|---|---|:---:|
| Automatic Background Flush with Manual Trigger | Automatic sync on link recovery with real-time state transitions, plus manual "Flush Local Outbox Now" button | ✓ |
| Manual Flush Approval Dialog | Prompt operator before dispatching | |
| Automatic Silent Flush | No manual trigger or prompt | |

**User's choice:** Automatic Background Flush with Manual Trigger option.  
**Notes:** Best of both worlds: zero-friction auto-sync plus operator on-demand control.

---

## 8. Offline Composer Behavior (FLT-02)

| Option | Description | Selected |
|---|---|:---:|
| Full Composer with Adaptive Label | Button adapts to "Store Locally (Offline Outbox)", RF Budget HUD remains live | ✓ |
| Standard Label with Amber Toast | Standard CTA label, toast confirms IndexedDB storage | |
| Read-Only Composer | Disables input while disconnected | |

**User's choice:** Full Composer with Adaptive Label and live RF Budget HUD.  
**Notes:** Embraces true store-and-forward offline-first operations.

---

## 9. Idempotency Re-Submission Feedback (FLT-03)

| Option | Description | Selected |
|---|---|:---:|
| Tactical Toast & Card Glow | Display "Deduplicated: Existing record returned", highlight existing card with cyan glow, avoid duplicate cards | ✓ |
| Modal Alert Dialog | Explicit popup informing operator of duplicate | |
| Silent Reconciliation | Return existing message without visual indication | |

**User's choice:** Tactical Toast & Card Glow.  
**Notes:** Immediately reassures operator that submission was recognized without cluttering feed.

---

## 10. Idempotency Key in Telemetry Drawer (FLT-03)

| Option | Description | Selected |
|---|---|:---:|
| Dedicated "IDEMPOTENCY SEAL" Chip | In drawer header with copyable client key UUID and "DEDUPLICATION SAFE" checkmark | ✓ |
| Raw JSON Inspector Only | Keep idempotency key inside collapsible raw event viewer | |
| Omit from Drawer | Focus purely on leases, inboxes, and receipts | |

**User's choice:** Dedicated "IDEMPOTENCY SEAL" chip in drawer header.  
**Notes:** Establishes cryptographic proof of client-side deduplication.

---

## 11. Double-Submission Guard on CTA (FLT-03)

| Option | Description | Selected |
|---|---|:---:|
| Immediate Client-Side Lockout | Disables on click with spinner, locking single UUID per draft | ✓ |
| Permissive Click with Server Dedup | Rely on backend HTTP 200 deduplication to filter rapid clicks | |
| Hold-to-Transmit Button | 500ms long-press required | |

**User's choice:** Immediate Client-Side Lockout.  
**Notes:** Prevents unnecessary network traffic and client-side race conditions.

---

## 12. Offline Sync Idempotency Reconciliation (FLT-03)

| Option | Description | Selected |
|---|---|:---:|
| Seamless Reconciliation | Bind to server record, remove local IndexedDB item, update card state without error | ✓ |
| Operator Warning Toast | Alert operator that duplicate was reconciled and dropped | |
| Preserve in Local History | Keep duplicate in IndexedDB marked as "DUPLICATE_SERVER_SYNCED" | |

**User's choice:** Seamless Reconciliation.  
**Notes:** Clean, robust state transition with zero operator intervention.

---

## 13. Lease Reclamation in Telemetry Drawer (FLT-04)

| Option | Description | Selected |
|---|---|:---:|
| Illuminated Timeline Node | "WORKER LEASE RECLAIMED" with amber glow, worker ID, and lease expiry details | ✓ |
| Header Warning Chip | Amber chip at top of drawer | |
| Raw Metadata Only | Stored in SQLite but visible only in JSON viewer | |

**User's choice:** Illuminated Timeline Node.  
**Notes:** Makes worker crash recovery visible and auditable in the event timeline.

---

## 14. Exponential Backoff HUD (FLT-04)

| Option | Description | Selected |
|---|---|:---:|
| Active Retry Telemetry HUD | "Attempt N/5 • Next retry in X.Xs [Backoff + Jitter]" badge with real-time countdown | ✓ |
| Static Attempt Counter Pill | Simple "Attempt 2/5" pill without countdown | |
| Standard State Pill Only | Generic "RETRYING" label | |

**User's choice:** Active Retry Telemetry HUD with live countdown.  
**Notes:** Provides transparent visibility into backend store-and-forward scheduling.

---

## 15. Worker Crash Test Controls (FLT-04)

| Option | Description | Selected |
|---|---|:---:|
| Tactical Crash & Reclaim Controls | "Simulate Worker Crash (Abort Lease)" and "Trigger Immediate Stale Lease Reclamation" buttons in ConnectivityView | ✓ |
| Natural Timeout Only | Wait for 30s timeout without buttons | |
| REST API Only | Expose API endpoint without UI buttons | |

**User's choice:** Tactical Crash & Reclaim Controls in ConnectivityView.  
**Notes:** Enables deterministic verification and presentation of fault resilience.

---

## 16. Exhausted Retry Handling (FLT-04)

| Option | Description | Selected |
|---|---|:---:|
| Red 3D Card with Re-Queue Action | Distinct "FAILED_PERMANENT" card with "Retry Limit Exhausted [5/5]" badge and "Force Re-Queue" action | ✓ |
| Archived Failure Card | Message remains permanently failed with no re-queue option | |
| Modal Error Alert | Popup dialog upon retry exhaustion | |

**User's choice:** Red 3D Card with "Force Re-Queue Transmission" operator action.  
**Notes:** Provides a clear terminal failure state while empowering the operator to override when conditions improve.

---

## 17. Multi-Tab IndexedDB Concurrency (FLT-02)

| Option | Description | Selected |
|---|---|:---:|
| Web Locks / BroadcastChannel Leader Election | Single tab acquires flush lock; secondary tabs observe sync events via BroadcastChannel | ✓ |
| Optimistic Multi-Tab Flush | Allow any tab to send, relying on backend HTTP 200 deduplication | |
| Designated Primary Tab Only | Only active focused tab flushes; background tabs passive | |

**User's choice:** Web Locks / BroadcastChannel Leader Election.  
**Notes:** Rock-solid concurrency prevention across multiple windows/tabs.

---

## 18. Tactical Audio/Visual Alerting (FLT-01)

| Option | Description | Selected |
|---|---|:---:|
| Tactical Audio Cues & Radar Animation | Synthesized Web Audio squelch/beep on link sever/restore (toggleable in Header) plus 3D radar sweep line | ✓ |
| Visual-Only 3D Tactical Pulsing | Glowing amber/red perimeter pulse without audio | |
| Standard Text Status Change Only | Silent text change | |

**User's choice:** Tactical Audio Cues & Radar Animation.  
**Notes:** Enhances immersion and situational awareness while remaining unobtrusive.

---

## 19. Timestamp Reconciliation Strategy (FLT-02)

| Option | Description | Selected |
|---|---|:---:|
| Dual Timestamp Display | Orders by original composition time, showing both "Composed" and "Server Queued" timestamps | ✓ |
| Server Arrival Ordering | Orders strictly by server stored_at timestamp | |
| Client-Only Timestamp | Displays only client compose time | |

**User's choice:** Dual Timestamp Display.  
**Notes:** Preserves conversational narrative while maintaining SQLite storage auditability.

---

## 20. Exponential Backoff Tuning (FLT-04)

| Option | Description | Selected |
|---|---|:---:|
| Dual-Profile Preset Toggle | "Demo Fast Retries: 0.5s base, 5s max" vs "Tactical Field: 2s base, 60s max" in ConnectivityView | ✓ |
| Fixed Tactical Default | Fixed 2s base, 60s max parameters permanently | |
| Granular Tuner Sliders | Expose numeric sliders for base, ceiling, and jitter | |

**User's choice:** Dual-Profile Preset Toggle.  
**Notes:** Allows rapid demonstration while preserving production tactical behavior.

---

## 21. IndexedDB Storage Quotas & Air-Gap Safeguards (FLT-02)

| Option | Description | Selected |
|---|---|:---:|
| Explicit Storage Persistence & Safe Ceiling | navigator.storage.persist() on boot, 500-message buffer ceiling, warning at 400+ | ✓ |
| Dynamic Quota Monitoring | Alert only if browser quota drops below 10% | |
| Unbounded Local Outbox | Unlimited storage without persistence calls | |

**User's choice:** Explicit Storage Persistence & Safe Ceiling.  
**Notes:** Guarantees browser will not evict offline messages under disk pressure.

---

## 22. Server Reboot Lease Recovery (FLT-04)

| Option | Description | Selected |
|---|---|:---:|
| Immediate Startup Scan & Recovery | Server boot sweeps stranded in-flight SENDING messages to FAILED_RETRYABLE for immediate dispatch | ✓ |
| Passive Lease Expiration | Wait for 30s timeout | |
| Manual Operator Recovery Only | Wait for operator to click reclaim | |

**User's choice:** Immediate Startup Scan & Recovery.  
**Notes:** Prevents orphaned messages from stalling for 30 seconds after server restart.

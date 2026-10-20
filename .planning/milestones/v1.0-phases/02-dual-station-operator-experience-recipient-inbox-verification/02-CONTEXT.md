# Phase 2: Dual-Station Operator Experience & Recipient Inbox Verification - Context

**Gathered:** 2026-10-19  
**Status:** Ready for planning  

<domain>
## Phase Boundary

Phase 2 delivers a user-friendly, realistic dual-station operator experience with advanced 3D tactical visual depth. It provides:
1. Seamless adaptive switching and side-by-side monitoring between Station Alpha (`endpoint-a`) and Station Bravo (`endpoint-b`) with zero state loss (UI-01).
2. Live recipient inbox verification querying durable recipient storage (`GET /api/v1/endpoints/<id>/inbox`) with emerald 3D seal badges (UI-02).
3. A slide-out tactical telemetry drawer rendering real-time chronological message audit events (`MESSAGE_ENQUEUED` → `LEASE_ACQUIRED` → `INBOX_PERSISTED` → `ACK_VALIDATED_DELIVERED`) with microsecond timestamps and cryptographic verification chips (UI-03).
</domain>

<decisions>
## Implementation Decisions

### Station Layout & Viewport (UI-01)
- **D-01: Adaptive Dual/Single Viewport Toggle** — **Reversibility:** costly — changes core viewport layout and container split in `MessagesView.tsx`.
  - Provide a sleek 3D toggle in the navigation/toolbar allowing the operator to switch instantly between:
    - **Dual-Station Side-by-Side View:** Station Alpha (Left) and Station Bravo (Right) columns rendered concurrently with independent quick-compose bars and live transmission mirrors.
    - **Focused Single-Station View:** Concentrated operator console focused on the selected station with quick identity flip.
  - Preserve all draft messages, input state, and filter criteria across view toggles.

### Recipient Inbox Verification (UI-02)
- **D-02: Live Cross-Station Receipt Cards** — **Reversibility:** reversible — UI rendering and API query wiring.
  - Query `/api/v1/endpoints/<id>/inbox` to verify that transmitted packets physically reside in recipient durable storage.
  - When Station Alpha transmits to Station Bravo, animate the incoming item directly into Station Bravo's Inbox feed with an emerald 3D verified badge, storage timestamp, and payload integrity indicator.
  - Distinguish clearly between sender Outbox state (`DELIVERED`) and recipient durable storage (`INBOX_PERSISTED`).

### Audit Event Timeline Display (UI-03)
- **D-03: Slide-Out Tactical Telemetry Drawer** — **Reversibility:** reversible — self-contained drawer component.
  - Clicking any message opens a sleek dark glassmorphic right-hand inspection drawer.
  - Display an illuminated vertical 3D stepped event timeline of verified lifecycle transitions (`MESSAGE_ENQUEUED` → `LEASE_ACQUIRED` → `INBOX_PERSISTED` → `ACK_VALIDATED_DELIVERED`).
  - Surface microsecond timestamps, worker lease IDs, retry attempts, and cryptographic HMAC receipt chips.

### 3D Tactical Aesthetics & Polling Cadence
- **D-04: Advanced 3D Military C2 Visual Design & 1.5s Adaptive Polling** — **Reversibility:** reversible — CSS styling and interval timers.
  - Implement a streamlined, user-friendly tactical aesthetic: deep dark palette (`#0B0F17` background, elevated `#131B2E` panels), glassmorphic blur, 3D card borders with subtle directional depth drop-shadows, and cyber-tactical emerald/cyan status lights.
  - Execute a high-performance **1.5s adaptive polling loop** for active outboxes/inboxes, with instant optimistic UI updates on send and automatic throttling to 5s when the browser tab is in background to preserve system resources.

### the agent's Discretion
- Exact CSS shadow values, glassmorphic backdrop-filter blurs, and transition timings for the 3D toggle and slide-out telemetry drawer.
- Icon selection from `lucide-react` for event node milestones in the audit timeline.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project & Requirements
- `.planning/PROJECT.md` — Core value, dual-station architecture context, and constraints.
- `.planning/REQUIREMENTS.md` — UI-01, UI-02, and UI-03 requirement specifications.
- `.planning/ROADMAP.md` § Phase 2 — Phase 2 success criteria, goals, and plan boundaries.

### Codebase Architecture & Conventions
- `.planning/codebase/CONVENTIONS.md` — Frontend component naming, TypeScript typing, and code style.
- `.planning/codebase/STRUCTURE.md` — Component layout and file locations in `frontend/src/`.
- `.planning/codebase/TESTING.md` — Test patterns and validation commands.

### Existing Implementation Source Files
- `Final-Project/frontend/src/components/MessagesView.tsx` — Base 3-panel messaging console to be adapted into dual-station console.
- `Final-Project/frontend/src/components/Header.tsx` — Navigation bar where adaptive dual/single view toggle will be mounted.
- `Final-Project/frontend/src/services/api.ts` — Frontend REST client providing `getMessages`, `getInbox`, `getHealth`.
- `Final-Project/messaging/api.py` — Canonical backend REST endpoints:
  - `GET /api/v1/endpoints/<id>/inbox` — Endpoint inbox records.
  - `GET /api/v1/messages/<id>/events` — Message audit log events.
  - `GET /api/v1/messages` — Message queue list.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Final-Project/frontend/src/components/StatusIndicator.tsx`: Real-time connectivity and status pills for stations.
- `Final-Project/frontend/src/types/index.ts`: Strongly typed `Message`, `InboxMessage`, `MessageEvent`, and `MessageState` interfaces.
- `Final-Project/frontend/src/services/api.ts`: API service with built-in bearer token support and JSON error handling.

### Established Patterns
- Component architecture: Functional React 19 components with TypeScript, `useState`, `useEffect`, `useCallback`.
- Styling: Tailwind CSS v4 directives with dark theme variables.
- REST querying: Safe integer handling and parameterized query filters (`sender`, `recipient`, `state`).

### Integration Points
- `/api/v1/endpoints/endpoint-a/inbox` and `/api/v1/endpoints/endpoint-b/inbox` for querying recipient durable inbox items.
- `/api/v1/messages/{id}/events` for populating the slide-out audit timeline drawer.

</code_context>

<specifics>
## Specific Ideas

- **User Direction:** "make it user friendly, ui is more complicated, make it more realistic, change ui more advance 3d".
- Clean tactical defense console visual hierarchy (reminiscent of modern C2 systems, Palantir Gotham, or high-end SDR workstations) avoiding cluttered visual noise while delivering tactile 3D depth, crisp typography, and instant station awareness.

</specifics>

<deferred>
## Deferred Ideas

- None — all discussed decisions strictly align with Phase 2 scope (UI-01, UI-02, UI-03). Fault injection controls remain in Phase 3; hardware lockouts remain in Phase 4.

</deferred>

---

*Phase: 02-dual-station-operator-experience-recipient-inbox-verification*  
*Context gathered: 2026-10-19*  

# Phase 6: Multi-Database Physical Isolation & Dedicated Daemon Endpoints — Discussion Log

**Date:** 2026-10-20  
**Phase:** 06  
**Status:** Completed

---

## Areas Discussed

### 1. Port & Console Topography
- **Options Presented:**
  1. Unified Gateway + Direct Access: Main UI on port 5050 with side-by-side dual-feed monitoring communicating with Alpha (5051) and Bravo (5052), while each daemon also serves its own standalone console directly.
  2. Strict Dual-Tab Independence: No proxy on 5050; operators open http://localhost:5051 for Alpha and http://localhost:5052 for Bravo in separate browser windows.
- **User Selection:** Option 1 (Unified Gateway + Direct Access).
- **Notes:** Operator can see both station feeds side-by-side on 5050 or open isolated tabs for individual stations.

### 2. Cross-Station Transport Protocol
- **Options Presented:**
  1. REST Peer Transport with Impairment Pipeline: Worker posts to remote station /api/v1/endpoints/incoming with simulated drops, latency, and air-gap interruptions.
  2. Dedicated Loopback RF Broker: A separate Python socket broker daemon multiplexing raw frames between stations.
- **User Selection:** Option 1 (REST Peer Transport with Impairment Pipeline).
- **Notes:** Clean, verifiable HTTP delivery that models tactical IP and packet radios with explicit failure handling.

### 3. Station Identity & Database Enforcement
- **Options Presented:**
  1. Strict Local Identity: alpha.db only permits local submissions as endpoint-a and stores endpoint-b as remote; bravo.db vice-versa. Local composition cannot spoof remote node.
  2. Permissive Multi-Node: Any station daemon can author messages as any endpoint if authorized by token.
- **User Selection:** Option 1 (Strict Local Identity).
- **Notes:** Prevents identity spoofing across independent station daemons.

### 4. Developer Launcher & Multi-Daemon Orchestration
- **Options Presented:**
  1. Unified scripts/dev.sh with --dual-station flag: Boots Alpha (5051) and Bravo (5052) concurrently with single-command trap cleanup, while also allowing single-station flags (--station alpha).
  2. Separate Scripts: scripts/dev-alpha.sh and scripts/dev-bravo.sh run in separate terminal tabs.
- **User Selection:** Option 1 (Unified scripts/dev.sh with --dual-station flag).
- **Notes:** Clean single-command developer experience with automated trap cleanup for all spawned daemons.

---

## Summary of Locked Decisions
- **D-01:** Unified Gateway + Direct Access on port 5050 proxying to Alpha (5051) and Bravo (5052).
- **D-02:** HTTP/REST Peer Transport across remote station endpoints with impairment simulation.
- **D-03:** Strict Local Station Identity enforcement per database instance.
- **D-04:** Unified `scripts/dev.sh --dual-station` multi-process launcher.

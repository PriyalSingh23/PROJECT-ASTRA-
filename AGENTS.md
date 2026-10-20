# Multi-Agent Coordination Protocol: Antigravity & OpenCode

This workspace operates under a collaborative multi-agent configuration where **Google Antigravity** and **OpenCode Agent** run concurrently on the same project repository.

---

## 1. Core Operating Principles

1. **Shared Filesystem Truth**:
   Both agents read and write directly to `/Users/sabhay/Downloads/PROJECT 13OCT`. Changes made by either agent are instantly live on disk.
2. **Git Baseline & Atomic Commits**:
   - All shared progress is committed to `main`.
   - Before starting a destructive refactor or large module, verify `git status` is clean.
   - Run verification tests before committing.
3. **Linker & Runtime Safety (Apple Silicon)**:
   - On macOS Apple Silicon (Darwin), `import torch` MUST strictly precede `numpy` and `scipy` in any Python entry point to avoid OpenBLAS linker collision (`SIGSEGV 139`).

---

## 2. Agent Domain Partitioning

To avoid concurrent write collisions or conflicting file edits:

| Domain | Primary Agent | Directory Scope |
| :--- | :--- | :--- |
| **Frontend UI/UX & Visuals** | **Antigravity** | `Final-Project/frontend/src/`, `SHADOWLINK-FIELD/frontend/src/` |
| **3D Topology & Visualizers** | **Antigravity** | `frontend/src/components/topology/`, `LiveSignalAnalyser.tsx` |
| **Verification & Documentation** | **Antigravity** | `tests/`, `docs/`, `README.md`, `.planning/` reviews |
| **Backend Daemons & Workers** | **OpenCode** | `Final-Project/messaging/`, `SHADOWLINK-FIELD/backend/` |
| **DSP, RF & LPI-CGAN Models** | **OpenCode** | `Final-Project/lpi_v4/`, `Final-Project/comms/` |
| **Hardware & Radio Adapters** | **OpenCode** | `Final-Project/integration/`, `SHADOWLINK-FIELD/integration/` |

---

## 3. Port & Service Allocation Matrix

Avoid port conflicts between concurrent daemons:
* **Port 5050**: Unified Web Console Gateway (`messaging.server --port 5050`)
* **Port 5051**: Station Alpha Daemon (`messaging.server --port 5051 --station-id endpoint-a`)
* **Port 5052**: Station Bravo Daemon (`messaging.server --port 5052 --station-id endpoint-b`)
* **Port 5173**: Vite Frontend Dev Server (`npm run dev`)
* **Port 8000**: Field Operations FastAPI Engine (`uvicorn app.main:app --port 8000`)

---

## 4. Verification Checkpoint Commands

Before any agent marks a task complete:
* **Python Backend Tests**: `cd Final-Project && pytest -q`
* **Frontend TypeScript Build**: `cd Final-Project/frontend && npm run build`
* **Planning State Sync**: Keep `.planning/STATE.md` updated with completed goals.

# macOS Developer & Operator Setup Guide: SHADOWLINK FIELD

**Environment Target:** macOS (Darwin 24+ / macOS Sequoia / Sonoma) on Apple Silicon & Intel  
**Default Shell:** `zsh`

---

## 1. Discovered Machine Toolchain

On this workstation, the required development and runtime tools are pre-installed:
- **Python Runtime**: `/Users/sabhay/radioconda/bin/python3` (Python 3.12.9)
- **Node.js**: `/usr/local/bin/node` (v24.22.0)
- **Package Manager**: `/usr/local/bin/npm` (11.19.1)
- **Database Engine**: Native SQLite 3.45+ with Write-Ahead Logging (WAL) support

---

## 2. Directory Structure

```
/Users/sabhay/Downloads/PROJECT 13OCT/
├── Final-Project/           (Original Research Provenance - Read Only)
└── SHADOWLINK-FIELD/        (Production Communications Platform)
    ├── backend/             (FastAPI + SQLAlchemy + Pydantic Core)
    ├── frontend/            (React + TypeScript + Vite + Tailwind CSS)
    ├── integration/         (Motorola, STAR-V, and SDR Adapters)
    ├── tests/               (Automated Unit & Contract Test Suites)
    └── docs/                (Comprehensive Architecture & Operations Guides)
```

---

## 3. Step-by-Step Launch Instructions

### Terminal 1: Launch Backend Core API Server
Navigate to the product directory and start the FastAPI service:

```bash
cd "/Users/sabhay/Downloads/PROJECT 13OCT/SHADOWLINK-FIELD/backend"
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
*Health Check*: Verify via browser or curl:
```bash
curl http://127.0.0.1:8000/api/v1/health
```

### Terminal 2: Launch Queue Delivery Worker Process
In a separate terminal, launch the background delivery engine:

```bash
cd "/Users/sabhay/Downloads/PROJECT 13OCT/SHADOWLINK-FIELD/backend"
python3 -m app.services.worker --interval 1.0
```
*The worker continuously monitors the persistent SQLite queue, acquires messages via atomic conditional updates, and handles delivery attempts.*

### Terminal 3: Launch Frontend Web Application
Navigate to the frontend folder and start the Vite development server:

```bash
cd "/Users/sabhay/Downloads/PROJECT 13OCT/SHADOWLINK-FIELD/frontend"
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```
Open your browser to: **http://127.0.0.1:5173**

---

## 4. Running the Automated Test Suite

To run all unit tests, contract tests, and simulation verification without radio hardware:

```bash
cd "/Users/sabhay/Downloads/PROJECT 13OCT/SHADOWLINK-FIELD"
pytest tests/ -v
```

---

## 5. macOS Troubleshooting & Pitfalls

### Issue 1: Port Conflicts on Port 5000 / 7000
- **Symptom**: `OSError: [Errno 48] Address already in use`
- **Cause**: macOS AirPlay Receiver listens by default on port 5000 and 7000.
- **Remedy**: SHADOWLINK FIELD deliberately defaults to port **8000** for FastAPI, port **5050** for simulation nodes, and port **5173** for the Vite frontend to avoid conflicting with macOS system services.

### Issue 2: PyTorch Complex BLAS Segfaults on Apple Silicon
- **Symptom**: Python segfaults (`Fatal Python error: Segmentation fault`) in matrix operations.
- **Cause**: Radioconda BLAS library vectorization under certain PyTorch versions when complex arrays are not memory-aligned.
- **Remedy**: The `SdrResearchAdapter` implements an internal pure-Python / NumPy simulation path for all software verification.

### Issue 3: SQLite File Locks Across Terminal Windows
- **Symptom**: `sqlite3.OperationalError: database is locked`
- **Remedy**: The database engine explicitly activates Write-Ahead Logging (`PRAGMA journal_mode=WAL`) and a 5-second busy timeout (`PRAGMA busy_timeout=5000`) in `app/core/database.py`.

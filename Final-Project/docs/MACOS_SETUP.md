# MACOS SETUP & OPERATIONAL EXECUTION GUIDE

**Project**: ShadowComm / ShadowLink Resilient Offline Messaging  
**Target Environment**: macOS Darwin (Apple Silicon M1/M2/M3/M4 or Intel x86_64)  
**Host Shell**: zsh / bash  

---

## 1. Important Operating System Notice

> [!CAUTION]
> Do **NOT** execute Windows batch files (`run_all.bat`, `start.bat`) on macOS. They contain Windows-specific syntax (`call`, `%~dp0`, `timeout /t`) and will fail or corrupt paths on Unix systems.
> Use only native macOS commands and POSIX shell scripts.

---

## 2. Environment Setup

### 2.1. Python Runtime
The system runs on Python 3.10+ (tested with Python 3.12.9 in the user's `radioconda` environment).

Check your active Python installation:
```bash
which python3
python3 --version
```
*Recommended macOS binary path*:
```bash
export PYTHON_BIN="/Users/sabhay/radioconda/bin/python3"
# Or standard system / Homebrew Python:
# export PYTHON_BIN="python3"
```

### 2.2. Setting Up Environment Configuration
From the `Final-Project` root directory:
```bash
cd "/Users/sabhay/Downloads/PROJECT 13OCT/Final-Project"

# Copy example environment configuration
cp .env.example .env

# Generate secure random secret key
export SHADOWCOMM_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
export SHADOWCOMM_REQUIRE_AUTH=false  # Set to true for strict token validation
export SHADOWCOMM_HOST=0.0.0.0
export SHADOWCOMM_PORT=5050
```

---

## 3. Operational Startup (Independent Processes)

Running a durable queue system requires keeping the web ingestion API independent of the background delivery queue worker. This ensures that web server restarts do not disrupt worker deliveries, and worker crashes do not drop incoming client requests.

### Terminal 1: Web Application & REST API Gateway
```bash
cd "/Users/sabhay/Downloads/PROJECT 13OCT/Final-Project"
export PYTHONPATH="."
python3 -m messaging.server --host 0.0.0.0 --port 5050
```
- **Local Browser Access**: [http://127.0.0.1:5050](http://127.0.0.1:5050)
- **Local Network (LAN) Access**: `http://<YOUR_MAC_IP>:5050`
- **REST Health Check**: [http://127.0.0.1:5050/api/v1/health](http://127.0.0.1:5050/api/v1/health)

### Terminal 2: Background Queue Delivery Worker
```bash
cd "/Users/sabhay/Downloads/PROJECT 13OCT/Final-Project"
export PYTHONPATH="."
python3 -m messaging.worker --interval 1.0 --max-attempts 5
```
- The worker process continuously leases and delivers queued messages using atomic database transactions.
- You can stop and restart the worker at any time without losing messages.

---

## 4. Running Automated Verification Tests

### 4.1. Run Full Regression Test Suite (14 Tests)
```bash
cd "/Users/sabhay/Downloads/PROJECT 13OCT/Final-Project"
python3 -m pytest tests/test_offline_messaging.py -v
```

### 4.2. Run 1,050-Message Deterministic Simulation Suite
```bash
cd "/Users/sabhay/Downloads/PROJECT 13OCT/Final-Project"
python3 -m pytest tests/test_simulation_1000_messages.py -v -s
```

---

## 5. Graceful Shutdown & Cleanup

To stop running background services cleanly:

1. **In Terminal 1 (Server)**: Press `Ctrl + C`. Flask will close active connections and release port 5050.
2. **In Terminal 2 (Worker)**: Press `Ctrl + C`. The worker catches `SIGINT`, finishes any in-flight database atomic lease, and exits cleanly:
   ```
   [Worker QueueWorker]: Signal 2 received: Initiating graceful worker shutdown...
   [Worker QueueWorker]: Worker stopped cleanly.
   ```
3. **Database WAL Checkpoint (Optional Maintenance)**:
   ```bash
   sqlite3 shadowcomm_messaging.db "PRAGMA wal_checkpoint(TRUNCATE);"
   ```

---

## 6. Hardware Independence

The messaging subsystem is completely **decoupled** from SDR hardware:
- Does **NOT** initialize UHD / USRP B200 hardware.
- Does **NOT** require GPU / CUDA (runs purely on CPU).
- Does **NOT** emit radio frequency energy.
- Safe to run on any standard MacBook or Mac mini.

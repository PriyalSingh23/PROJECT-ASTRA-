# SHADOWLINK FIELD: SYSTEM OPERATIONS & RECOVERY GUIDE

**Audience**: Field Systems Operators, Incident Dispatchers & IT Administrators  
**System**: SHADOWLINK Resilient Communications Platform  
**Target Host**: macOS / Linux Edge Gateway  
**Document Version**: 2.0  

---

## 1. System Startup Procedures

The system utilizes independent process architecture to isolate message ingestion from queue delivery:

```
[Terminal 1: REST API Gateway] <---> [SQLite WAL Database] <---> [Terminal 2: Queue Worker]
```

### Step 1: Environment Initialization
```bash
cd "/Users/sabhay/Downloads/PROJECT 13OCT/Final-Project"

# Copy example environment configuration if not present
cp -n .env.example .env

# Configure environment variables
export SHADOWCOMM_HOST="0.0.0.0"
export SHADOWCOMM_PORT="5050"
export SHADOWCOMM_REQUIRE_AUTH="true"
export SHADOWCOMM_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
```

### Step 2: Launch REST API Gateway (Terminal 1)
```bash
python3 -m messaging.server --host 0.0.0.0 --port 5050
```
- Web UI: [http://127.0.0.1:5050](http://127.0.0.1:5050)
- Health API: [http://127.0.0.1:5050/api/v1/health](http://127.0.0.1:5050/api/v1/health)

### Step 3: Launch Background Delivery Worker (Terminal 2)
```bash
python3 -m messaging.worker --interval 1.0 --max-attempts 5
```

---

## 2. Health Monitoring & Diagnostics

### Real-Time Queue Inspection:
```bash
curl -s http://127.0.0.1:5050/api/v1/queue/stats | python3 -m json.tool
```
Key health indicators to monitor:
- `queue_depth`: Number of unleased queued messages (normal: 0–10).
- `oldest_pending_seconds`: Age of oldest pending message (if growing, transport is disconnected).
- `failed_retryable_count`: Messages undergoing exponential backoff retries.
- `expired_count`: Messages discarded after TTL expiration.

### Inspecting Security Audit Logs (Administrator Token Required):
```bash
curl -s -H "Authorization: Bearer <ADMIN_SESSION_TOKEN>" \
  http://127.0.0.1:5050/api/v1/security/audit-logs
```

---

## 3. Database Backup & Restore Procedures

### 3.1. Hot Backup (Zero-Downtime SQLite WAL Backup)
SQLite in WAL mode supports online backups without stopping the application:
```bash
# Force a WAL checkpoint to flush in-flight transactions
sqlite3 shadowcomm_messaging.db "PRAGMA wal_checkpoint(TRUNCATE);"

# Create timestamped atomic backup
sqlite3 shadowcomm_messaging.db ".backup 'backups/shadowcomm_backup_$(date +%Y%m%d_%H%M%S).db'"
```

### 3.2. Disaster Recovery / Restore Procedure
1. Stop the web gateway and queue worker (`Ctrl + C` in both terminals).
2. Archive the corrupted database:
   ```bash
   mv shadowcomm_messaging.db shadowcomm_messaging.db.corrupted
   ```
3. Restore from verified backup:
   ```bash
   cp backups/shadowcomm_backup_YYYYMMDD_HHMMSS.db shadowcomm_messaging.db
   ```
4. Run SQLite integrity check:
   ```bash
   sqlite3 shadowcomm_messaging.db "PRAGMA integrity_check;"
   # Expected output: ok
   ```
5. Restart server and worker processes.

---

## 4. Graceful Shutdown

1. **Stop Worker Process**: Press `Ctrl + C` in Terminal 2. The worker catches `SIGINT`, finishes any in-flight database transaction, releases worker leases, and exits cleanly.
2. **Stop API Gateway**: Press `Ctrl + C` in Terminal 1. Flask releases port 5050 and terminates.

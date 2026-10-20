# Testing Patterns

**Analysis Date:** 2026-10-19

## Test Framework

**Runner:**
- **pytest >= 7.4.0** (Python 3.12 environment)
- Config: `Final-Project/tests/conftest.py` with dynamic linker pre-initialization (`import torch`)

**Assertion Library:**
- Native Python `assert` with descriptive failure messages
- `pytest.raises` for expected domain exceptions (`AuthenticationError`, `InvalidStateTransitionError`, `StarVSafetyLockoutError`)

**Run Commands:**
```bash
pytest                                                 # Run all 101 unit and integration tests
pytest tests/test_offline_messaging.py -v              # Run messaging state machine and concurrency tests
pytest tests/test_simulation_1000_messages.py -s       # Run 1,050-message deterministic stress simulation
pytest tests/integration/ -v                           # Run hardware adapter and relay integration tests
pytest --cov=messaging --cov=integration --cov=lpi_v4  # Run test suite with line coverage
```

---

## Test File Organization

**Location:**
- Separate dedicated test directory at `Final-Project/tests/` with subdirectories for specialized integration tests.

**Naming:**
- Prefixed with `test_` matching the subsystem under evaluation: `test_offline_messaging.py`, `test_security_auth.py`, `test_lpi_v4.py`, `test_simulation_1000_messages.py`.

**Structure:**
```
Final-Project/tests/
├── conftest.py                             # Global fixtures and torch dynamic linker pre-initialization
├── integration/                            # Multi-transport hardware and adapter tests
│   ├── test_adapters.py                    # Motorola, STAR-V, LPI-CGAN adapter tests
│   ├── test_motorola_bridge.py             # Motorola hardware bridge and TMS PDU validation
│   └── test_relay_nodes.py                 # Telemetry and aerial store-and-forward failsafes
├── test_offline_messaging.py               # 16-test lifecycle, lease, concurrency, and ACK reconciliation suite
├── test_security_auth.py                   # 9-test PBKDF2, RBAC, and AES-256-GCM v2 envelope suite
├── test_simulation_1000_messages.py        # Deterministic 1,050-message outage and recovery stress test
├── test_lpi_v4.py                          # 22-test PyTorch waveform, RS/CRC framing, and EW statistics suite
├── test_spectrum_analyser.py               # PSD, spectrogram, autocorrelation, and IQ replay tests
├── test_tx_rx_integration.py               # End-to-end transmitter DSP and receiver recovery tests
├── test_workstation_service.py             # Mission overview and SDR probe tests
├── test_guided_demo_and_help.py            # Glossary, workflow steps, and help modal tests
└── test_presentation_mode.py               # Recorded IQ file replay and hardware fallback tests
```

---

## Test Structure

**Suite Organization:**
```python
import pytest
from messaging.db import init_db, get_db_session
from messaging.models import Message, Endpoint
from messaging.service import MessagingService
from messaging.crypto_v2 import encrypt_v2_gcm, decrypt_v2_gcm, AuthenticationError

@pytest.fixture
def test_db(tmp_path):
    """Creates an isolated temporary SQLite database for each test."""
    db_file = tmp_path / "test_messaging.db"
    db_path = str(db_file)
    init_db(db_path)
    yield db_path

def test_aes_256_gcm_tamper_detection():
    key = "master-aes-key-for-testing-0012"
    envelope = bytearray(encrypt_v2_gcm("Sensitive coordinates: 34.05,-118.25", key))
    envelope[-1] ^= 0x01  # Mutate ciphertext byte
    
    with pytest.raises(AuthenticationError):
        decrypt_v2_gcm(bytes(envelope), key)
```

**Patterns:**
- **Setup Pattern:** Pytest fixture creates a temporary SQLite file with WAL mode enabled and initializes clean table schemas (`init_db(db_path)`).
- **Teardown Pattern:** Fixtures yield the database path to the test function, then remove the `.db`, `-wal`, and `-shm` files upon completion.
- **Assertion Pattern:** Assert equality of state transitions, verify timestamp ordering (`created_at <= delivered_at`), and assert HMAC signature validity.

---

## Mocking

**Framework:**
- In-memory simulation and hardware stub objects (`transport.reset()`, `SimulatedTransport`, `RadioSim`). No heavy external mocking frameworks required; domain classes provide built-in simulation hooks.

**Patterns:**
```python
# Impairing simulated link to test offline retry backoff
transport.reset()
transport.set_connected(False)
assert transport.is_connected() is False

# Reconnecting transport and draining queue
transport.set_connected(True)
processed = worker.run_once()
assert processed > 0
```

**What to Mock:**
- Physical SDR hardware interfaces (Ettus USRP B200/B210 UHD device communication).
- External Motorola MOTOTRBO DMR radio hardware channels (`TransportReadiness.SIMULATION_ONLY`).
- Network dropouts and physical link disruptions via `transport.set_connected(False)`.

**What NOT to Mock:**
- SQLite database transactions, WAL locks, and concurrent worker leases (tested on real SQLite engines).
- Cryptographic hashing, PBKDF2 derivations, and AES-256-GCM cipher operations (tested with live cryptography).
- PyTorch tensor mathematics and forward error correction (RS/CRC) routines.

---

## Fixtures and Factories

**Test Data:**
```python
@pytest.fixture
def test_db():
    """Creates an isolated temporary SQLite database for each test."""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, f"test_messaging_{uuid.uuid4().hex[:8]}.db")
    init_db(db_path)
    transport.reset()
    yield db_path
    transport.reset()
    try:
        for suffix in ["", "-wal", "-shm"]:
            f = f"{db_path}{suffix}"
            if os.path.exists(f):
                os.remove(f)
        os.rmdir(temp_dir)
    except Exception:
        pass
```

**Location:**
- Shared fixtures located in `Final-Project/tests/conftest.py` and module-level fixtures in `Final-Project/tests/test_offline_messaging.py`.

---

## Coverage

**Requirements:**
- High coverage target on critical messaging logic (state machine, retry backoff, worker leases, cryptographic envelope). 101 tests verifying all core paths.

**View Coverage:**
```bash
pytest --cov=messaging --cov=integration --cov=lpi_v4 --cov-report=term-missing
```

---

## Test Types

**Unit Tests:**
- Cryptographic envelope encryption and tampering detection (`Final-Project/tests/test_security_auth.py`).
- Deterministic message state transitions and validation constraints (`Final-Project/tests/test_offline_messaging.py`).
- Reed-Solomon framing and Zadoff-Chu preamble synchronization (`Final-Project/tests/test_lpi_v4.py`).

**Integration Tests:**
- Multi-transport routing decisions and adapter boundaries (`Final-Project/tests/integration/test_adapters.py`).
- Motorola TMS PDU parsing, corruption detection, and 280-byte ceiling verification (`Final-Project/tests/integration/test_motorola_bridge.py`).
- Store-and-forward relay node battery/storage telemetry failsafes (`Final-Project/tests/integration/test_relay_nodes.py`).

**E2E Tests:**
- 1,050-message deterministic outage, lease recovery, and signed ACK reconciliation simulation (`Final-Project/tests/test_simulation_1000_messages.py`).
- Hardware presentation and IQ replay pipeline tests (`Final-Project/tests/test_presentation_mode.py`).

---

## Common Patterns

**Async / Concurrency Testing:**
```python
# Two workers competing for the same message queue concurrently
with ThreadPoolExecutor(max_workers=2) as executor:
    future1 = executor.submit(worker1.run_once)
    future2 = executor.submit(worker2.run_once)
    p1 = future1.result()
    p2 = future2.result()

# Exactly one worker must claim the lease; no duplicate delivery
assert p1 + p2 == 1
```

**Error Testing:**
```python
# Verifying safety lockout for physical transmission
with pytest.raises(StarVSafetyLockoutError):
    adapter.transmit_raw_rf(b"UNAUTHORIZED_RF_FRAME")
```

---

*Testing analysis: 2026-10-19*

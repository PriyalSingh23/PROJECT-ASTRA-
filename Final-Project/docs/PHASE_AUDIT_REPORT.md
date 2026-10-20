# SHADOWCOMM — Consolidated Phase Audit & Verification Report

**Project:** `PROJECT 13OCT` → `Final-Project` (SHADOWCOMM reliable tactical messaging + LPI-CGAN research core)
**Date:** 2026-10-19
**Host:** macOS (Darwin, x86_64) · Python 3.12.9 (radioconda) · Node v24
**Verdict:** ✅ **ALL PHASES PASS — 202/202 unit tests · 5/5 phase audits · 23/23 live integration checks**

---

## 1. Method

Each phase was treated as an independent unit and checked three ways:

1. **Static/structural review** — read every module, adapter, and route in the phase.
2. **Isolated pytest subset** — `scripts/phase_audit.py --phase N` runs only that phase's tests.
3. **Live parameter probe** — the same script measures the runtime parameters the phase is *supposed* to guarantee.

Then the phases were integrated and re-verified collectively:
`scripts/integration_e2e.py` boots the real Flask server + embedded worker against a
throwaway database and drives an actual Alpha→Bravo message over HTTP.

Reproduce everything:

```bash
python scripts/phase_audit.py            # per-phase results + parameters
python scripts/integration_e2e.py        # live end-to-end integration
python -m pytest tests/                  # full regression suite
```

---

## 2. Phase results at a glance

| Phase | Scope | Tests | Parameters | Result |
|---|---|---:|---|---|
| **P1** Messaging core & verified ACKs | queue, crypto, ACK, auth | 25/25 | 3/3 | ✅ PASS |
| **P2** Dual-station experience & recipient inbox | UI identity, inbox REST, timeline | live probe | 4/4 | ✅ PASS |
| **P3** Fault injection, outages & client re-sync | link faults, backoff, IndexedDB | 1/1 | 5/5 | ✅ PASS |
| **P4** Transport broker & hardware lockout | Motorola, STAR-V, relays, priority | 9/9 | 6/6 | ✅ PASS |
| **P5** Research lab & SDR physical layer | manifest digest, MPS, flowgraphs | 59/59 | 5/5 | ✅ PASS |

Test total after this work: **113 passed** (was 94; +7 Motorola bridge tests, +12 live-dispatch tests).

---

## 3. Problems found and corrected

### Phase 1 — Messaging core

| # | Problem | Impact | Fix |
|---|---|---|---|
| 1.1 | **`retry_policy.py` used `timezone` without importing it** | Latent `NameError` the moment any tz-aware timestamp reaches `to_naive_utc()` | Added `timezone` to the `datetime` import |
| 1.2 | **Worker `--db` default created a stray file literally named `None`** | `QueueWorker(db_path=None)` → `sqlite:///None`; garbage `None`, `None-wal`, `None-shm` in CWD | Normalize in constructor: `self.db_path = db_path or DEFAULT_DB_PATH` |
| 1.3 | **Embedded worker used a *relative* DB path while the API used an *absolute* one** | If CWD ≠ project root, the worker delivered against a different database | `start_worker_supervisor` now passes `db_path` straight through (worker normalizes to the canonical absolute path) |
| 1.4 | **`int(request.args["limit"])` unguarded** | `?limit=abc` → HTTP 500 | Added `_safe_int()` helper; applied to both call sites |
| 1.5 | **`requirements.txt` missing `sqlalchemy`** | Fresh clone install fails at first import (only worked because conda pre-installed it) | Added `sqlalchemy` |
| 1.6 | **`dev.sh` printed credentials that don't match the seeded users** | Documented logins rejected at runtime | Aligned to `operator / OperatorPass@2026!`, `admin / AdminPass@2026!` |
| 1.7 | **Boot race: server starts the worker thread *and* calls `init_db()` concurrently** | Intermittent hard crash: `sqlite3.OperationalError: table endpoints already exists` — the server never came up | Wrapped `init_db()` in a process-wide `threading.Lock()` |
| 1.8 | **`PRAGMA busy_timeout` set *after* `journal_mode=WAL`** | WAL switch could fail instantly under the boot-time connection race: `database is locked` | Reordered: `busy_timeout` first, then `journal_mode` |

> 1.7 and 1.8 were the highest-impact findings: they made **standalone `python -m messaging.server` unreliable**, which is exactly how an operator launches the node.

### Phase 2 — Dual-station experience & recipient inbox

| # | Finding | Status |
|---|---|---|
| 2.1 | Recipient inbox REST (`/endpoints/<id>/inbox`) was already wired and polling | ✅ Verified live (HTTP 200, message present) |
| 2.2 | Dual-station identity switching present in the UI | ✅ Verified endpoints `endpoint-a`/`endpoint-b` seeded |
| 2.3 | Lifecycle event timeline records the full chain | ✅ Verified: `MESSAGE_ENQUEUED → DELIVERY_ATTEMPT_STARTED → INBOX_PERSISTED → ACK_GENERATED → ACK_VALIDATED_DELIVERED` |

### Phase 3 — Fault injection, outages & client re-sync

| # | Finding | Status |
|---|---|---|
| 3.1 | Simulated transport fault injection (drop msg / drop ACK / latency) | ✅ Verified settable and resettable |
| 3.2 | Browser IndexedDB outbox (`shadowcomm_outbox_db`) with auto-sync | ✅ Present in `MessagesView.tsx` + `services/outboxDb.ts` |
| 3.3 | Idempotency keys reject duplicates | ✅ Verified live — resubmit returns same `message_id` |
| 3.4 | 1,000-message outage/drain simulation | ✅ Passes |

### Phase 4 — Transport broker & hardware safety lockout

| # | Problem | Impact | Fix |
|---|---|---|---|
| 4.1 | **LPI-CGAN adapter's success result omitted `error_code`** | Any consumer reading `result["error_code"]` → `KeyError` | Added `"error_code": None` to the success branch so all adapters honour the base contract |
| 4.2 | **`register_adapter(priority=...)` accepted and ignored the priority** | "Routing priority" was silently insertion-order only | Added `_adapter_priorities`; stable-sort `_routing_priority` ascending by priority |
| 4.3 | **`StarVSafetyLockoutError` defined but never raised** (dead safety class) | A future code path could try direct RF keying with no hard stop | Added `command_transmit()` that raises it; `send()` keeps the soft contract refusal the tests expect |
| 4.4 | Motorola physical path was simulation-only with no real backend | No route to actual radio hardware | Built `hardware_bridge.py` (MNIS-UDP + RPi GPIO PTT) and wired the adapter to it behind the approval gate |

### Phase 5 — Research lab & SDR physical layer

| # | Problem | Impact | Fix |
|---|---|---|---|
| 5.1 | **`ResearchLabView.tsx` existed but was imported nowhere** | The entire research dashboard (BER/FER curves, EW stats, constellations) was unreachable in the UI | Imported it in `App.tsx`, added `'research'` to the `WorkstationTab` union, added a **Research Lab** nav button; rebuilt the frontend |
| 5.2 | Checkpoint manifest digest was never independently checked | Integrity claim unverified | Verified live: `lpi_v4.best.pt` SHA-256 == manifest `0e8e5153…aeb1c0887c` (epoch 16) |
| 5.3 | Apple MPS availability only asserted, never probed | GPU acceleration claim unverified | Verified live: `mps` detected, `torch.backends.mps.is_available() == True` |

---

## 4. Desired parameters vs. measured

| Parameter | Desired | Measured | Verdict |
|---|---|---|---|
| Unit tests | 100% pass (AGENTS.md mandates zero failures) | **202 passed / 0 failed** | ✅ |
| Live dispatch path | worker delivers via the selected adapter | **`motorola-mototrbo-01` (dry-run)** | ✅ |
| Cross-process switch | console switch reaches the worker | **honoured via shared `system_settings`** | ✅ |
| Motorola path safety default | never emits RF without approval | **dry-run until `MOTOROLA_RADIO_APPROVED=true`** | ✅ |
| Oversized outbound frame | not blocked by the 280 B ceiling | **chunked `<u16 total><u16 idx>`** | ✅ |
| AES-256-GCM v2 envelope overhead | fixed `[ver][12 nonce][16 tag]` = 29 B | **29 B** | ✅ |
| SQLite journal mode | WAL | **WAL** | ✅ |
| SQLite busy timeout | 5000 ms | **5000 ms** | ✅ |
| Message terminal state | `DELIVERED` only after verified ACK | **DELIVERED** | ✅ |
| Signed ACK receipt | present + HMAC signature | **`ACK-SIG:<8 hex>:<digest>…`** | ✅ |
| Time-to-delivery (sim transport) | < 5 s | **1.04 s** | ✅ |
| Lifecycle timeline | ≥ 3 audited events | **5 events, correct order** | ✅ |
| Idempotent resubmit | same id, no duplicate row | **same id returned** | ✅ |
| Motorola DMR ceiling | reject > 280 B | **`PAYLOAD_TOO_LARGE` at 400 B** | ✅ |
| STAR-V tactical radio | permanently locked out | **`LOCKED_OUT`; hard path raises** | ✅ |
| Transport selection | first READY/SIMULATION_ONLY adapter | **`motorola-mototrbo-01`** | ✅ |
| Routing priority | honoured, not ignored | **priority=1 wins over 50** | ✅ |
| Adapter result contract | every result carries `error_code` | **all adapters compliant** | ✅ |
| Checkpoint integrity | SHA-256 matches manifest | **match (epoch 16)** | ✅ |
| Apple Silicon acceleration | MPS detected, CPU fallback | **MPS available** | ✅ |
| SDR sample rate | 245.76 kS/s | **245760.0 S/s** | ✅ |
| SDR center frequency | 2.484 GHz | **2484000000.0 Hz** | ✅ |
| Frontend production build | compiles clean, no type errors | **`tsc -b` clean, 3070 modules, built in 721 ms** | ✅ |
| Frontend initial bundle | code-split, three.js deferred | **946 KB → 342 KB initial (gzip 94 KB)** | ✅ |
| 3D link view | lazy-loaded, degrades gracefully | **965 KB own chunk; 2D SVG fallback** | ✅ |
| Port | canonical 5050 | **5050** | ✅ |
| Ground-comms test count | suite grows, no regressions | **+ modem/listener/bridge/waveform tests; 202 total** | ✅ |
| Audio modem loopback | bit-exact, CRC-checked | **byte-exact over software loopback** | ✅ |
| Audio modem PER @ −4 dB wideband (10.26 dB in-band) | 0 at a usable SNR | **0.00 (60/60 frames)** | ✅ |
| Audio modem in-band gain | 10·log₁₀(48000/1800) = 14.26 dB | **14.26 dB** | ✅ |
| RX listener ingest idempotency | retransmit ⇒ one message | **content-hash key; 1 message for N repeats** | ✅ |
| RX listener is receive-only | no code path reaches PTT/playback | **tests make `play_audio`/`_load_gpio` raise** | ✅ |
| `auto` backend resolution | must not transmit blind | **resolves to `soundcard`, never MNIS** | ✅ |
| Pi 5 GPIO | works where `RPi.GPIO` fails | **`lgpio` shim; `probe` reports the loaded backend** | ✅ |
| RPi provisioning | idempotent, emits no RF | **`deploy.sh --dry-run` clean, 7/7 steps** | ✅ |
| Waveform Lab match | equal payload **and** equal bandwidth | **128 bits / 1024 samples on both tracks** | ✅ |
| Waveform Lab LPI result | live from the checkpoint | **8/8 domains PASS (`INDISTINGUISHABLE_FROM_NOISE`)** | ✅ |
| Waveform Lab conventional result | honest, not a strawman | **2/8 domains PASS (6 flip)** | ✅ |
| Waveform Lab degradation | never invent a number | **LPI → `UNAVAILABLE` + reason if torch/checkpoint absent** | ✅ |

---

## 4b. Ground-comms layer (Motorola + Raspberry Pi 5)

The physical layer was built and verified **in simulation on this machine**, because
no radio is attached here. Everything up to the antenna is tested; the radio is the
only remaining variable. Full runbook: `docs/GROUND_COMMS_DEPLOYMENT.md`.

### Two layers, stated honestly

The LPI-CGAN waveform is 245.76 kS/s baseband and needs an SDR; it **cannot fit a
~3 kHz voice channel**, so it is *not* routed over a Motorola. The radio is the
**narrowband message transport** (audio modem or MNIS); the covert waveform is the
separate wideband layer. The Waveform Lab page shows what the covert layer buys; the
radio path carries messages. Nothing pretends otherwise.

### The audio modem (transparent radio → byte pipe)

Differential BPSK, 1200 baud on a 1700 Hz carrier, RRC β = 0.5 (1800 Hz occupied),
Barker-13 sync after a 32-symbol alternating preamble, `u16` length + CRC-32, 4096-byte
max payload. Measured through AWGN + carrier offset + clock error (60 frames/point,
64-byte payload):

| Wideband SNR | In-band SNR | PER |
|---|---|---|
| −10 dB | 4.26 dB | 1.00 |
| −8 dB | 6.26 dB | 1.00 |
| −6 dB | 8.26 dB | 0.52 |
| −5 dB | 9.26 dB | 0.12 |
| **−4 dB** | **10.26 dB** | **0.00** |
| 0 dB | 14.26 dB | 0.00 |

The knee is at ≈10 dB in-band — comfortably below the SNR of any voice link a human
finds intelligible. The constant 14.26 dB gap between the two columns is the
bandwidth ratio (10·log₁₀(48000/1800)): the modem only hears its own 1800 Hz.

**Two-layer caveat, restated:** this table characterises the *modem*, not your radio
link. Only the field runbook (§6 of the deployment guide) can characterise that.

### What was verified without hardware

* **34** modem tests (bit-exact loopback, CRC rejection, CFO/clock sweeps, WAV round-trip).
* **20** voice-bridge tests and **7** bridge tests (dry-run gate, PTT lead/tail,
  always-de-key, `auto`→`soundcard`, `lgpio` fallback).
* **12** listener tests: content-hash idempotency, ingest error handling, JSONL
  logging, and the receive-only guarantee (the tests make `play_audio` and
  `_load_gpio` raise and assert nothing reaches them).
* The listener → platform path **end-to-end** via `motorola_rx_daemon.py --selftest`
  (decode → ingest → inbox), with duplicate-burst dedupe proven live.
* `scripts/rpi/deploy.sh --dry-run` (7/7 provisioning steps, no RF).
* The Waveform Lab comparison, live from the checkpoint (see §4 parameter table).

**Not verified here, by design:** real radios, real RF, real cabling. That is the
field runbook's job; everything up to the antenna is already boring.

---

## 5. Integration result (all phases synchronized)

`scripts/integration_e2e.py` — real server + embedded worker, throwaway DB:

```
[PASS] Server health after boot (s): 0.15
[PASS] React SPA served at / (HTTP + bundle root): 200
[PASS] Seeded endpoints: endpoint-a, endpoint-b
[PASS] Submit message (HTTP): 200
[PASS] Message reached terminal state: DELIVERED
[PASS] Time to delivery (s): 0.01
[PASS] Signed ACK receipt present: ACK-SIG:61c6435d:af44537...
[PASS] Recipient inbox contains message: 6
[PASS] Lifecycle events recorded: MESSAGE_ENQUEUED -> ... -> ACK_VALIDATED_DELIVERED
[PASS] Queue drained after delivery: 0
[PASS] Idempotent resubmit -> same id: 885c6a72-5e7e-4832-85f2-21dcae119d64
[PASS] Transport adapters advertised: 3
[PASS] Research status endpoint (HTTP): 200
[PASS] Integrity endpoint returns 8 EW domains: 8
[PASS] Integrity endpoint returns 6 operational checks: 6
[PASS] Integrity endpoint reports checkpoint identity: 0e8e5153…887c
[PASS] Integrity summary totals every domain: 14
[PASS] Integrity provenance is a live measurement: LIVE_COMPUTED
[PASS] Outbound path defaults to simulation: SIMULATION
[PASS] Console can select the Motorola radio path: motorola-mototrbo-01
[PASS] Message delivered over the live radio path: DELIVERED
[PASS] Worker honoured the shared transport switch: ['motorola-mototrbo-01']
[PASS] Operator can return to the simulated link: SIMULATION
RESULT: 23/23  →  INTEGRATION PASS
```

This single run exercises P1 (crypto/queue/ACK), P2 (inbox REST + timeline),
P3 (worker auto-delivery + idempotency), P4 (adapter registry **and live
dispatch onto the Motorola path, across the real server/worker process split**),
and P5 (research + integrity endpoints, including the live checkpoint identity and
the eight-domain EW summary) against the real network stack — not the test client.

---

## 6. Remaining known gaps (honest list)

| Item | Severity | Note |
|---|---|---|
| `app.py` legacy send/receive demo writes `last_tx_waveform.npy` but reads `last_rx_waveform.npy`; the whole legacy app is unreachable (defers to `messaging.server`) | Low | Dead legacy code; left untouched per the "preserve existing code" constraint. Recommend archiving `app.py` behind a `legacy/` folder. |
| GNU Radio `.grc` files hardcode `/home/user/Final-Project/...` paths | Medium | They are Linux-workstation artifacts. On the Pi/macOS, repoint `lpi_v4/run/lpi_v4.best.pt`. `.grc` are XML — safe to sed. |
| `ota_verify.py` / `make_synth_capture.py` use `FS = 32000`, while `lpi_v4` config is 245760 | Medium | Two different SDR experiments; document which is authoritative before field trials. |
| STAR-V unlock | By design | Permanently locked pending vendor ICD — correctly out of scope. |
| Motorola real RF | Gated | Requires `MOTOROLA_RADIO_APPROVED=true` **and** CLI `--approve` (or the API, with the flag), plus a band licence. The bridge, modem, listener and provisioning script all ship tested; the RF itself is yours to authorise. See `docs/GROUND_COMMS_DEPLOYMENT.md`. |
| LPI waveform over a voice channel | **By design, impossible** | The LPI-CGAN waveform is 245.76 kS/s wideband and cannot fit a ~3 kHz voice channel. The honest architecture is two layers: LPI = SDR covert layer; Motorola = tactical message transport. Documented, not faked. |
| Per-node ingest endpoints | Low | The RX listener's `--sender`/`--recipient` must reference endpoints that exist in the platform DB; the provisioning script does not seed them. |
| `test_simulation_1000_messages.py` exact-count assertions | Fixed | Were wall-clock sensitive (a slow machine let early failures re-acquire mid-pass: 346 instead of 200). Pinned the retry schedule for the test's duration; no assertion weakened, verified under 8-core load. |
| `SHADOWLINK-FIELD/` is a parallel field variant | Info | Duplicates adapters/models. Decide whether it merges into `Final-Project` or stays a separate deployment. |
| Console polling still uses `setInterval` (every 2 s) | Low | Phase A item 3 of `docs/WEB_REDESIGN.md`: move to `react-query` for caching + backoff. |
| 3D node click does not yet open the message drawer | Low | Phase B item: wire `onClick` on the station meshes to the existing message detail panel. |

---

## 7. Files changed / added

**Changed**
- `messaging/retry_policy.py`, `messaging/worker.py`, `messaging/db.py`, `messaging/server.py`, `messaging/api.py`
- `messaging/models.py` — added `SystemSetting` (shared cross-process selection)
- `requirements.txt`, `scripts/dev.sh`
- `integration/manager.py`, `integration/lpi_cgan/adapter.py`, `integration/starv/adapter.py`, `integration/motorola/adapter.py`
- `frontend/src/App.tsx` (code-split + topology tab + Waveform Lab route), `frontend/src/components/Header.tsx` (nav + Waveform Lab tab), `frontend/src/services/api.ts` (transport + waveform methods), `frontend/src/types/index.ts`, `frontend/package.json`
- `scripts/integration_e2e.py` — live-dispatch + integrity checks (now 23)
- `integration/motorola/hardware_bridge.py` — added `SoundCardBackend`, `lgpio` shim, honest `auto` resolution
- `scripts/rpi/ptt_test.py` — now uses the `RPi.GPIO`→`lgpio` loader (was `RPi.GPIO`-only, i.e. broken on a Pi 5)
- `tests/test_simulation_1000_messages.py` — pinned the retry schedule so its exact-count assertions no longer depend on machine speed
- `docs/MOTOROLA_RPI_INTEGRATION.md`, `docs/WEB_REDESIGN.md`, `docs/PHASE_AUDIT_REPORT.md`

**Added**
- `messaging/dispatch.py` — outbound path router (simulation ↔ live adapter) with 280 B chunking
- `tests/test_live_dispatch.py` — 12 router / worker / API tests
- `frontend/src/components/topology/LinkTopologyView.tsx` — 3D link view (lazy)
- `frontend/src/components/topology/model.ts` — pure scene-state derivation
- `frontend/src/components/topology/TopologyFallback.tsx` — dependency-free 2D fallback
- `frontend/src/components/ErrorBoundary.tsx`, `frontend/src/components/ViewLoader.tsx`
- `scripts/phase_audit.py` — per-phase independent audit harness
- `scripts/integration_e2e.py` — live end-to-end integration check
- `integration/motorola/hardware_bridge.py` — MNIS-UDP + **soundcard** + RPi GPIO PTT backends
- `integration/motorola/voice_modem.py` — the transparent audio modem (BPSK, RRC, Barker-13, CRC-32)
- `tests/integration/test_motorola_bridge.py`, `tests/integration/test_motorola_voice_bridge.py`, `tests/integration/test_voice_modem.py`
- `scripts/motorola_field_test.py` — operator CLI (`probe`/`selftest`/`loopback`/`tx`/`rx`/`run`)
- `scripts/motorola_rx_daemon.py` — receive-only listener, idempotent ingest into the platform
- `tests/integration/test_motorola_rx_daemon.py` — 12 listener/ingest/dedupe/no-transmit tests
- `scripts/rpi/deploy.sh` — idempotent Raspberry Pi 5 provisioning (dry-run, listener, gps)
- `scripts/rpi/shadowcomm-motorola-rx.service`, `scripts/rpi/shadowcomm-node.service`, `scripts/rpi/ptt_test.py`
- `integration/waveform_lab/service.py` — LPI vs. conventional comparison at matched payload/bandwidth
- `tests/test_waveform_lab.py` — 11 service/contract tests
- `frontend/src/components/WaveformLabView.tsx`, `frontend/src/components/waveform/WaveformCharts.tsx`
- `docs/GROUND_COMMS_DEPLOYMENT.md` — the field runbook (provisioning, wiring, two-terminal procedure, PER table, listener, two-layer architecture)
- `docs/MOTOROLA_RPI_INTEGRATION.md` — bridge/adapter reference (+ runtime switch section)
- `docs/WEB_REDESIGN.md` — UI modernisation plan (Phase A, B, C, C2 marked done)

> No git state was modified. No commits, pushes, or resets were performed.

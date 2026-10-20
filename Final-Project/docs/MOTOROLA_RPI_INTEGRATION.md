# Motorola Integration + Raspberry Pi Field Deployment

This guide describes the SHADOWCOMM **hardware bridge**: the adapter contract and
the three transports that carry SHADOWCOMM messages over real radios. It is the
reference for *how the bridge is built*; for the step-by-step field runbook
(provisioning, wiring, two-terminal procedure, measured performance, the always-on
listener) use **`docs/GROUND_COMMS_DEPLOYMENT.md`**.

> **Scope, stated plainly.** This is the **narrowband message transport** layer: a
> Motorola (or any) radio carrying SHADOWCOMM messages as an audio burst or MNIS
> data. The **LPI-CGAN covert waveform** is a separate wideband layer that needs an
> SDR and cannot fit a ~3 kHz voice channel — see
> `docs/GROUND_COMMS_DEPLOYMENT.md` §"Two layers". The two are complementary.

> **Safety first.** Nothing here transmits until you set
> `MOTOROLA_RADIO_APPROVED=true` **and** you hold a valid frequency/station
> licence for the band you are using. With the flag unset, every dispatch runs
> as a dry-run preview. This mirrors the STAR-V lockout philosophy — an
> unapproved transmitter is a bug, not a feature.

---

## 0. Where to start

| You want to… | Read |
|---|---|
| Provision a Pi 5 and run a live two-radio test | **`docs/GROUND_COMMS_DEPLOYMENT.md`** |
| Understand the adapter/bridge contract and backends | this document |
| Flip a running node between the simulated link and the radio | this document §"Switching the node live" |
| See the LPI-vs-conventional waveform comparison | `docs/WEB_REDESIGN.md` §"Waveform Lab" |

The two entry points into the hardware from a shell are:

* **`scripts/motorola_field_test.py`** — the operator CLI (`probe`, `selftest`,
  `loopback`, `tx`, `rx`, `run`). Everything except `tx`/`run --role tx` transmits
  nothing.
* **`scripts/rpi/deploy.sh`** — idempotent Pi 5 provisioning (systemd units, audio
  and GPIO groups, venv, `/etc/shadowcomm/motorola.env`). `--dry-run` first.
* **`scripts/motorola_rx_daemon.py`** — receive-only listener that POSTs decoded
  frames into the local SHADOWCOMM API (idempotent by content hash).


---

## 1. Architecture

```
  ┌────────────┐   HTTPS / WSS   ┌──────────────────────────┐
  │ Operator UI│ ──────────────► │  SHADOWCOMM core (Flask) │
  │ (browser)  │ ◄────────────── │  port 5050 + worker      │
  └────────────┘                 └────────────┬─────────────┘
                                              │ TransportManager.route_and_dispatch()
                                              ▼
                                   ┌──────────────────────────┐
                                   │ MotorolaMOTOTRBOAdapter  │  (280-byte DMR ceiling)
                                   └────────────┬─────────────┘
                                                │ MotorolaHardwareBridge
              ┌─────────────────────────────────┼─────────────────────────────────┐
              ▼                                 ▼                                 ▼
     ┌─────────────────┐             ┌──────────────────┐            ┌──────────────────┐
     │ mnis_udp        │             │ soundcard  ★     │            │ gpio_ptt         │
     │ (vendor IP path)│             │ (audio modem)    │            │ (serial bytes)   │
     └────────┬────────┘             └────────┬─────────┘            └────────┬─────────┘
              │ UDP :4001                     │ PTT + USB audio                │ PTT + UART
              ▼                               ▼                                ▼
     ┌─────────────────┐             ┌──────────────────┐            ┌──────────────────┐
     │ MOTOTRBO radio  │             │ Any radio        │            │ Radio with a     │
     │ + MNIS on host  │             │ (analogue / DMR) │            │ serial data port │
     └─────────────────┘             └──────────────────┘            └──────────────────┘
```

All three backends plug into the same adapter contract. Choose **one** per node via
`MOTOROLA_BACKEND=mnis_udp|soundcard|gpio_ptt|auto`. `auto` resolves to
**`soundcard`** (★), not MNIS — a UDP `connect()` cannot prove MNIS is listening, so
auto-selecting it could transmit into the void and report success. See
`docs/GROUND_COMMS_DEPLOYMENT.md` §1.

---

## 2. Which backend should you use?

| | `mnis_udp` | `soundcard` ★ | `gpio_ptt` |
|---|---|---|---|
| Works with | MOTOTRBO (DMR) with a data licence | **any** radio, analogue or digital | a radio with a serial data port |
| Needs vendor software | Yes (MOTOTRBO Network Interface Service) | No | No |
| Needs extra hardware | USB/IP link to radio, host running MNIS | USB sound card + 1 opto-isolator | opto-isolator + serial adaptor |
| Reliability | High when MNIS is stable | Highest; radio is just a byte pipe | High; needs a wired data port |
| Setup effort | Medium (CPS programming, radio IDs) | Low (a few wires) | Medium (serial + wiring) |
| **Recommendation** | When you already run MOTOTRBO infrastructure | **Start here** for a field pilot | When the radio exposes a data port |

`auto` selects `soundcard`, and only `soundcard`. MNIS must be requested
explicitly (`MOTOROLA_BACKEND=mnis_udp`) because it cannot be probed safely — see
§1. `gpio_ptt` writes raw serial bytes and therefore needs a radio that already
speaks a data protocol on its port.

---

## 3. Raspberry Pi bring-up

> The fast path is the provisioning script — `sudo bash scripts/rpi/deploy.sh`
> (review it first with `--dry-run`). It performs everything in §3.1–3.3, plus the
> GPIO/audio group membership and the `lgpio` install a Pi 5 needs. The steps below
> are the manual equivalent, for when you want to understand or change each one.

### 3.1 Flash and base packages

```bash
# Raspberry Pi OS Lite (64-bit), then:
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y python3-venv python3-pip git sqlite3 ufw \
                    alsa-utils libportaudio2 portaudio19-dev \
                    liblgpio1 python3-lgpio
sudo usermod -aG gpio,audio,dialout "$USER"

# Clone your project onto the Pi
git clone <your-repo-url> ~/shadowcomm
cd ~/shadowcomm/Final-Project
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install sounddevice rpi-lgpio lgpio     # audio + Pi 5 GPIO
```

> **Pi 5 GPIO.** `RPi.GPIO` **does not work on a Raspberry Pi 5** — the GPIO block
> moved behind the RP1 southbridge, so the old `/dev/gpiomem` path no longer
> describes it (`RuntimeError: Cannot determine SOC peripheral base address`).
> `rpi-lgpio` + `lgpio` provide the working path; the bridge falls back to an
> `lgpio` shim automatically and `probe` prints which backend loaded.

> Torch on a Pi is heavy (~1 GB). If the node only relays messages (no LPI
> research), install a trimmed set: `pip install flask sqlalchemy pycryptodome
> reedsolo requests numpy` and run with the research views disabled.

### 3.2 Configure the node (`.env`)

```bash
# --- Messaging core ---
SHADOWCOMM_ADMIN_PASSWORD=<change-me>
SHADOWCOMM_OPERATOR_PASSWORD=<change-me>

# --- Motorola hardware path (leave OFF until licensed) ---
MOTOROLA_RADIO_APPROVED=false
MOTOROLA_BACKEND=soundcard         # or mnis_udp / gpio_ptt / auto

# soundcard (recommended):
MOTOROLA_PTT_GPIO=17
MOTOROLA_AUDIO_OUT=default         # e.g. plughw:1,0 for the USB dongle
MOTOROLA_AUDIO_IN=default
MOTOROLA_AUDIO_FS=48000
MOTOROLA_PTT_LEAD_MS=250           # key PTT before audio starts
MOTOROLA_PTT_TAIL_MS=150           # hold PTT after audio ends

# mnis_udp:
MOTOROLA_MNIS_HOST=127.0.0.1
MOTOROLA_MNIS_PORT=4001

# gpio_ptt:
MOTOROLA_SERIAL_PORT=/dev/ttyUSB0
```

### 3.3 Install the systemd service

```bash
sudo cp scripts/rpi/shadowcomm-node.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now shadowcomm-node
systemctl status shadowcomm-node
curl -s http://127.0.0.1:5050/api/v1/health
```

For the always-on receive listener, install `scripts/rpi/shadowcomm-motorola-rx.service`
(`deploy.sh --with-listener`) — see `docs/GROUND_COMMS_DEPLOYMENT.md` §7.

---

## 4. Wiring the PTT path

The PTT wiring is identical for the `soundcard` and `gpio_ptt` backends; only the
payload medium differs (audio burst vs. serial bytes).

```
 Raspberry Pi 5                   Radio (3.5/2.5 mm + PTT)
 ───────────────                  ────────────────────────
 GPIO17 (pin 11) ──► [1kΩ] ──► opto LED (PC817)
 GND    (pin 6)  ────────────► opto cathode
                                 opto transistor collector ──► PTT line
                                 opto transistor emitter   ──► radio GND
 USB sound card  ──────────────► MIC  (modem audio out)
 radio SPKR      ──────────────► USB sound card line-in
```

- The opto-isolator keeps the radio's ground isolated from the Pi.
- **Never** connect GPIO directly to a radio PTT line.
- Set the radio to a data-capable mode and **disable VOX** (VOX clips the burst head).

Safe, non-transmitting pin test (keys PTT briefly, sends NO data). Works on a Pi 5
(uses the same `lgpio` fallback as the transmit path):

```bash
python scripts/rpi/ptt_test.py --pin 17              # report only
python scripts/rpi/ptt_test.py --pin 17 --confirm    # pulse 200 ms
```

---

## 5. Operator CLI — the fast path

`scripts/motorola_field_test.py` wraps all of the above so you rarely touch these
internals. It transmits **nothing** except `tx` / `run --role tx`.

```bash
python scripts/motorola_field_test.py probe      # hardware inventory, no RF
python scripts/motorola_field_test.py selftest   # modem vs. simulated channel
python scripts/motorola_field_test.py loopback   # message -> TMS -> audio -> decode
python scripts/motorola_field_test.py run --role rx --count 6
MOTOROLA_RADIO_APPROVED=true \
  python scripts/motorola_field_test.py run --role tx --approve --message "..." --count 6
```

Full two-terminal procedure and the measured PER/SNR table are in
`docs/GROUND_COMMS_DEPLOYMENT.md` §6.

---

## 6. Backend `mnis_udp` — quick reference

1. Program each MOTOTRBO radio in CPS: unique Radio ID, **Data Services on**,
   and the feature licence for *Text Message Service / IP data*.
2. Connect the radio to the host (USB or IP) and start **MOTOTRBO Network
   Interface Service**.
3. Note the UDP port MNIS exposes for data (commonly `4001`).
4. Point SHADOWCOMM at it: `MOTOROLA_MNIS_HOST`, `MOTOROLA_MNIS_PORT`.
5. Verify reachability without transmitting:

```bash
python - <<'PY'
from integration.motorola.hardware_bridge import MotorolaHardwareBridge
import json; print(json.dumps(MotorolaHardwareBridge(backend="mnis_udp").probe(), indent=2))
PY
```

---

## 7. Verifying end to end

```bash
# 1) Contract + dry-run (no RF):
python -m pytest tests/integration/test_motorola_bridge.py -v

# 2) Whole-stack probe (no RF):
curl -s http://127.0.0.1:5050/api/v1/transports | python -m json.tool

# 3) Arm the radio ONLY after licensing, then send a real 280-byte-max message.
export MOTOROLA_RADIO_APPROVED=true
curl -s -X POST http://127.0.0.1:5050/api/v1/messages \
  -H 'Content-Type: application/json' \
  -d '{"sender_endpoint_id":"endpoint-a","recipient_endpoint_id":"endpoint-b",
       "payload":"FIELD-CHECK-01","client_idempotency_key":"field-001"}'
```

Success looks like `"current_state":"DELIVERED"` with a populated
`signed_ack_receipt` (SDR-only hops will show `SIMULATION_ONLY`).

---

## 7a. Switching the node live (runtime, no restart)

By default the delivery worker pushes everything through the **simulated link**.
You can move the whole node onto the radio path at runtime — from the console's
**3D Link View → "GO LIVE (MOTOROLA)"** button, or over the API:

```bash
# Go live on the radio path:
curl -s -X POST http://127.0.0.1:5050/api/v1/transports/active \
  -H 'Content-Type: application/json' \
  -d '{"transport_id":"motorola-mototrbo-01"}'

# Check what the node is using (includes a live bridge probe):
curl -s http://127.0.0.1:5050/api/v1/transports/active | python -m json.tool

# Return to the simulated link:
curl -s -X POST http://127.0.0.1:5050/api/v1/transports/active \
  -H 'Content-Type: application/json' -d '{"transport_id":null}'
```

**How this works (important):** the web API and the delivery worker run as
*separate processes*. The selection is therefore persisted to a shared
`system_settings` row, and the worker re-reads it before every delivery cycle
(≤ 1 s). That means the switch takes effect across processes without a restart.

Precedence: **shared setting → `SHADOWCOMM_LIVE_TRANSPORT` env pin → simulation.**
An air-gapped unit with no console can be pinned permanently:

```bash
export SHADOWCOMM_LIVE_TRANSPORT=motorola-mototrbo-01   # in .env
```

Safety is unchanged by all of the above: without `MOTOROLA_RADIO_APPROVED=true`
the hardware bridge still runs **dry-run only** — selecting the path never
emits RF on its own.

Outbound frames larger than the 280-byte DMR ceiling are split into ordered,
self-describing chunks (`<uint16 total><uint16 index><data>`) and handed to the
adapter one at a time, so a long tactical message rides the radio path instead
of failing with `PAYLOAD_TOO_LARGE`.

---

## 8. Operational checklist

- [ ] Band licence and radio IDs documented
- [ ] `.env` passwords rotated from defaults
- [ ] `MOTOROLA_RADIO_APPROVED=false` during bench tests
- [ ] PTT opto-isolator installed (radio GND isolated)
- [ ] `probe` reports the expected GPIO backend (`lgpio` on a Pi 5) and sound card
- [ ] `selftest` and `loopback` both pass before the first live transmission
- [ ] Receive listener enabled if used: `systemctl enable --now shadowcomm-motorola-rx`
- [ ] `ufw` allows only 5050 on the LAN: `sudo ufw allow from 192.168.0.0/16 to any port 5050`
- [ ] Nightly DB backup: `sqlite3 shadowcomm_messaging.db ".backup /var/backups/shadowcomm-$(date +%F).db"`
- [ ] Watchdog: `systemctl enable --now shadowcomm-node` (auto-restart on crash)

---

## 9. See also

* **`docs/GROUND_COMMS_DEPLOYMENT.md`** — the field runbook: provisioning, PTT
  wiring detail, two-terminal procedure, measured PER/SNR table, the always-on
  listener and its idempotent ingest, and the two-layer (LPI vs. voice-channel)
  architecture explained honestly.
* `docs/WEB_REDESIGN.md` — the console, including the Waveform Lab page.
* `docs/PHASE_AUDIT_REPORT.md` — the verification record.

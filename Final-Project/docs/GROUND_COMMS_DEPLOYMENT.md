# SHADOWCOMM Ground-Comms Deployment — Motorola Radios + Raspberry Pi 5

This is the field runbook for putting SHADOWCOMM on **real radios**. It covers the
transparent audio-modem path (the recommended one), the MNIS path, provisioning a
Raspberry Pi 5, wiring PTT safely, and the exact order of operations that keeps the
first transmission boring.

> **Two layers, stated honestly.**
> SHADOWCOMM is a **two-layer** system, and this document only implements the
> second layer.
>
> * **Layer 1 — LPI covert waveform (wideband).** The LPI-CGAN waveform is
>   245.76 kS/s baseband, ~1.8 MHz-class occupancy once on a carrier. It needs an
>   SDR (USRP/pluto-class) as the radio. It is *not* placed on a Motorola here,
>   because it **cannot fit a ~3 kHz voice channel.**
> * **Layer 2 — tactical message transport (narrowband).** This document. A
>   Motorola (or any) radio carries SHADOWCOMM messages as an audio burst or as
>   MNIS data PDUs. The radio is a **byte pipe**; the covert waveform is not this
>   path's job.
>
> Anyone claiming "LPI over a handheld voice channel" is either lying or shipping
> noise. The two layers are complementary: the radio carries the message, an SDR
> would carry the covert signal.

---

## 1. The three transports

All three live in `integration/motorola/hardware_bridge.py` and plug into the same
adapter contract (`integration/motorola/adapter.py`, 280-byte DMR ceiling).

| | `mnis_udp` | `soundcard` *(recommended)* | `gpio_ptt` |
|---|---|---|---|
| Path | MOTOTRBO Network Interface Service over UDP | USB sound card + GPIO PTT = audio modem | GPIO PTT + UART/serial bytes |
| Works with | MOTOTRBO with a data licence | **any** radio, analogue or digital | a radio with a serial data port |
| Vendor software | Yes (MNIS) | No | No |
| Extra hardware | IP/USB link to radio, host running MNIS | USB sound card + 1 opto-isolator | opto-isolator + serial adaptor |
| Programming | CPS: radio IDs, data mode | none | none |
| **Use it when** | you already run MOTOTRBO infrastructure | you are starting a field pilot | you have a wired data port |

### Why `MOTOROLA_BACKEND=auto` resolves to `soundcard`, not MNIS

A UDP `connect()` proves nothing: it cannot tell you whether MOTOTRBO Network
Interface Service is actually listening. Auto-selecting MNIS would therefore risk
**transmitting into the void and reporting success** — the worst possible failure
mode for a comms system. The sound-card path either works or fails loudly, so it is
the honest default. Force MNIS explicitly only when you know it is up:

```bash
export MOTOROLA_BACKEND=mnis_udp    # only when MNIS is confirmed running
```

---

## 2. What you need

* **Raspberry Pi 5** (4 GB is plenty for the node role) + PSU + microSD (16 GB+).
* **Two radios** — any Motorola handheld with a 3.5/2.5 mm audio jack and a PTT
  line. Analogue or DMR; the modem does not care.
* **USB sound card** (a €5 dongle is fine — the onboard Pi analogue audio is noisy).
* **1 × opto-isolator** (e.g. PC817 / 4N35) + 1 kΩ resistor. Non-negotiable: never
  drive a radio PTT line directly from GPIO.
* **Licence** for the frequency/band you will use, and the operator's authority to
  transmit. The software cannot grant this and will not pretend to.
* Cables: 3.5/2.5 mm to the sound card, and access to the radio's PTT contact.

---

## 3. Provision the Pi 5

One idempotent script does the whole node. Run it **on the Pi**:

```bash
git clone <your-repo> ~/shadowcomm-src
cd ~/shadowcomm-src/Final-Project
bash scripts/rpi/deploy.sh --dry-run      # review every step first
sudo bash scripts/rpi/deploy.sh           # apply
```

`deploy.sh` performs, in order:

| Step | What |
|---|---|
| 1 | `apt-get` base packages incl. `alsa-utils`, `libportaudio2`, `liblgpio1`, `python3-lgpio` |
| 2 | Adds the node user to `gpio spi audio dialout`; installs a GPIO `udev` rule |
| 3 | rsyncs the repo into `$HOME/shadowcomm` |
| 4 | Creates a venv and installs `requirements.txt` + `sounddevice rpi-lgpio lgpio` |
| 5 | Writes `/etc/shadowcomm/motorola.env` (only if absent) with `MOTOROLA_RADIO_APPROVED=false` |
| 6 | Installs the systemd units (node server, and — with `--with-listener` — the receive listener) |
| 7 | Verifies: runs the modem self-test and the hardware probe. **Transmits nothing.** |

Flags: `--dry-run` (show, change nothing) · `--with-listener` (install the always-on
RX service) · `--with-gps` (install GPS time source).

### Why the Pi 5 needs `lgpio`

`RPi.GPIO` **does not work on a Pi 5.** The Pi 5 moved the GPIO block behind the RP1
southbridge, so the old `/dev/gpiomem` mapping no longer describes it. The bridge
therefore tries `RPi.GPIO` first and falls back to an `lgpio` shim
(`LgpioShim` in `hardware_bridge.py`); `deploy.sh` installs `rpi-lgpio` + `lgpio`.
The probe reports which backend actually loaded (`GPIO backend` line), so a silent
fallback is impossible.

### Configuration

`/etc/shadowcomm/motorola.env` (installed with the flag OFF):

```ini
MOTOROLA_RADIO_APPROVED=false
MOTOROLA_BACKEND=soundcard          # or mnis_udp / gpio_ptt
MOTOROLA_PTT_GPIO=17
MOTOROLA_AUDIO_OUT=default          # or plughw:1,0 for the USB dongle
MOTOROLA_AUDIO_IN=default
MOTOROLA_AUDIO_FS=48000
MOTOROLA_PTT_LEAD_MS=250            # key PTT this long before audio starts
MOTOROLA_PTT_TAIL_MS=150            # hold PTT this long after audio ends
# MNIS only:
MOTOROLA_MNIS_HOST=127.0.0.1
MOTOROLA_MNIS_PORT=4001
```

---

## 4. Wire the PTT path

```
 Raspberry Pi 5                      Radio (audio jack + PTT contact)
 ───────────────                     ────────────────────────────────
 GPIO17 (pin 11) ──► [1kΩ] ──► opto LED (PC817 anode)
 GND    (pin 6)  ─────────────► opto LED cathode
 3V3/GND         ──► transistor collector ──► radio PTT
                     transistor emitter   ──► radio GND (its own ground)
 USB sound card  ──► radio MIC  (modem audio out)
 radio SPKR      ──► USB sound card line-in (modem audio in)
```

Rules that matter:

* The opto-isolator keeps the radio's ground off the Pi's. **Never** wire GPIO
  straight to a PTT line.
* Set the radio to a data/voice mode and **disable VOX** (VOX clips the burst head).
* Set radio volume to a mid level; check for clipping with the probe (below).
* Bench test PTT pin toggling **without** audio first:

```bash
python scripts/rpi/ptt_test.py --pin 17        # report only; keys nothing
python scripts/rpi/ptt_test.py --pin 17 --confirm   # pulse PTT 200 ms; still no data
```

### Why the PTT lead/tail exist

A radio keyed for only the length of the audio will clip the burst's first symbol
and lose sync. The bridge therefore **keys PTT 250 ms before audio** and **holds it
150 ms after**. On *every* failure path the PTT line is released — a stuck
transmitter is both a licence breach and a jamming hazard, so the tests assert
de-key on every exception.

---

## 5. The audio modem

`integration/motorola/voice_modem.py`. Design choices, briefly:

| Property | Value | Why |
|---|---|---|
| Modulation | differential BPSK | differential = no absolute phase reference needed after a deep fade |
| Symbol rate | 1200 baud | sits in the passband of every narrowband voice channel |
| Carrier | 1700 Hz | centre of a 300–3400 Hz voice channel |
| Pulse | RRC, β = 0.5 | band-limited; keeps the burst inside the channel |
| Occupied BW | ≈ 1800 Hz | fits a 3 kHz voice channel with margin |
| Sync | Barker-13 after a 32-symbol alternating preamble | unambiguous frame sync, robust to inversion |
| Framing | `u16 length` + payload + **CRC-32** | bad frames are rejected, never passed off as good |
| Max payload | 4096 B | larger messages are chunked by the adapter, not silently truncated |
| Air time | 0.504 s for 64 B | makes PER measurement meaningful per burst |

The channel simulator adds **AWGN + carrier offset (CFO) + clock error (ppm)**. A
carrier offset must rotate the *analytic* signal; multiplying a double-sideband
signal by `cos(2π·cfo·n)` produces amplitude modulation, not a carrier shift — a bug
that was caught and fixed, and which the `--selftest` CFO sweep now guards.

Everything is provable **without hardware**:

```bash
# 60 frames through a simulated channel at a chosen SNR. Transmits nothing.
python scripts/motorola_field_test.py selftest --frames 60 --snr 0
```

---

## 6. Two-terminal field runbook

Run each step in order. The first three transmit nothing, so the first *real*
transmission is the TX command below — and by then you already know everything else
works.

```bash
# On the TX terminal (the operator's Pi):
python scripts/motorola_field_test.py probe        # 1. inventory, no RF
python scripts/motorola_field_test.py selftest     # 2. modem vs. a simulated channel
python scripts/motorola_field_test.py loopback     # 3. message -> TMS -> audio -> decode
```

**Only after both operators are on frequency and listening:**

```bash
# Terminal B — listen (no approval needed; receive never transmits)
python scripts/motorola_field_test.py run --role rx --count 6

# Terminal A — transmit (needs the licence gate, see §8)
export MOTOROLA_RADIO_APPROVED=true
python scripts/motorola_field_test.py run --role tx --approve \
    --message "SITREP LIMA-3 GRID 31U-DQ-8842 NOMINAL" --count 6
```

`probe` prints the hardware inventory: sound card present, GPIO backend (`RPi.GPIO`
vs `lgpio`), modem plan, and the gate state. `selftest` proves the DSP.
`loopback` proves the whole chain (message → TMS frame → audio → demodulate →
parse) **in software, with no radio**.

Common options (`--backend`, `--gpio-pin`, `--audio-out/in`, `--sample-rate`,
`--report`, `--approve`) are accepted **before or after** the sub-command, because
that is how people actually type.

---

## 6a. Measured link performance

From the modem's own self-test — 60 frames per point, 64-byte payload, 5 Hz carrier
offset, 20 ppm clock error. "Wideband" is noise over the full 48 kHz sound-card
band; "in-band" is noise over the modem's 1800 Hz occupied band. Reproduce with
`selftest --frames 60 --snr <dB>`.

| Wideband SNR | In-band SNR | Packet error rate |
|---|---|---|
| −10 dB | 4.26 dB | 1.00 |
| −8 dB | 6.26 dB | 1.00 |
| −6 dB | 8.26 dB | 0.52 |
| −5 dB | 9.26 dB | 0.12 |
| **−4 dB** | **10.26 dB** | **0.00** |
| −3 dB | 11.26 dB | 0.00 |
| −2 dB | 12.26 dB | 0.00 |
| 0 dB | 14.26 dB | 0.00 |

Two readings of the same table:

* The **knee is at ≈10 dB in-band**. Below it the link falls off a cliff (this is a
  coherent BPSK decision boundary, so it should). A voice channel a human finds
  intelligible is comfortably above 10 dB, so a working voice link is a working data
  link.
* The **in-band gain is a constant 14.26 dB** (`10·log10(48000/1800)`): the modem
  only listens where its energy lives, so it tolerates 14 dB more wideband noise
  than the raw SNR suggests.

> These are **simulated-channel** numbers. They characterise the modem, not your
> radios. The field runbook exists precisely to measure the real ones.

---

## 7. Always-on receive listener

For an unattended RX node, `scripts/motorola_rx_daemon.py` + the systemd unit
`scripts/rpi/shadowcomm-motorola-rx.service`:

```bash
sudo bash scripts/rpi/deploy.sh --with-listener
sudo systemctl status shadowcomm-motorola-rx
journalctl -u shadowcomm-motorola-rx -f
```

It records a window, demodulates, and — on a clean CRC — **POSTs the message into
the local SHADOWCOMM API**, so radio traffic lands in the platform inbox beside
everything else. Idempotency is keyed on a **SHA-256 of the decoded frame**, so a
radio retransmission (or an operator repeating a callsign) is recognised as the
existing message, not a new one.

The unit is hardened and **cannot transmit**: it runs the `soundcard` backend
without ever calling `send`, and the tests assert the receive path never reaches
`play_audio`. Nothing it does can key a radio.

Verify the listener → platform path **with no radio**:

```bash
python scripts/motorola_rx_daemon.py --selftest --api http://127.0.0.1:5050
```

This injects one burst through the software loopback, decodes it, and ingests it —
one decoded, one ingested — using the exact code path the service uses. It touches
no hardware: the tests assert that even self-test cannot reach the GPIO.

---

## 8. The licence gate

Transmission is closed until **both** conditions hold:

1. `MOTOROLA_RADIO_APPROVED=true` is set, **and**
2. the CLI `run --role tx` is given `--approve` (or the API path is used with the
   flag set).

With the flag unset, `tx` and `run --role tx` run as **DRY-RUN** and print exactly
what *would* have been sent. Two deliberate exceptions, both of which emit no RF:

* **Software loopback** (`SoundCardBackend(self_loopback=True)`, used by `loopback`
  and the daemon `--selftest`) captures the audio in memory. It sits *before* the
  gate because it is not a transmission — but it still reports `dry_run=True` so no
  caller can mistake it for RF.
* **Receive** never needs the gate: it keys nothing.

Procedure to go live, once and only once the licence is in hand:

1. Confirm both radios are on the licensed channel and a second operator is listening.
2. `export MOTOROLA_RADIO_APPROVED=true`.
3. `run --role tx --approve --count 1` with a short callsign-style message.
4. Confirm the RX terminal decodes it and the inbox receives it.
5. If anything is wrong, `unset MOTOROLA_RADIO_APPROVED` — the gate closes instantly.

---

## 8a. Where the LPI comparison lives

The LPI-vs-conventional comparison is a **web page**, not a radio path: the
**Waveform Lab** tab (and `GET /api/v1/research/waveform-comparison?frames=<1..16>`).
It runs both waveforms through the *same* eight-domain EW battery at matched
payload (128 bits/frame) and matched sample budget (1024 real samples/frame) at
245.76 kS/s, so neither column is given a bandwidth advantage.

Live result from the current checkpoint (`lpi_v4/run/lpi_v4.best.pt`):

| Domain (gate) | LPI-CGAN | Conventional QPSK | Flip |
|---|---|---|---|
| KS p-value vs. Gaussian (p > 0.05) | **0.849** ✅ | 3.1e-140 ❌ | yes |
| Kurtosis (\|v−3\| < 0.15) | **2.945** ✅ | 1.465 ❌ | yes |
| Spectral entropy (> 0.95) | **0.958** ✅ | 0.595 ❌ | yes |
| IQ circularity (< 0.15) | **0.014** ✅ | 0.018 ✅ | no |
| PAPR deviation (\|v\| < 3.0) | **−0.10** ✅ | −3.91 ❌ | yes |
| SCF ratio (< 3.0) | **1.018** ✅ | 0.408 ✅ | no |
| HOS C42 (\|v\| < 0.3) | **−0.013** ✅ | −0.776 ❌ | yes |
| WVD ratio (< 3.7) | **1.049** ✅ | 5.624 ❌ | yes |
| **Total** | **8/8** | **2/8** | **6 flip** |

Representative live run (`frames=8`). The generator draws fresh latent noise per
call and the conventional payload bits are drawn per call too, so the last digits
move between runs. The *result* does not: **8/8 vs 2/8 with 6 of 8 domains
flipping**, every time.

The page states the same disclaimer the API returns: these are laboratory
statistics from a software model, not a field guarantee — a pass means "this
reference detector cannot separate the waveform from Gaussian noise in this
domain", not "undeceivable".

---

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `GPIO_UNAVAILABLE` on a Pi 5 | `RPi.GPIO` installed instead of `lgpio` | `pip install rpi-lgpio lgpio`; check the `GPIO backend` line in `probe` |
| `no decode :: neither sounddevice nor arecord is available` | no capture backend | `sudo apt-get install alsa-utils` or `pip install sounddevice` |
| PTT keys but nothing decodes | audio too quiet, clipped, or VOX on | check `probe` levels (`rms`/`peak`/`clipped_fraction`); disable VOX; raise radio volume |
| Decodes on the bench, not in the field | multipath/fade; burst head clipped | increase PTT lead; shorten payload; retransmit (the listener dedupes the duplicates) |
| `MOTOROLA_RADIO_APPROVED is not set` | gate closed | expected — set the flag only when licensed |
| Ingests fail with `HTTP 400: Sender endpoint ... does not exist` | the endpoint IDs in the env don't exist in the platform | seed or point `--sender`/`--recipient` at real endpoints |
| Inbox shows duplicates | should not happen | idempotency key is the SHA-256 of the frame; check the log's `ingest` field |

---

## 10. Proven vs. not proven

**Proven here (this machine, simulation only):**

* The modem is bit-exact and CRC-checked through an AWGN + CFO + clock-error channel
  (34 modem tests, 12 listener tests, 20 voice-bridge tests).
* The PTT safety contract: dry-run without approval, de-key on every failure path.
* The listener → platform path end-to-end (decode → dedupe → inbox), driven by the
  real code path via `--selftest`.
* The Waveform Lab comparison, live from the checkpoint at matched payload/bandwidth.
* The RPi provisioning script is idempotent and its `--dry-run` is clean.

**Not proven here — because it needs your hardware:**

* Real radios in the real band, at real distance, with real RF noise.
* Your cabling, your audio levels, your exact Motorola model's PTT contact.
* The actual on-air packet error rate. §6a characterises the *modem*; only §6
  characterises *your link*.

That gap is deliberate and is exactly what the field runbook is for: everything
up to the antenna is tested and boring, so the only new variable on the bench is
the radio.

---

## 10a. Operations & security checklist

- [ ] Band/station licence on file; operator authorised to transmit
- [ ] `MOTOROLA_RADIO_APPROVED=false` for all bench work
- [ ] Opto-isolator fitted; radio and Pi grounds separated
- [ ] Passwords in `.env` rotated from defaults
- [ ] `ufw` allows 5050 only from the LAN: `sudo ufw allow from 192.168.0.0/16 to any port 5050`
- [ ] Nightly DB backup: `sqlite3 shadowcomm_messaging.db ".backup /var/backups/shadowcomm-$(date +%F).db"`
- [ ] `systemctl enable --now shadowcomm-node` (server) and, if used, `shadowcomm-motorola-rx` (listener)
- [ ] Journal reviewed after the first live transmission

---

## 11. Related documents

* `docs/MOTOROLA_RPI_INTEGRATION.md` — the adapter/bridge contract and the runtime
  "go live" switch.
* `docs/WEB_REDESIGN.md` — the console, including the Waveform Lab page.
* `docs/PHASE_AUDIT_REPORT.md` — the verification record for this work.

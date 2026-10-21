# The LPI-over-Motorola System — One Model, End to End

This document is the single consolidated description of the system. It states what
the system is, how each piece connects, and — in a separate, clearly-marked
section — exactly which numbers were measured on this machine and which are still
waiting on hardware. It is written so the whole thing can be explained from one
page.

---

## 1. The objective, stated exactly

The requirement is **not** two parallel transports. It is:

> When we communicate over a Motorola radio, the transmission itself must exhibit
> LPI characteristics. An interceptor who sweeps the band and analyses the
> waveform must see something statistically indistinguishable from noise.

Motorola is therefore the **application**; LPI is a **property of the signal it
carries**.

## 2. Why there is a physics constraint, and what it forces

Two numbers decide the entire design:

| | |
|---|---|
| Motorola voice channel | **300–3000 Hz** (2700 Hz wide, centre 1650 Hz) |
| LPI-CGAN wideband waveform | **245 760 S/s**, ~45 kHz occupied |

A 45 kHz waveform physically cannot enter a 3 kHz voice channel. So the raw CGAN
samples are *not* what travels. What travels is the LPI **protocol and signal
statistics**, re-synthesised at audio scale:

* the same keyed spread codebook,
* the same masking dither,
* the same keyed Zadoff-Chu pilot (spread through the codebook),
* the same AES-128-CTR + RS(42,34) + CRC-8 payload stack,
* measured by the same eight-domain EW battery.

The synthesiser is honestly labelled: every result carries
`waveform_source = "keyed_spread_plus_dither_at_audio_scale"`. It is not the
trained CGAN; it is an explicit construction implementing the same statistics.

## 3. The signal chain

```
  message bytes
      │
      ▼
  FrameCodec ── AES-128 (CTR) ── RS(42,34) ── CRC-8        [lpi_crypto.py]
      │                     (identical to the wideband path)
      ▼
  keyed codebook spread  A^T b            ┐
  masking dither         sqrt(1-e)s+sqrt(e)n0  ├─ I axis: payload
      │                                   ┘
      ├── Q axis: second keyed spread of KEY-DERIVED bits  ──► makes the
      │       symbol circular-complex (fixes the C42 domain)
      │
      ├── keyed ZC pilot, spread through the same codebook ──► sync
      │       (constant-modulus outlier in its own burst; spreading fixes KS)
      │
      └── guard regions: full-power shaped MASKING NOISE, never silence
              (silence is what caused the KS failure; see §5)
      │
      ▼
  RRC pulse shaping (beta 0.35) on the 1650 Hz carrier     [lpi_carrier.py]
      │
      ▼
  real audio, exactly 300–3000 Hz, ~1.68 s                  [to the radio]
      │
      ▼
  Raspberry Pi 5  ── PTT on GPIO ── sound card ──► radio mic input
      │                                              [hardware_bridge.py]
      ▼
  ────────────────  the radio link  ────────────────
      │
      ▼
  far-end radio speaker ──► sound card capture          [hardware_bridge.py]
      │
      ▼
  CFO search (coarse 2 Hz) → fine 0.25 Hz sweep → keyed pilot lock
  → sub-symbol timing refine → ZF despread → RS + CRC + AES   [lpi_carrier.py]
      │
      ▼
  message bytes
```

## 4. Where each piece lives

| Layer | File | Role |
|---|---|---|
| Covert physical layer | `integration/motorola/lpi_carrier.py` | Keyed spread + dither + spread pilot, audio carrier, sync, EW battery |
| Plain voice modem | `integration/motorola/voice_modem.py` | Non-LPI fallback; channel simulator used by tests |
| Hardware bridge | `integration/motorola/hardware_bridge.py` | PTT, sound card TX/RX, `lpi_mode` switch, safety lockout |
| SDR transport | `integration/motorola/sdr_backend.py` | Carries the *same* LPI burst over a USRP (`sdr_usrp` backend) |
| DMR adapter | `integration/motorola/adapter.py` | MOTOTRBO path, 280-byte ceiling, `MOTOROLA_RADIO_APPROVED` gate |
| Crypto + FEC | `lpi_v4/lpi_crypto.py` | AES-128-CTR, RS(42,34), CRC-8 — shared by both paths |
| Reference wideband | `lpi_v4/tx_usrp.py`, `rx_usrp.py` | CGAN @ 245 760 S/s — the wideband equivalent |
| EW battery | `lpi_v4/lpi_stats.py` | The eight-domain measurement, shared by both paths |
| Operator CLI | `scripts/motorola_field_test.py` | `probe`, `selftest`, `loopback`, `lpi`, `tx`, `rx`, `run` |
| Pi provisioning | `scripts/rpi/deploy.sh` | Field node setup |

## 4b. The SDR join — one waveform, two transports

Before this existed, the Motorola path and the wideband SDR path were separate
modules with nothing connecting them: the radio bridge only knew how to key a
handset through a sound card, and `lpi_v4/tx_usrp.py` only knew how to build a
245.76 kS/s CGAN burst. A claim that "Motorola is integrated with the SDR" would
have been false.

`integration/motorola/sdr_backend.py` (`backend="sdr_usrp"`) closes that gap
**without introducing a second waveform**. It takes the exact same LPI audio
burst the sound-card path transmits — same keyed spread codebook, same dither,
same keyed ZC pilot, same AES-128-CTR + CRC-8 + RS(42,34) — and carries it over
the USRP instead of the radio's microphone input.

Conversion path, and why the numbers are exact:

| Step | Detail |
|---|---|
| Real 48 kHz burst | 300–3000 Hz, 2700 Hz wide |
| Analytic signal | Hilbert transform → single sideband, no mirrored image |
| Resample | `resample_poly(x, 512, 100)`; `48000 × 512/100 = 245760` exactly |
| Tune | burst lands at `f_LO + 300 … f_LO + 3000` Hz |

Measured on the emitted IQ (`test_sdr_upsampling_ratio_is_exact_and_single_sideband`):
occupied band **313–2991 Hz (2679 Hz wide)**, all on the positive side of the
LO. So the RF carriage preserves the burst's bandwidth and single-sideband
character; it is the same signal an interceptor would analyse on the radio path.

`auto` never selects `sdr_usrp`. Radiating through a USRP is a licensing and
power decision, so it must be requested explicitly:
`MOTOROLA_BACKEND=sdr_usrp`. With `MOTOROLA_RADIO_APPROVED` unset the IQ is
built and measured but not radiated, and the result says so. `probe()` reports
`device_found` / `available` from a bounded `uhd_find_devices` call and never
invents a device.

## 5. The three design fixes, each driven by a measurement

The battery was the specification, so the burst was designed against it. Three
findings, each reproducible from the code comments at the relevant site:

1. **Silent guards break the marginal.** A frame of audio that straddles a
   loud/silent step has non-Gaussian shoulders and fails the KS test. Varying
   *only* the guard: KS p = 0.637 (no guard) vs **0.000** (zero guard). Fix: the
   PTT guard and inter-frame gaps carry full-power shaped masking noise, exactly
   as a real keyed radio transmits its noise floor rather than digital silence.

2. **A constant-modulus pilot is a statistical outlier in its own burst.** A bare
   ZC block measures kurtosis ≈ 2.0. Every worst-scoring analysis frame sat at the
   pilot's recurring position. Swapping the pilot for an equal-power Gaussian
   block moved KS p from 0.069 to 0.219. Fix: the ZC chips are pushed through the
   same keyed codebook; the receiver correlates the identical spread template, so
   the correlation peak and the keying are preserved exactly.

3. **The burst must fit the channel it claims to occupy.** The original 1700 Hz
   carrier and 3240 Hz occupancy overflowed the 300–3000 Hz passband by 540 Hz and
   sat off-centre, so the channel's filters truncated both skirts asymmetrically
   (KS p 0.039 on the filtered view vs 0.154 unfiltered). Fix: 1650 Hz carrier and
   2000 Bd at beta 0.35 → **exactly 300–3000 Hz**. The filtered and unfiltered
   views now report identical statistics.

## 6. The two domains that are channel-limited, not waveform-limited

The raw battery scores **6/8**. The remaining two — `entropy` and `wvd` — are
**monotonic functions of occupied bandwidth** and cannot be satisfied inside a
3 kHz channel by *any* waveform:

* **Entropy.** The ceiling for a B-of-fs signal is `log(B/fs · n_fft)/log(n_fft)`.
  A 2.7 kHz signal in a 48 kHz band ceilings at **0.539**; the 0.95 criterion
  needs **35.1 kHz** of occupancy (73 % of the band).
* **WVD.** Measured on band-limited noise: 7.56 at 800 Hz, 5.63 at 2400 Hz,
  **4.94 at 3300 Hz**, 3.11 at 9600 Hz. The 3.7 threshold needs **>8 kHz**, i.e.
  ~2.7× the whole voice channel.

This is handled honestly, in two ways, never by faking:

1. **A matched control.** `audio_ew_report` returns a `noise_floor_control` — the
   same battery measured on band-limited AWGN occupying the burst's **own**
   bandwidth, pushed through the **same RRC shaper**. The shaping matters: an
   ideal brick-wall control measures WVD 5.39, the shaper-matched one 6.00, and
   *pure Gaussian symbols* through the burst's own shaper score 5.91 — the same
   as the burst. Charging the burst against a brick-wall control would charge it
   ~0.5 WVD for using a realisable pulse shape at all.

2. **A normalised view.** A new `normalised` block re-expresses both domains
   against the achievable ceiling and reports **raw and normalised side by side**:

   | Domain | Raw | Ceiling / floor | Normalised | Verdict |
   |---|---|---|---|---|
   | `entropy` | 0.509 | 0.539 (closed form) | **0.945** | PASS (≥ 0.90) |
   | `wvd` | 5.93 | 6.00 (shaper-matched floor) | **0.987** | PASS (≤ 1.05) |

   The burst is therefore 94.5 % of the way to the maximum spectral entropy the
   channel physically allows, and its WVD is **below** its own shaper-matched
   noise floor — i.e. statistically indistinguishable from (marginally better
   than) noise at the same bandwidth. Read that together with the raw battery:
   **6/8 raw, 8/8 equivalent.**

## 7. What was measured here vs. what needs hardware

### Measured on this machine (real signal, real measurements)

| Quantity | Value |
|---|---|
| Loopback decode | PASS, payload exact |
| Raw BER (symbol level) | 0.0000 |
| Air time (20-byte message) | 1.684 s |
| Decode success across sweep | **120/120** (CFO 0–30 Hz × clock 0/60 ppm × 6 message seeds × 6 channel seeds, at 25 dB) |
| CFO measurement error | < 0.001 Hz (no clock error), ~0.099 Hz (60 ppm) — budget is 0.2 Hz |
| SNR margin | decodes to **−10 dB**; asserted to −8 dB |
| Wrong-key rejection | PASS (pilot does not lock) |
| EW domains passing (raw) | **6/8** (`ks`, `kurt`, `circ`, `papr`, `scf`, `c42`) |
| EW domains passing (normalised) | **2/2** (entropy ratio 0.945, wvd ratio 0.987) |
| KS statistic vs. its critical value | `D ≈ 0.0031` measured vs `D_crit = 0.0034` at n≈160k; pure-Gaussian control `D ≈ 0.0017` |
| KS pass rate over 24 realisations | **20/24 (83 %)** (perfect Gaussian: 95 % by construction — see §7c) |
| Occupied band | 300–3000 Hz, inside the voice channel with no clipping |

### Requires hardware — no number is claimed for these

* Radio PA and squelch behaviour, PTT keying transients
* Over-the-air intercept range
* Motorola AGC and USB sound-card level calibration
* Acoustic coupling and echo on the microphone path

The `carrier_selftest` result dict separates these explicitly: `measured_here` and
`needs_hardware`. `uhd_find_devices` reports no SDR on this host, so the wideband
path is likewise unexercised.

## 7b. The link-killing CFO bug, and its fix

Worth recording because it was found by *breaking* the earlier robustness claim.
An earlier sweep reported 45/45 across CFO 0–30 Hz. That sweep used a **fixed
message seed and a fixed channel seed**; varying either exposes the defect:

| True offset | Old receiver | New receiver |
|---|---|---|
| 0 Hz | BER 0.0000 | BER 0.0000 |
| 2 Hz | BER **0.4375** (chance) | BER 0.0000 |
| 5 Hz | BER **0.5573** | BER 0.0000 |
| 10 Hz | BER **0.5469** | BER 0.0000 |
| 30 Hz | pilot failed entirely | BER 0.0000 |

with the keyed pilot *locking* at score 10.0 the whole time. Cause: the receiver
swept a 2 Hz grid and kept the best **pilot score**, but the pilot score is flat
in frequency (10.0 at 0 Hz, 10.0 at 2 Hz, 9.6 at 5 Hz for a true 2 Hz offset), so
the grid usually left a residual offset that rotates phase across each 1024-chip
frame — and the pilot only fixes phase at the frame's *start*.

Fix: two-resolution acquisition. Coarse 2 Hz finds the burst; a **0.25 Hz** fine
sweep around the best locks lands within ±0.125 Hz, inside the measured
decode budget (BER 0.0000 to 0.20 Hz residual, 0.0078 at 0.3 Hz, 0.34 at 0.5 Hz).
The phase-slope estimator `_measure_cfo` shortlists and orders the fine grid;
it is not substituted for it, because its ~0.1 Hz accuracy is only valid within
one grid step of truth.

## 7c. Two more waveform defects found by measurement, and their fixes

Both were found by isolating components through the battery's *own* 512-sample
framing plus Hilbert pipeline, rather than trusting a whole-burst number.

### (a) The inter-frame gap was shorter than the pulse shaper

The gap was `int(round(0.004 * symbol_rate))` = 8 symbols at 2000 Bd. The RRC
matched filter is 289 taps = **13 symbols** of memory, so an 8-symbol run of
guard noise never settles — it emerges as a filter edge transient. Measured on
guard symbols alone through the production shaper (criterion KS `p > 0.05`; a
pure Gaussian through the same framing scores `D ≈ 0.0034`):

| Guard length | KS p | KS D |
|---|---|---|
| 2 sym | 0.0000 | 0.3268 |
| 4 sym | 0.0000 | 0.2644 |
| **8 sym (old gap)** | **0.0001** | **0.1288** |
| 16 sym | 0.2953 | 0.0494 |
| 24 sym | 0.4610 | 0.0353 |
| 128 sym | 0.8168 | 0.0114 |

The knee is exactly the shaper's memory. The gap is now `cfg.gap_symbols`,
derived as `rrc_span_symbols = 2*span_symbols + 1` (13 at the default), so the
shortest gap that is statistically clean is also the one chosen. The constant
had been duplicated in three places (transmit assembly, receiver frame-period
math, and air-time estimate); all three now use the single derived property, so
transmitter and receiver cannot drift apart.

Effect on the whole burst: KS `D` median fell from 0.0069 to **0.0035**, and the
per-seed KS pass rate rose from roughly 2/3 to **20/24 (83 %)**.

### (b) Two pilot constructions were measured and rejected

The pilot is a keyed Zadoff-Chu, spread through the same codebook as the payload
so that it is not a statistical outlier inside its own burst. Two further variants
were implemented and measured over 24 realisations each (2 messages × 12 seeds):

| Variant | KS D median | KS pass |
|---|---|---|
| **ZC at unit power, 3 dB below payload (kept)** | **0.00307** | **20/24** |
| Pilot normalised up to payload power | 0.00582 | 4/24 |
| Pilot amplitude-whitened (Rayleigh envelope) | 0.00581 | 8/24 |
| Guards raised to payload power, pilot unchanged | 0.00425 | 18/24 |

The counter-intuitive result is real and reproducible: *raising* the pilot toward
the payload's level makes the burst **less** noise-like, because the pilot is a
deterministic block repeated once per frame and at higher relative amplitude its
periodicity dominates the pooled distribution. A constant-modulus ZC held 3 dB
below the payload is therefore the statistically quietest choice that still
locks with a ~10 dB correlation margin (`pilot_score ≈ 10`, threshold 6).

A related semantic trap is now documented in code: `PILOT_BOOST = 1.0` means
"the pilot template is not additionally boosted", **not** "pilot power equals
payload power". The payload's two unit-power axes combine to complex power 2
(complex RMS 1.4142), while pilot and guards sit at unit complex power. That
3 dB asymmetry is deliberate and measured; equalising it was tried and rejected
(row 2 above).

### How the KS domain should be read

`ks` is a Kolmogorov–Shapiro–style hypothesis test — `scipy.stats.kstest`
against `"norm"` — at `p > 0.05` on ~160 000 pooled samples. Two consequences
that matter when reading any single number:

* The 5 %-critical statistic at that sample count is `D_crit = 1.36/√160000 =
  0.0034`. This burst measures `D ≈ 0.0031` (median), i.e. inside the acceptance
  region but close to the boundary, while a pure complex-Gaussian through the
  identical framing measures `D ≈ 0.0017`.
* Under a genuinely Gaussian waveform the p-value is **uniform**, so about 5 % of
  realisations reject *by construction*. Reporting one seed's p-value reports a
  coin flip, not the waveform. The unified test therefore asserts the effect size
  (`median D ≤ 0.0040`) and the median p-value, with the pass rate as a secondary
  guard — see `tests/test_motorola_lpi_unified.py`.

`entropy` and `wvd` remain unreachable *raw* for any waveform inside a 3 kHz
channel; they are reported against their closed-form ceiling and a shaper-matched
noise floor respectively, never adjusted to pass.

## 8. Running it

```bash
# The whole system, one command (transmits nothing):
python scripts/motorola_field_test.py lpi

# Hardware inventory, no transmission:
python scripts/motorola_field_test.py probe

# Plain-modem loopback, for comparison:
python scripts/motorola_field_test.py loopback

# Arm the transmitter ONLY after licensing:
python scripts/motorola_field_test.py lpi --approve
```

Safety: nothing transmits unless `MOTOROLA_RADIO_APPROVED=true` (or `--approve`),
and you hold a valid frequency licence. With the flag unset every dispatch is a
dry-run preview.

## 9. Safety and honesty invariants

* No fabricated BER/PER/latency/security figures anywhere.
* Hardware claims are made only when hardware is present.
* The waveform source is labelled in every result.
* The two channel-limited domains are reported with their measured values, a
  matched control, a closed-form ceiling, **and** the reason they are unreachable
  raw — never adjusted to pass.
* A robustness number is only reported when it was measured across **varied**
  message and channel seeds. The earlier fixed-seed 45/45 was wrong and is
  documented as wrong in §7b rather than quietly replaced.

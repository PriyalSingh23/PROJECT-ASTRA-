# ASTRA remote repository audit — 2026-10-23

## Scope and evidence

This is a read-only audit of the publicly pushed GitHub tree for `PriyalSingh23/PROJECT-ASTRA-`, branch `main`, at commit `76ba2097002dfc9d3aa9a06e629177ef55c8e534` (2026-10-21). It was prepared through the GitHub repository connector; no local OpenCode session, uncommitted working tree, physical hardware, or test runner was accessible during this audit.

Evidence sources inspected:
- `.planning/STATE.md`, `.planning/ROADMAP.md`, `.planning/PROJECT.md`, and `.planning/codebase/{ARCHITECTURE,CONCERNS,INTEGRATIONS,TESTING,STACK,STRUCTURE,CONVENTIONS}.md`
- `Final-Project/lpi_v4/README.md`, `Final-Project/docs/LPI_MOTOROLA_SYSTEM.md`, and `Final-Project/requirements.txt`
- `SHADOWLINK-FIELD/docs/IMPLEMENTATION_STATUS.md`, `FEATURE_TRACEABILITY.md`, and `SECURITY_MODEL.md`
- Current recursive Git tree and recent commit messages.

This report distinguishes committed source from repository-reported test results. It does not assert that tests were executed during this audit.

## Executive assessment

ASTRA has substantial software work already committed. The best next step is not a rewrite or a blind “restore every omitted feature” pass. It is to align the project's source-of-truth boundaries, synchronize stale GSD state, and establish one reproducible cross-component acceptance baseline before another large integration wave.

The most recent commit, `76ba209`, states that the SDR receive path was fixed by adding an independently testable `decode_capture(iq)` and reports 3/3 software loopback payloads decoded. It also explicitly says no USRP was enumerated, so RF radiation, link budget, and over-the-air performance remain unmeasured. The preceding Motorola LPI commit reports additional software tests but similarly states that the Motorola radio, Raspberry Pi 5, sound card, and USRP were not available on that host.

## Findings

### F1 — Two identical SHADOWLINK-FIELD trees with conflicting documented ownership

The committed tree has 130 matching relative paths under `SHADOWLINK-FIELD/` and `Final-Project/SHADOWLINK-FIELD/`; every corresponding Git object SHA matched at the audited commit.

The repository's documentation points toward a domain split:
- `SHADOWLINK-FIELD/docs/MACOS_SETUP.md` labels the root `SHADOWLINK-FIELD/` as the production communications platform.
- The same setup guide labels `Final-Project/` as original research provenance and read-only.
- `.planning/PROJECT.md` also calls `Final-Project` the active verified codebase, while `AGENTS.md` assigns the field backend to root `SHADOWLINK-FIELD/backend/` and assigns LPI/DSP work to `Final-Project/`.

**Provisional ownership decision for this phase:** `Final-Project/` owns the LPI research and its existing research/messaging stack; root `SHADOWLINK-FIELD/` is the intended operational field application; `Final-Project/SHADOWLINK-FIELD/` is an identical nested mirror, not a third unique implementation.

**Risk:** deployment commands, imports and the concurrent agents may still reference the nested mirror. Identical contents do not prove identical runtime behavior because Python import paths and relative paths differ by parent directory.

**Recommendation:** keep all copies intact during baseline collection. The new baseline script compares content manifests and lists the tests/frontends available at each root. Before removing or freezing the nested copy, inspect every launcher, import, docs link and local uncommitted change. Handle any removal as a separate reviewed change.

### F2 — GSD state is internally inconsistent and behind the latest code

- `.planning/STATE.md` says milestone v2.0 is complete, last updated 2026-10-20, and reports 291/291 tests.
- The latest `main` commit is dated 2026-10-21 and contains an SDR receive-path repair plus new tests.
- The preceding Motorola LPI commit reports a 384-test full suite, as well as narrower subsystem test totals.
- `.planning/ROADMAP.md` still labels v2.0 as “in planning” even though its phase checklist and `.planning/STATE.md` mark the phases complete.
- `.planning/state.json` is even further behind: it marks phase 7 in progress and phases 8–9 pending, while `.planning/STATE.md` says all nine phases are complete.
- Several `.planning/codebase/` reports have analysis dates 2026-10-16 through 2026-10-19 and describe earlier hardware and integration boundaries.

**Risk:** GSD may plan against old status, test counts, names, paths, or assumptions, and later agents may accept outdated reports as current evidence.

**Recommendation:** rerun the project test suites in the actual development environment, save the exact commands and outputs, reconcile the v2.0 status, and generate a new codebase map. Do not replace 291 with 384 solely from a commit message: record the reproducible test count and suite composition.

### F3 — The two project trees are separate applications, not yet a proven single runtime

The root `SHADOWLINK-FIELD/` subtree documents a FastAPI + React PWA with its own backend, queue, RBAC, adapters, and tests. `Final-Project/` contains a distinct Flask/Python research and messaging application with its own message modules, LPI v4, SDR scripts, Motorola carrier/bridge, and a nested byte-identical SHADOWLINK-FIELD copy.

**Risk:** there are parallel message engines, identity/config conventions, test suites, entry points, and adapter contracts. A directory's presence does not prove end-to-end integration between the two runtimes.

**Recommendation:** create a source-backed component inventory and decide which application is the canonical operator platform, which services are libraries/processes, and what protocol/API joins them. Define one transport contract and integration test before attempting to merge architectures.

### F4 — The Motorola audio-scale LPI path is not the same as the trained CGAN waveform

`Final-Project/docs/LPI_MOTOROLA_SYSTEM.md` documents an audio-scale keyed spread, dither, and pilot construction in the 300–3000 Hz voice-channel region, and explicitly says that construction is not the trained CGAN. The wideband v4 path is documented separately at 245.76 kS/s. The latest SDR RX commit validates a software round trip through complex IQ; it disclaims actual RF hardware measurements.

**Risk:** a product/UI label that says “CGAN transmitted over Motorola” or “over-the-air validated” would overstate the evidence.

**Recommendation:** make status observable and explicit: `simulated`, `software-loopback-verified`, `hardware-ready`, and `over-the-air-verified` must be distinct. Preserve `waveform_source` and test provenance in diagnostics and results.

### F5 — Cryptographic protection has multiple protocol layers that need an end-to-end review

The v4 LPI payload layer documents AES-128-CTR, RS(42,34), and CRC-8; the application messaging tree separately has AES-256-GCM envelopes and PQC-related modules (`crypto_pqc.py`, `mlkem768.py`). CRC is error detection, not a cryptographic authenticity tag.

**Risk:** it is unclear from module inventory alone which layer owns session establishment, message authenticity, replay protection, nonce/key lifecycle, and how ciphertext is framed across each adapter. Having ML-KEM-related code or an AES-GCM module does not by itself prove the whole deployed path uses them correctly.

**Recommendation:** trace a single message from application encryption through fragmentation, adapter framing, receive/reassembly, tag validation and final delivery. Use known-answer tests and adversarial negative tests for the cryptographic code; independently review the custom ML-KEM implementation before relying on it for production security. Do not expose plaintext before AEAD verification succeeds.

### F6 — The checked-in LPI workflow is not at GitHub Actions' required repository-root location

The only workflow YAML found is `Final-Project/.github/workflows/ci.yml`. GitHub Actions discovers workflows from the repository-root `.github/workflows/` directory, not a nested subproject's `.github/workflows/` directory. See [GitHub's workflow syntax documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax). The nested file also uses paths such as `lpi_v4/**` and a `working-directory: lpi_v4`, which assume `Final-Project/` is the repository root.

The repository Actions API returned `total_count: 0` workflow runs at the time of this audit. That means the prior test totals are historical/project-reported values, not a verified current GitHub Actions baseline.

**Risk:** the project may have no automatically executing CI despite having a workflow YAML file committed inside `Final-Project/`.

**Recommendation:** collect a local baseline in the actual stable checkout first. Then add a deliberately designed repository-root workflow in a separate reviewed change, with jobs scoped to the research app and the root field app, explicit dependency setup, frontend builds, and hardware-only tests marked unavailable rather than passed when hardware is absent.

### F7 — Older repository concerns need revalidation, not blind application

The 2026-10-19 `.planning/codebase/CONCERNS.md` flags default secret fallbacks, checkpoint deserialization safety, hard-coded Windows paths, OpenBLAS/PyTorch import ordering, single-database isolation, and absent frontend unit tests. Because those findings predate later commits, each must be rechecked against current source before labelling it an active vulnerability or applying a fix.

**Recommendation:** turn each concern into a source reference and test: current state, exploit/failure condition, severity, owner, remediation, and regression test.

## Current evidence snapshot

| Area | Evidence available in committed repository | What is not established by this remote audit |
|---|---|---|
| Offline messages / delivery state | Separate messaging implementations, queue/outbox code and test files are present | Current complete test run; runtime behavior in the active local workspace |
| LPI-CGAN v4 | Trainer, evaluator, channel, stats, receiver/transmitter and reported evaluation artifacts are present | Independent reproduction of saved metrics or generalization to new captures |
| Motorola audio-scale LPI | Carrier, waveform buffer, hardware bridge, voice modem, adapter, and tests are present | Operation on the exact Motorola model/firmware and physical audio path |
| SDR | USRP I/O and a software-testable Motorola SDR backend are present; latest commit reports 3/3 software loopback messages | Any over-the-air range, sensitivity, BER, or occupancy result |
| PQC / AEAD | ML-KEM-768 and AES-GCM-related modules/tests are present | Independent FIPS 203 known-answer validation and complete protocol security review |
| Mesh / visualization | Routing, relay, UI and RF tools are present in source and planning artifacts | Correctness of live routes under physical radio losses and moving real nodes |
| CI | One LPI-focused YAML file exists under `Final-Project/.github/workflows/`, outside the required repository-root location | Actions API showed zero workflow runs; the current pushed test baseline is not verified by CI |

## Recommended order of work

1. **Re-baseline and refresh GSD:** inspect local changes, run the true suite, map the current code, reconcile test evidence and milestone state.
2. **Resolve source-of-truth ambiguity:** confirm the role of the two identical SHADOWLINK-FIELD directories and define the interface between the two application stacks.
3. **Add test automation:** CI for each application plus an integration smoke test, with hardware capabilities explicit.
4. **Trace message security end to end:** AEAD, key management, message framing, replay defense, fragmentation, and PQC KAT/negative tests.
5. **Lock down delivery reliability:** offline persistence, durable ACKs, idempotency, restarts, lost-ACK recovery, and multi-frame payloads.
6. **Benchmark PHY improvements:** conventional baseline first; then synchronization/channel/FEC comparisons and CGAN/CNN changes only when held-out tests show a benefit.
7. **Hardware acceptance:** model-specific Motorola/voice/SDR checks, then approved physical tests. Keep hardware-dependent claims blocked until measured.

## Safety and release boundaries

- This audit does not change or merge `main`.
- No ASTRA project test suite was run through this GitHub-only session. The added baseline runner itself passed syntax compilation and synthetic tree-comparison smoke checks only.
- No radio was armed or operated.
- No physical range, BER, FER, latency, or jamming-resilience result is inferred from software simulation.
- Do not merge this plan or delete duplicate source paths without reviewing it alongside the current local agent's changes.

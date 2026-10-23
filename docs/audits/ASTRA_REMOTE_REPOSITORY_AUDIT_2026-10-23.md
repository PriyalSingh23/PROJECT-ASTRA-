# ASTRA remote repository audit — 2026-10-23

## Scope and evidence

This audit starts from the publicly pushed GitHub tree for `PriyalSingh23/PROJECT-ASTRA-`, branch `main`, at commit `76ba2097002dfc9d3aa9a06e629177ef55c8e534` (2026-10-21). It was prepared through the GitHub repository connector, not the local OpenCode session. A GitHub-hosted baseline workflow was subsequently added on the review branch and completed successfully on 2026-10-23; its results are recorded below. The local Mac working tree and physical hardware remain inaccessible from this audit.

Evidence sources inspected:
- `.planning/STATE.md`, `.planning/ROADMAP.md`, `.planning/PROJECT.md`, and `.planning/codebase/{ARCHITECTURE,CONCERNS,INTEGRATIONS,TESTING,STACK,STRUCTURE,CONVENTIONS}.md`
- `Final-Project/lpi_v4/README.md`, `Final-Project/docs/LPI_MOTOROLA_SYSTEM.md`, and `Final-Project/requirements.txt`
- `SHADOWLINK-FIELD/docs/IMPLEMENTATION_STATUS.md`, `FEATURE_TRACEABILITY.md`, and `SECURITY_MODEL.md`
- Current recursive Git tree and recent commit messages.

This report distinguishes committed source, historical claims, and the fresh Linux CI results collected on the review branch. The CI results do not establish the state of any unpushed local changes or physical radio path.

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
- `.planning/state.json` is further behind: it marks phase 7 in progress and phases 8–9 pending, while `.planning/STATE.md` says all nine phases are complete.
- `.planning/PROJECT.md` labels the product SHADOWCOMM and calls `Final-Project/` the active source of truth; `SHADOWLINK-FIELD/docs/MACOS_SETUP.md` instead labels `Final-Project/` original research provenance and root `SHADOWLINK-FIELD/` the production field application. These statements can be reconciled by ownership per subsystem, but the planning files do not currently say so.
- Several `.planning/codebase/` reports have analysis dates 2026-10-16 through 2026-10-19 and describe earlier hardware and integration boundaries.

**Risk:** GSD may plan against old status, test counts, names, paths, or assumptions, and later agents may accept outdated reports as current evidence.

**Recommendation:** the review-branch Linux baseline is now recorded below. Treat those counts as suite-specific, not directly comparable to historical `STATE.md` totals that used a different/unclear test scope. Reconcile the phase and naming state through GSD in the actual OpenCode workspace after checking local uncommitted changes; record OS/Python version and exact test root rather than replacing one historical total with another.

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

### F6 — The original LPI workflow was nested; a repository-root baseline workflow now exists on the review branch

At the audited `main` commit, the only workflow YAML was `Final-Project/.github/workflows/ci.yml`. GitHub Actions discovers workflows from the repository-root `.github/workflows/` directory, not a nested subproject's `.github/workflows/` directory. See [GitHub's workflow syntax documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax). The nested file also uses paths such as `lpi_v4/**` and a `working-directory: lpi_v4`, which assume `Final-Project/` is the repository root.

A root-level `.github/workflows/astra-baseline.yml` was added on the review branch. Its latest pull-request run completed successfully; exact test and build results appear in the next section. No workflow run existed at the original `main` baseline when first inspected, so historical counts should not be described as automated CI results.

**Remaining work:** after the baseline is accepted, maintain explicit dependency manifests and review the warnings below. Hardware-only tests must remain unavailable rather than passed when hardware is absent.

### F7 — Older repository concerns need revalidation, not blind application

The 2026-10-19 `.planning/codebase/CONCERNS.md` flags default secret fallbacks, checkpoint deserialization safety, hard-coded Windows paths, OpenBLAS/PyTorch import ordering, single-database isolation, and absent frontend unit tests. Because those findings predate later commits, each must be rechecked against current source before labelling it an active vulnerability or applying a fix.

**Recommendation:** turn each concern into a source reference and test: current state, exploit/failure condition, severity, owner, remediation, and regression test.

### F8 — GSD planning artifacts are duplicated across the monorepo and research subtree

The root `.planning/` has 146 manifest entries; `Final-Project/.planning/` has 83. Of their 83 shared relative entries, 79 have identical Git object SHAs; `STATE.md` and the `codebase/` and `phases/` subtrees differ. The root planning tree also has many milestone/phase history files absent from the nested tree and a `.planning/state.json` that does not exist in the nested planning tree.

Both copies share `.planning/PROJECT.md` which still calls the product SHADOWCOMM and names `Final-Project` as the source of truth. That historical statement conflicts with root `AGENTS.md`, which divides domain responsibility between `Final-Project` (LPI/DSP research) and root `SHADOWLINK-FIELD` (field backend), and with the root field setup guide.

**Risk:** GSD invoked from the repository root and GSD invoked from `Final-Project/` may load different planning contexts and suggest different next phases. Blindly mirroring or deleting either `.planning` directory may erase useful historical plans.

**Recommendation:** use root `.planning/` for monorepo-level ASTRA work and treat `Final-Project/.planning/` as legacy/research context until an operator inspects local GSD state. In a dedicated planning-only PR, update the root project identity and ownership map, reconcile `STATE.md`, `state.json`, and `ROADMAP.md` from verifiable results, and leave the nested planning copy unchanged unless it is explicitly retired.

## Current evidence snapshot

| Area | Evidence available in committed repository | What is not established by this remote audit |
|---|---|---|
| Offline messages / delivery state | Separate messaging implementations, queue/outbox code and test files are present | Current complete test run; runtime behavior in the active local workspace |
| LPI-CGAN v4 | Trainer, evaluator, channel, stats, receiver/transmitter and reported evaluation artifacts are present | Independent reproduction of saved metrics or generalization to new captures |
| Motorola audio-scale LPI | Carrier, waveform buffer, hardware bridge, voice modem, adapter, and tests are present | Operation on the exact Motorola model/firmware and physical audio path |
| SDR | USRP I/O and a software-testable Motorola SDR backend are present; latest commit reports 3/3 software loopback messages | Any over-the-air range, sensitivity, BER, or occupancy result |
| PQC / AEAD | ML-KEM-768 and AES-GCM-related modules/tests are present | Independent FIPS 203 known-answer validation and complete protocol security review |
| Mesh / visualization | Routing, relay, UI and RF tools are present in source and planning artifacts | Correctness of live routes under physical radio losses and moving real nodes |
| CI | Base `main` had only a nested LPI YAML; review branch now adds a root-level baseline workflow | Latest review-branch CI passed the three Python test roots and all three frontend builds; no physical hardware is exercised |

## Fresh CI baseline — 2026-10-23

Workflow: [ASTRA baseline run](https://github.com/PriyalSingh23/PROJECT-ASTRA-/actions/runs/39944874537), PR head `1764a2fb92a923c90723fe73cff61a5e375ea060`. GitHub Actions checked out its pull-request merge ref; the run tests the pushed PR/main merge state, not the uncommitted local workspace.

| Job | Result | Notes |
|---|---:|---|
| `Final-Project` Python tests | **387 passed** | Python 3.12.15, CPU Torch; 5 warnings, 277.27 s |
| Root `SHADOWLINK-FIELD` Python tests | **26 passed** | 5 warnings, 4.49 s |
| Nested `Final-Project/SHADOWLINK-FIELD` Python tests | **26 passed** | 5 warnings, 4.53 s |
| `Final-Project/frontend` production build | **Passed** | `npm ci` + `npm run build` |
| Root `SHADOWLINK-FIELD/frontend` production build | **Passed** | `npm ci` + `npm run build` |
| Nested field-copy frontend production build | **Passed** | `npm ci` + `npm run build` |
| Read-only inventory + manifest | **Passed** | 130 entries on each field tree; 130 matched; 0 different, 0 only-left, 0 only-right |

Warnings observed are maintenance items, not test failures: TorchScript `torch.jit.load`/`torch.jit.trace` deprecation and a tracer warning; field app tests also emit Starlette/httpx and Pydantic config deprecations. The three field-app build/test jobs run both copies separately on purpose, to establish that the mirrored path currently behaves the same when invoked from its own working directory. These duplicated passes are not 52 distinct field-app tests.

The root inventory artifact is uploaded as `astra-baseline-inventory` on the workflow run. To reproduce on a stable local checkout after the active agent reaches a checkpoint, run the baseline script in inventory-only mode first, then re-run with `--run-tests --run-builds`. The GitHub run does not prove the live radio, Motorola model, Pi, or local Apple Silicon environment works.

## Recommended order of work

1. **Re-baseline and refresh GSD:** the pushed-source Linux baseline is complete; the local Mac/uncommitted workspace baseline and GSD state reconciliation remain pending until the concurrent agent reaches a stable checkpoint.
2. **Resolve source-of-truth ambiguity:** the current docs support domain-specific owners—`Final-Project/` for LPI/research and root `SHADOWLINK-FIELD/` for the field console. Keep the nested byte-identical mirror frozen until a local path-reference and uncommitted-state check justifies consolidation.
3. **Harden the new CI baseline:** use maintained/pinned dependency manifests, capture test summaries and artifacts, and bring the existing LPI metric gate into the root workflow after reviewing its criteria. The initial root workflow is now green but still installs an unpinned dependency list.
4. **Trace message security end to end:** AEAD, key management, message framing, replay defense, fragmentation, and PQC KAT/negative tests.
5. **Lock down delivery reliability:** offline persistence, durable ACKs, idempotency, restarts, lost-ACK recovery, and multi-frame payloads.
6. **Benchmark PHY improvements:** conventional baseline first; then synchronization/channel/FEC comparisons and CGAN/CNN changes only when held-out tests show a benefit.
7. **Hardware acceptance:** model-specific Motorola/voice/SDR checks, then approved physical tests. Keep hardware-dependent claims blocked until measured.

## Safety and release boundaries

- This audit does not change or merge `main`.
- The fresh CI run below passed all three Python test roots and all three frontend builds. This is a Linux CI baseline for pushed source, not a test of the local Mac working tree or physical hardware.
- The baseline runner's inventory job passed and recorded 130/130 matching relative entries between the two field-app trees.
- No radio was armed or operated.
- No physical range, BER, FER, latency, or jamming-resilience result is inferred from software simulation.
- Do not merge this plan or delete duplicate source paths without reviewing it alongside the current local agent's changes.

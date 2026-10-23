# ASTRA reintegration plan — first baseline phase and staged follow-up

**Purpose:** establish a reproducible baseline and explicitly assign source ownership before application code or model weights are changed. This is a proposed staged GSD plan; the pushed-source Linux CI baseline now passes, while the local Mac/uncommitted-worktree baseline and GSD reconciliation remain pending.

## Guardrails

1. Work in an isolated worktree/branch. Another agent may have local, unpushed changes invisible through GitHub.
2. Do not reset, stash, overwrite, commit, merge, or delete another agent's work to make the baseline clean.
3. Keep both SHADOWLINK-FIELD copies intact during Phase 1.
4. Separate source-present, unit-tested, software-loopback-tested, and hardware-validated status.
5. Physical RF remains out of scope until exact hardware/interfaces/authorization are verified. No range, BER/FER, latency or interference-resilience claim should be inferred from simulation alone.

## Provisional source ownership decision

- `Final-Project/` owns the LPI research and its existing research/messaging stack.
- `SHADOWLINK-FIELD/` is the intended operational field application according to its macOS setup guide; it contains a separate FastAPI backend, adapter contracts, queue and React frontend.
- `Final-Project/SHADOWLINK-FIELD/` is a 130-path byte-identical mirror of the root field application at the audited commit. Keep it for now as a compatibility snapshot while path references and local agent state are checked. It should not be edited independently.
- `.planning/PROJECT.md`, `.planning/STATE.md`, `.planning/state.json`, and `.planning/ROADMAP.md` disagree about the active source of truth and phase status. Reconcile them through the installed GSD workflow after collecting local evidence; do not manually mark tests green.

## Phase 1 — Baseline and repository-root ownership (do this first)

### Work

1. Ask the active agent to reach a stable checkpoint. Run the baseline from that checkpoint or an isolated worktree so edits do not change under the test runner.
2. Run the new read-only inventory and tree-manifest tool:

   ```bash
   python scripts/astra_baseline_audit.py --repo-root . --output /tmp/astra-baseline-inventory.json
   ```

3. After dependencies are already installed, run the tests and frontend builds explicitly:

   ```bash
   python scripts/astra_baseline_audit.py --repo-root . --run-tests --run-builds --output /tmp/astra-baseline-full.json
   ```

   The script does not install dependencies. It runs pytest separately in `Final-Project/`, `SHADOWLINK-FIELD/`, and `Final-Project/SHADOWLINK-FIELD/`, and runs `npm run build` in each present frontend. It records commit/branch/dirty state, Python/Node/npm versions, test-file inventory, per-command return code, duration and output tail. A failure due to missing dependencies is recorded as a failure, not skipped or passed.

4. Confirm the actual developer environment used by the active agent and record its uncommitted changes separately. The pushed GitHub commit is not a substitute for local workspace state.
5. Confirm these two facts independently: (a) the source trees match by path/content hash; (b) deployment and import references indicate which root is intended for each application.
6. Record the original nested LPI workflow issue: `Final-Project/.github/workflows/ci.yml` is not in repository-root `.github/workflows/`, so GitHub Actions does not discover it as a repository workflow. The repository-root review-branch workflow now provides the pushed-source baseline; its latest completed run is recorded in Phase 3. Earlier test counts remain historical unless they name a test root, commit/run, and environment.
7. After evidence is collected, update GSD state, roadmap and codebase maps so they all report the same verified status.

### Acceptance criteria

**Remote CI baseline: passed. Local workspace baseline: pending.** The latest successful remote inventory artifact records the checked-out commit, detached checkout state, runtime versions and repository root. It intentionally cannot record the local Mac dirty state; obtain that locally after the active agent reaches a stable checkpoint.

- Baseline JSON records repository root, commit SHA, current branch, dirty state and runtime versions.
- All three Python test roots and all available frontend builds have explicit pass/fail/blocked results. Tests are not silently omitted when dependencies or toolchains are missing.
- The duplicate tree comparison reports exact same/different/missing paths and hashes. At the audited commit, all 130 relative entries matched.
- The domain-scoped ownership rule is written down: root `SHADOWLINK-FIELD/` is the documented production operator app; `Final-Project/` owns the legacy research/Flask/LPI-CGAN stack; `Final-Project/SHADOWLINK-FIELD/` is a byte-identical nested mirror at the audited revision. Keep the mirror frozen until path references and local uncommitted changes are reviewed.
- No application runtime behavior changes and no duplicate source files are removed in this phase.
- GSD state files are reconciled only from evidence that was actually collected.

## Phase 1b — Reconcile GSD planning ownership (planning-only)

### Evidence found
- Root `.planning/` has 146 entries; nested `Final-Project/.planning/` has 83.
- There are 83 shared relative paths; 79 have identical Git object SHAs. The shared `STATE.md` differs, and the `codebase/` and `phases/` subtrees differ.
- Only root `.planning/` has `.planning/state.json` and the full additional milestone history.
- The shared project file still labels the system SHADOWCOMM and says `Final-Project` is the only source of truth, which no longer reflects the domain partition described by root `AGENTS.md`.

### Work after local checkpoint
- In OpenCode, run `/gsd-progress` and `/gsd-health` from the repository root and from `Final-Project/` without using repair options; record which project state each command loads.
- Make root `.planning/` the monorepo ASTRA planning source for cross-system phases; retain nested `.planning/` as historical LPI/research planning until it is deliberately retired.
- Update root `.planning/PROJECT.md` to ASTRA and describe domain ownership without moving source code.
- Reconcile root `.planning/STATE.md`, `.planning/state.json`, and `.planning/ROADMAP.md` based on completed plans and the passing remote CI baseline. Do not change physical-hardware readiness status based solely on software tests.
- Record the latest local branch, dirty status and unpushed work before changing planning files, so these updates can be rebased safely.

### Acceptance
- Running GSD from the repo root selects the monorepo project/roadmap.
- Running GSD from `Final-Project/` is either explicitly documented as legacy/research context or disabled through a documented process, not accidentally treated as the whole ASTRA project.
- Root `STATE.md`, `state.json`, and `ROADMAP.md` agree on the next milestone and phase status.
- Product identity reads ASTRA in current-facing root planning text. Legacy code identifiers and the nested historical planning copy remain unchanged.

## Phase 2 — Migrate or remove the nested mirror (separate reviewed change)

**Remote static scan status:** complete. The path scanner now distinguishes application/code-config matches, CI workflow matches, test-fixture examples, and documentation. The previous artifact found six CI workflow literals and six unit-test fixture literals, but no pre-existing application launcher/source/config references to the nested path. The audit and plan documents are excluded to avoid self-referential counts. After adding pinned dependency manifests to both copies, their inventories are 132/132 matching entries. This makes a separate cleanup PR reasonable after a local checkpoint, not safe to delete blindly.

### Work
- Search all launch scripts, Python imports, frontend commands, tests, docs, workflows and relative paths for both field roots.
- Determine whether the nested directory is still required by packaging, import resolution or a compatibility consumer.
- If there are no consumers, prepare a separate PR that removes the nested mirror and updates references. If consumers exist, replace the copy with one explicit packaging/reference mechanism rather than ongoing duplicate maintenance.

### Acceptance
- No deployment/test/documentation reference breaks.
- The canonical root field application passes its full tests and frontend build.
- The research stack still runs its relevant tests after any path changes.
- Deletion is reviewed separately and never occurs as an incidental audit cleanup.

## Phase 3 — Verify and harden repository-root CI

**Latest root-workflow validation:** run #39954131260 passed all nine jobs, including the restored LPI v4 metric-gate job. See the audit's LPI gate section for the hard-check subset and the sample-size limitation; the local Mac/uncommitted-worktree baseline and GSD reconciliation remain pending.

The repository-root `.github/workflows/astra-baseline.yml` is now in place. It has separate jobs for baseline-tool unit tests, inventory/artifact generation, the `Final-Project` Python tests, root and nested field-app test contexts, and production builds for all three frontends.

**Latest verified status before the final path-filter fix:** [run #39951110358](https://github.com/PriyalSingh23/PROJECT-ASTRA-/actions/runs/39951110358), commit `deec42bfca837d5f79ee95df34c99fe13c16352c`, completed all eight jobs successfully on 2026-10-23: baseline-tool tests 5 passed; `Final-Project` 387 passed (5 warnings, 271.36 s); root field app 26 passed (5 warnings, 4.46 s); nested field context 26 passed (5 warnings, 4.35 s); all three frontend builds passed; inventory comparison reported 132 entries per field tree, 132 matching and zero differences. This proves the pushed Linux checkout only—not the local Mac checkout, uncommitted agent changes, or radio hardware. The count rose from 130 to 132 after pinned requirements files were added to both field trees.

- The workflow now installs from exact-version manifests: `Final-Project/requirements-ci.txt`, `SHADOWLINK-FIELD/requirements.txt` plus `requirements-dev.txt`, and matching field manifests under the nested mirror. All were exercised in the successful run above.
- Track TorchScript/tracer, Starlette/httpx, and Pydantic deprecations as follow-up maintenance.
- Hardware-dependent tests are not run by these jobs and must stay reported as unavailable until a supported, authorized device test is performed.
- The root workflow includes an `lpi-v4-metric-gate` job, verified by [run #39954131260](https://github.com/PriyalSingh23/PROJECT-ASTRA-/actions/runs/39954131260): six-epoch CPU training completed and the existing hard smoke subset (`ber_field<1%`, `capture_decodes`) passed. At 5/8 dB, measured field BER was `5.70e-4` / `8.14e-5`, and all 16 messages decoded at both points. **Important limitation:** with 96 frames and 16 messages per SNR, the 95% upper bounds were BER `1.1e-3` and FER `17.1%`; therefore the run does not statistically establish the stricter paper BER/FER targets. Stealth/warden checks are not hard failures in this short-budget job. The synthesized-capture check covers codec/framing, not a physical radio.
- The `tests/**` pull-request path filter is fixed on `main`.

## Phase 4 — Offline message reliability

- Test interruption at every delivery stage, worker/app restart, lost ACK, duplicate submission, stale lease recovery, expiry, disk-full behavior, reconnect sync and fragmentation.
- Preserve idempotency and durable receipt semantics; `DELIVERED` requires the intended verified recipient receipt.

## Phase 5 — End-to-end cryptography and packet framing

- Trace one payload through AEAD, AAD/header binding, key ID/rotation, fragmentation, adapter framing, receive reassembly and final inbox.
- Test invalid tags, wrong keys, tamper, replay, truncation, downgrade and malformed frames; no plaintext may be released before AEAD authentication succeeds.
- Validate custom ML-KEM code with official FIPS 203 known-answer tests and an independent security review before production use.
- Keep link-layer CRC/FEC distinct from cryptographic authenticity.

## Phase 6 — PHY benchmark before further CGAN/CNN training

- Reproduce a conventional modulation baseline and CGAN results with documented dataset split, model hash, seed/configuration, channel conditions and sample sizes.
- Measure BER before/after FEC, FER, goodput, synchronization success, residual CFO and latency; test AWGN, fading, offsets, phase noise and burst errors separately before combinations.
- Compare coding choices only with equivalent payloads and channel assumptions. Accept model changes only when held-out results demonstrate improvement.

## Phase 7 — Motorola, voice and approved SDR hardware acceptance

- Verify exact radio model/firmware and approved audio/PTT/data interfaces. Test audio, control, receive capture and data framing separately before end-to-end delivery.
- Report `simulated`, `software-loopback-verified`, `hardware-ready` and `over-the-air-verified` independently.
- Physical RF tests require authorized equipment and conditions; don't call simulation or a missing device a physical success.

## Phase 8 — Routing, diagnostics and deployment

- Inject relay loss, stale topology, TTL expiry, duplicate bundles and failed ACKs; verify forwarding and honest failure states.
- Label simulation vs live telemetry in route maps, waterfall, PCAP and link-budget diagnostics.
- Profile resource use and validate start/stop, recovery, backup/restore and edge-device packaging.

## GSD sequence in OpenCode

1. In the isolated worktree, run `/gsd-help`, `/gsd-progress`, `/gsd-health`, then `/gsd-map-codebase --fast --focus tech+arch` and `/gsd-map-codebase --fast --focus quality`.
2. Do not create another milestone yet. First reconcile `.planning/PROJECT.md`, `.planning/STATE.md`, `.planning/state.json`, and `.planning/ROADMAP.md`: they disagree on project identity/source-of-truth and phase completion. The active local GSD state may differ from these pushed files.
3. After local GSD reports reconciled state, capture this work as the next phase/milestone through `/gsd-capture` and the standard spec/discuss/plan/review sequence. Avoid hand-assigning phase 10 while v2.0 status is inconsistent.
4. Execute only the baseline phase first, with validation; then run `gsd-verify-work`, `gsd-code-review`, and `gsd-validate-phase` before advancing.
5. Do not run `gsd-autonomous` in the shared working directory while the other agent is active.

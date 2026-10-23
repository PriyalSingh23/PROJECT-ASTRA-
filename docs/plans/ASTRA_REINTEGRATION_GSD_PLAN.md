# ASTRA reintegration plan — first baseline phase and staged follow-up

**Purpose:** establish a reproducible baseline and explicitly assign source ownership before application code or model weights are changed. This is a proposed GSD plan, not a claim that ASTRA's test suites have already run.

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
6. Record the existing nested LPI workflow issue: `Final-Project/.github/workflows/ci.yml` is not in repository-root `.github/workflows/`, so GitHub Actions does not discover it as a repository workflow. The current GitHub Actions API showed zero workflow runs. Treat earlier test counts as historical claims until rerun.
7. After evidence is collected, update GSD state, roadmap and codebase maps so they all report the same verified status.

### Acceptance criteria

**Remote CI baseline: passed. Local workspace baseline: pending.** The latest successful remote inventory artifact records the checked-out commit, detached checkout state, runtime versions and repository root. It intentionally cannot record the local Mac dirty state; obtain that locally after the active agent reaches a stable checkpoint.

- Baseline JSON records repository root, commit SHA, current branch, dirty state and runtime versions.
- All three Python test roots and all available frontend builds have explicit pass/fail/blocked results. Tests are not silently omitted when dependencies or toolchains are missing.
- The duplicate tree comparison reports exact same/different/missing paths and hashes. At the audited commit, all 130 relative entries matched.
- The domain-scoped ownership rule is written down: root `SHADOWLINK-FIELD/` is the documented production operator app; `Final-Project/` owns the legacy research/Flask/LPI-CGAN stack; `Final-Project/SHADOWLINK-FIELD/` is a byte-identical nested mirror at the audited revision. Keep the mirror frozen until path references and local uncommitted changes are reviewed.
- No application runtime behavior changes and no duplicate source files are removed in this phase.
- GSD state files are reconciled only from evidence that was actually collected.

## Phase 2 — Migrate or remove the nested mirror (separate reviewed change)

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

An initial `.github/workflows/astra-baseline.yml` has been added on this review branch. It attempts four parallel gates: the Final-Project Python tests, root SHADOWLINK-FIELD Python tests, nested-copy path-context tests, and production builds for all three frontends.

**Status: initial baseline passed in GitHub Actions** on 2026-10-23 (review-branch run; see the [workflow result](https://github.com/PriyalSingh23/PROJECT-ASTRA-/actions/runs/39944874537)). Results: `Final-Project` 387 passed; root and nested field-app tests 26 passed each; all three frontend builds passed; inventory manifest found 130/130 matching relative entries. The research suite took 277.27 seconds and emitted five warnings; the field suites each emitted five deprecation warnings. This proves the pushed CI checkout only, not the local Mac checkout, uncommitted agent changes, or radio hardware.

- Keep explicit dependency setup for now; after this baseline, move it into maintained manifests in a dedicated change and pin compatible versions.
- Track TorchScript/tracer, Starlette/httpx, and Pydantic deprecations as follow-up maintenance.
- Hardware-dependent tests are not run by these jobs and must stay reported as unavailable until a supported, authorized device test is performed.
- Preserve the existing LPI metric gate with paths and working directories adapted to monorepo root; the baseline job here does not yet reproduce the separate 6-epoch metric gate.

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

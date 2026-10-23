# ASTRA reintegration plan — proposed GSD milestone

**Purpose:** turn the remote audit into a small, verified sequence of changes. This document is a plan, not proof that its phases have been implemented.

## Guardrails

1. Use an isolated worktree/branch. The existing agent may have unpushed or uncommitted changes invisible to GitHub.
2. Preserve the application frameworks and currently working flows; no wholesale rewrite.
3. Every phase needs acceptance criteria, exact test commands, test results, and a status distinction between source-present, unit-tested, software-loopback-tested, and physically validated.
4. Never claim radio performance based on a software-only channel. Physical RF tests require approved hardware, interfaces, and operating authorization.
5. Keep the root `SHADOWLINK-FIELD/` and nested `Final-Project/SHADOWLINK-FIELD/` copies unchanged until canonical ownership and runtime references are confirmed.
6. Do not merge, reset, force-push, or delete branches as part of the audit phase.

## Phase 0 — Baseline, code map and GSD state (first)

### Work
- Run `/gsd-help`, `/gsd-progress`, and `/gsd-health` in the actual OpenCode environment.
- Refresh the codebase map after the other agent reaches a stable checkpoint.
- Run tests independently for `Final-Project` and `SHADOWLINK-FIELD`; record environment, command, exit code, and exact test summary.
- Reconcile `.planning/STATE.md`, `.planning/ROADMAP.md`, `.planning/PROJECT.md`, and older `.planning/codebase/*` report dates.
- Rename GSD-facing project identity to ASTRA where it is a user-facing product name, without mechanically renaming internal packages, API identifiers, DB tables, environment variables or legacy compatibility fields.

### Acceptance
- The current commit SHA and local dirty state are recorded.
- Both app roots and test commands are explicit.
- Test counts are reproduced, not copied from commit prose.
- Every known concern is either confirmed with a current file/line + regression test, or marked stale/not reproduced.
- No application runtime behavior is changed in this phase.

## Phase 1 — Establish the integration boundary and remove ambiguity

### Work
- Inventory entry points, backend services, database ownership, endpoints, adapter interfaces, and frontends in both application trees.
- Verify the 130-path byte-identical SHADOWLINK-FIELD duplicate and search scripts, CI, docs, imports, and deployment files for references to each location.
- Decide whether one copy is canonical, the nested copy is a frozen snapshot, or both are intentionally distributed. Do not delete before the decision is reviewed.
- Define versioned inter-process message/adapter contracts, with capability negotiation and explicit simulation/hardware status.
- Add contract tests before consolidating implementation.

### Acceptance
- One architecture diagram has authoritative runtime and deployment boundaries.
- Every transport has a documented contract and status semantics.
- Test/launch scripts cannot silently select the wrong copy.
- Duplication cleanup is a separate PR with traceable reference checks.

## Phase 2 — Reproducible quality gates

### Work
- Add Python CI jobs for each supported application root after confirming supported Python versions and native dependencies.
- Add frontend dependency install, type-check/lint, and production build to CI; add frontend unit tests if needed.
- Mark hardware-dependent tests explicitly and skip only when a capability probe proves hardware is absent.
- Preserve software-loopback tests that cover realistic framing/decoder paths without a radio.
- Attach reports for environment, test command, pass/fail/skip totals, and build status.

### Acceptance
- Every pull request automatically checks the changed application.
- CI doesn't require secrets, radio devices, or live RF.
- Missing hardware is reported as “not run / unavailable,” never success.
- Test totals in the GSD state can be regenerated from CI.

## Phase 3 — End-to-end message security and fragmentation

### Work
- Trace payload protection across the message API, envelope, fragmenter, adapter, receive side, and final inbox.
- Define one clear security boundary: authenticated application message payload plus immutable AAD for IDs, endpoint identities, sequence, expiry and protocol version.
- Verify AES-GCM nonce uniqueness, tag verification before plaintext exposure, replay rejection, key rotation, key IDs, downgrade behavior, and error handling.
- Validate ML-KEM-768 against official FIPS 203 known-answer test vectors and independently review its implementation; keep hybrid key schedule and failure/negotiation semantics explicit.
- Review the experimental LPI crypto layer separately: CRC-8 is not a MAC. Ensure application AEAD remains end-to-end even when an adapter uses its own FEC/CRC/framing.
- Implement or test fragmentation/reassembly limits, missing fragment recovery, duplicate suppression, expiry, and larger application messages.

### Acceptance
- Round-trip tests pass across simulated adapters.
- Tamper, truncation, replay, invalid tag, wrong key, invalid header, bad KEM vectors and downgrade tests fail closed.
- No plaintext is released before AEAD verification.
- Key material and payload plaintext are absent from logs.
- Any fallback path is explicit, authenticated as appropriate, and visible to the operator.

## Phase 4 — Reliable offline store-and-forward

### Work
- Test process crash/restart before send, during send, after receiver persistence, and before ACK arrival.
- Test duplicate message submissions, duplicate frames, lost ACK, stale leases, expired messages, reconnect synchronization, disk-full conditions and competing workers.
- Verify the message state machine distinguishes queued, transmitted, received, authenticated, acknowledged, expired and failed.
- Exercise larger multi-frame transfers and selective retransmission.
- Measure delivery completion and queue delay under deterministic injected link loss and interruption.

### Acceptance
- No accepted message is silently lost during tested recoverable failures.
- Retries do not create duplicate inbox deliveries.
- `DELIVERED` requires the configured, verifiable recipient receipt.
- Payload size limits, expiry behavior and queue-full behavior are documented and tested.

## Phase 5 — PHY benchmark and measured improvement

### Work
- Run the conventional PHY baseline and CGAN path under identical documented payload/channel test assumptions.
- Separate AWGN, multipath, CFO/clock drift, phase noise, timing error, IQ imbalance/DC offset, and burst corruption in controlled simulation. Then combine them.
- Measure BER before/after FEC, FER, payload goodput, P50/P95/P99 latency, synchronization success, residual CFO, PAPR/occupied bandwidth as relevant, and confidence bounds/sample sizes.
- Compare RS and candidate codes such as LDPC only where frame sizes, latency, complexity and target platform make comparison meaningful.
- Inspect the decoder/CNN task, dataset splitting, and held-out generalization before deciding whether more training will improve the link.
- Preserve model manifest/hash, training configuration, dataset provenance, checkpoint and evaluation JSON for each accepted checkpoint.

### Acceptance
- Benchmark is deterministic enough to compare changes and records its configuration.
- Held-out tests are split by independent source/session where appropriate.
- A model change is accepted only if it improves pre-agreed metrics without unacceptable regression in other metrics.
- All reported scores include test conditions and sample sizes.
- No “undetectable”, “jam-proof”, or physical range claims are inferred from the model's training metrics.

## Phase 6 — Motorola, voice and SDR hardware acceptance

### Work
- Confirm exact Motorola product family/model, firmware, accessory/audio interface, digital-service license and supported data transport.
- Test audio/PTT and receive capture separately from message dispatch.
- Test SDR software loopback, device discovery timeout, explicit RF arming/lockout, receive decode, and safe failure modes.
- Check voice latency, jitter, interruptions, prioritization, and audio quality independently from text message retry queues.
- Keep each adapter's readiness state explicit and fail closed when prerequisites are absent.

### Acceptance
- Model/profile validation passes with vendor-approved interfaces.
- A physical test report identifies hardware, firmware, configuration, venue/authorization, test commands, and captured receiver outcomes.
- Hardware absent or unapproved means physically validated = false.
- Simulation/software-loopback remains available as a separate test tier.

## Phase 7 — Route recovery, observability and field packaging

### Work
- Inject relay outages, delayed acknowledgements, stale topology, loops, TTL expiry, and duplicate bundle delivery.
- Validate route-choice inputs and recovery time using measured link state; label simulated geometry separately from real telemetry.
- Ensure waterfall, PCAP, link-budget and diagnostic displays expose units, timestamps, source and simulation/hardware provenance.
- Profile CPU/memory/latency for edge deployment and define service start/stop, storage and recovery procedures.
- Perform security/configuration review of secrets, device permissions, logs, exports and backup/restore.

### Acceptance
- Routing tests prove message delivery/recovery or an honest failure result.
- Operator UI never displays stale simulation data as live RF.
- Field-start/stop and recovery are documented and tested on supported target platforms.
- Release report lists passed, failed, skipped and unvalidated hardware cases.

## GSD execution sequence

Use these installed skills in the actual OpenCode worktree, confirming their precise syntax with `/gsd-help`:

1. `/gsd-progress` → `/gsd-health` → `/gsd-map-codebase --fast --focus tech+arch` → `/gsd-map-codebase --fast --focus quality`.
2. `/gsd-ingest-docs` only if important local documents are absent from planning; review current `.planning` artifacts before importing.
3. `/gsd-capture` and `/gsd-review-backlog` to record and select phases.
4. `/gsd-spec-phase 0` → `/gsd-discuss-phase 0` → `/gsd-plan-phase 0` → `/gsd-plan-review-convergence 0`.
5. `/gsd-execute-phase 0 --validate` → `/gsd-verify-work 0` → `/gsd-code-review 0` → `/gsd-validate-phase 0`.
6. Repeat for one phase at a time. Use `/gsd-secure-phase` for Phase 3 and `/gsd-eval-review` for Phase 5.
7. Do not use `/gsd-autonomous` on the active shared worktree. Do not delete the duplicate tree or merge the branch without review.

If the installed skill's argument syntax differs, treat `/gsd-help` output as authoritative.

# LOCAL_UPGRADE_RUNBOOK.md — Hermes production upgrade contract

## 1. Purpose, authority, and non-authorization

This Runbook is the reusable operating contract for upgrading the production Hermes fleet. The document itself contains **no standing authorization** to start an upgrade, stop production, modify source, change configuration, install packages, restart Gateways, or schedule a Timer. A cycle may act only under either (a) a current explicit owner instruction, or (b) an enabled external maintenance controller whose recurring scope and side effects were explicitly approved by the owner. The controller must preserve that approval reference and may not expand it.

This document deliberately contains no permanent target SHA, dependency version, Cron count, PID, test total, or one-time business-task instruction. Those belong in an atomic per-cycle plan/result generated from live state.

Authority order:

1. current explicit owner instruction;
2. latest official Hermes documentation and the target version's own CLI/source behavior;
3. live production state and real consumers;
4. `LOCAL_PATCHES.md` for already approved deployed semantics;
5. the `hermes-maintenance` Skill and this Runbook;
6. historical receipts, which are evidence only.

If any lower layer conflicts with a higher layer, stop the affected action, preserve or restore known-good production, and repair governance within the authorized scope. Never treat an old target, old authorization, old failure, or old success as current authority.

## 2. Per-cycle production state

This reusable Runbook contains no cached production identity, Profile count, package count, task count, remote tip, target SHA, or process state. Every cycle records those facts in its own immutable baseline, state and result artifacts and re-reads the live system before action. A previous cycle's receipt is evidence only; it is never current authority.

## 3. Official Hermes update semantics to preserve

The current official documentation defines `hermes update` as the supported update entry. For a Git installation it pulls latest `main`, updates dependencies, detects new configuration options, and restarts discovered Hermes services.

The official workflow currently provides:

- `hermes update --check` — fetch/check whether an update exists;
- `hermes update --plan` — read-only inventory of install kind, discovered Profiles, running services, supervisors, running code identity, and restart method;
- pre-update snapshots for every discovered Profile;
- quick snapshot by default, including runtime-mutated state such as pairing data, Cron jobs, configuration, environment/auth files, while skipping individual files over 1 GiB;
- optional full backup and snapshot-restore support;
- configuration migration detection and `hermes config check` / `hermes config migrate` flows;
- service restart planning, including drain-first behavior when supported.

Local production adds governed source deltas and large/protected state. Therefore:

1. `--check` and `--plan` are mandatory evidence inputs.
2. The official snapshot/config/service-discovery behavior is reused wherever it remains compatible.
3. A quick snapshot is not a complete recovery point for large Session/business databases because files over 1 GiB may be skipped.
4. Direct unattended `hermes update` on the live modified production tree is not the sole deployment engine: it cannot decide semantic absorption, generate the local allowlist, protect all external consumers, or prove fleet-specific behavior.
5. This is not a blanket ban on the official updater. A cycle may invoke official update behavior in an isolated candidate or use it for migration/snapshot/service evidence after confirming its exact target-version behavior. Production cutover still remains externally controlled and rollback-capable.
6. Never guess flags. Read current `--help` and target source before first use each cycle.

Official references to read fresh each cycle as applicable:

- <https://hermes-agent.nousresearch.com/docs/getting-started/updating>
- <https://hermes-agent.nousresearch.com/docs/user-guide/checkpoints-and-rollback>
- <https://hermes-agent.nousresearch.com/docs/user-guide/profiles>
- <https://hermes-agent.nousresearch.com/docs/user-guide/multi-profile-gateways>
- <https://hermes-agent.nousresearch.com/docs/user-guide/features/cron>
- current Configuration, Skills, Memory, Sessions, Kanban, Browser, plugin, and platform pages affected by target changes.

## 4. Permanent owner boundaries

### 4.1 Source

- The current owner authorization determines target policy: it may require the latest official upstream or may freeze one exact previously qualified official SHA. Never silently switch policies.
- Resolve and record the immutable full target SHA at baseline and immediately before cutover. When the owner froze an exact SHA, later remote movement is audit evidence only and must not invalidate or replace that target.
- Start from untouched target source.
- Re-audit every active `LOCAL_PATCHES.md` invariant against the authorized target behavior.
- Port only the smallest already approved semantic hunk. Never copy an old whole file.
- No unlisted candidate difference reaches production.
- A new source semantic, larger authority surface, optional feature, or unrelated repair requires explicit authorization. Automatic maintenance restores known-good production instead of inventing a fix.

### 4.2 Profiles and models

- Every discovered formal Profile remains an independent Hermes Home with independent config, credentials, persona, memories, Sessions, Skills, Cron, Gateway state, model route, tools, and platform bindings.
- Never point two live agents at one Profile home.
- Crawler's execution model is immutable unless the owner explicitly directs a change. Do not alter it through config migration, CLI override, testing, or a shared default.
- Additions discovered outside the governed Profile set are classified before adoption or cleanup; they are not silently ignored or deleted.

### 4.3 Business work and history

- Historical Cron/Kanban/maintenance failure or success is telemetry and never blocks a new eligible cycle.
- Current-run locking and external-side-effect idempotency remain mandatory.
- An interrupted business run is recorded truthfully. Never mark it successful or blindly replay it when duplicate messages, writes, purchases, publications, or fees are possible.
- Low-frequency or publishing jobs are not force-triggered merely to satisfy maintenance verification. Use protected shadow/contract tests and automatically monitor first natural execution where immediate safe proof is impossible.

### 4.4 Scope discipline

- A Hermes upgrade validates fleet-wide invariants but upgrades only Hermes dependencies/components required by current target compatibility or explicitly included by the owner.
- Discovery of Node, browser, Office, database, RAG, website, container, or security state is not automatic permission to upgrade it.
- Agent-invented diagnostics, optional tools, and new tests do not become production entry points, defaults, or permanent hard gates.
- Repository-external scripts and services are real maintenance debt; classify their consumer and owner rather than treating them as invisible.

### 4.5 Data and cleanup

- Protect business databases, KB/RAG content, formal service assets, project environments, active recovery state, owner-retained evidence, and configured credentials.
- Temporary candidate/rollback material and formal compact evidence are separate classes.
- Successful production ends with one canonical Hermes source, environment, and launcher; bounded alternatives exist only during the active transaction.
- Secrets are never printed. Record key names/presence and `[REDACTED]` only.

## 5. External control architecture

A fleet update is controlled outside every Hermes Gateway. Hermes Cron cannot be the sole controller because the update stops/replaces Hermes itself.

The production design consists of:

- a user-level systemd Timer or explicitly authorized manual service start as trigger;
- one external controller service, stored outside the source tree being replaced;
- one external continuation worker, armed before `default` stops, that re-enters the unfinished transaction after the new `default` is healthy and performs verification, governance, cleanup, and final delivery without waiting for another user message;
- one global fleet-maintenance lock shared with `profile-hygiene` and any later fleet-wide maintenance task;
- an atomic current-cycle state file and immutable cycle id;
- bounded candidate and rollback workspaces;
- deterministic inventory, hash, database, process, cutover, recovery, and residue checks;
- Agent phases only for semantic upstream/local-patch analysis and evidence interpretation.

The schedule, unit names, retry cadence, exact workspace path, and current fleet size are controller configuration, not permanent Runbook constants.

### 5.1 Global lock

The lock must contain enough live identity to reject stale-file false positives: transaction id, controller PID, process start identity, state-file hash/path, acquisition time, and owning maintenance class.

Behavior:

- active valid lock: a second maintenance task exits without touching production and records a truthful skip/defer result;
- stale lock file with no matching controller/start identity: recover or remove only after current transaction state is reconciled;
- a historical failed/successful lock never blocks a new eligible cycle;
- `profile-hygiene` and monthly maintenance cannot run cutover/cleanup concurrently.

### 5.2 Durable controller state

At minimum persist:

- cycle id and authorization reference;
- current phase and phase attempt;
- production identity;
- latest candidate identity and second-resolution result;
- baseline/plan/result hashes;
- admission snapshot;
- worker/Gateway stop status;
- rollback object identities and readback status;
- cutover identity;
- per-Profile start/verification status;
- recovery state;
- cleanup state;
- final terminal state and notification receipt.
- continuation identity, origin/destination, armed/claimed/completed state, and its final-delivery receipt.

Write state atomically. On controller or host restart, resume from the first unproved phase; never repeat an irreversible side effect merely because the prior command response was lost. Restarting the Gateway does not resume an interrupted Agent turn: the controller must explicitly wake an external continuation worker after `default` is healthy. A service restart plus a status message is not continuation.

The cutover/recovery controller is a fail-closed one-shot service: `Type=exec`, `Restart=no`. `Restart=on-failure`, `Restart=always`, `StartLimitIntervalSec=0`, a timer-driven retry, or any equivalent automatic process-manager re-entry is forbidden for a controller that can stop a Gateway or replay recovery. Resume is a separately triggered, state-aware operation after the durable state has been read. Every recovery attempt records a terminal recovery-failure state before returning; re-entry into that state performs no stop/start/publication side effect until the failed prerequisite has been repaired and a new attempt is explicitly authorized. This prevents a failed recovery health check from becoming a fleet stop/start loop.

### 5.3 Terminal states

Only these terminal states are valid:

- `UPDATED_LATEST` — latest authorized target deployed, fleet verified, governance converged, transaction residue closed.
- `ALREADY_LATEST` — no newer target; required live checks completed; no transaction residue.
- `RECOVERED_RETRY_PENDING` — latest candidate/cutover failed; known-good production restored and verified; failed material removed; a later eligible run may retry whatever is latest then.
- `FATAL_RECOVERY_FAILURE` — known-good production cannot be proved healthy. External recovery authority remains alive and sends urgent alert; completion is not claimed.

Intermediate failure, notification, rollback start, test success, or Agent summary is not a terminal completion state.

## 6. Per-cycle artifacts

Create only after lock acquisition and authorization validation:

- `plan.json` — target policy, live baseline references, discovered scope, active invariants, proposed changes, verification and recovery plan;
- `baseline.json` — redacted immutable pre-change inventory and hashes;
- `state.json` — controller phase state;
- `result.json` — terminal evidence and cleanup proof;
- bounded candidate source/runtime/test homes;
- bounded rollback material;
- raw logs only while needed for the live transaction;
- one compact non-executable formal receipt after closeout.

Raw logs, temporary backups, Candidate trees, test Profiles, browser state, and controller scratch data are deleted after successful readback. Formal receipts remain outside executable production paths and contain no secrets or stale instructions presented as current authority.

## 7. End-to-end execution procedure

### Phase 0 — trigger eligibility and recovery

1. Validate the current authorization source: either the explicit task instruction or the owner-approved enabled controller contract; confirm its exact side-effect scope and immutable approval reference.
2. Acquire the shared non-blocking lock.
3. Inspect current transaction state only; old receipts do not block eligibility.
4. If a half-finished cutover exists, recover production before new candidate work.
5. Confirm external controller can query and start the `default` Gateway independently of the current chat.
6. Capture the current transaction's continuation instruction and authorized reply destination, then prove an external worker can execute it after a Gateway restart without the old Agent process.
7. Create the minimum bounded workspace and initial atomic state.

No production source/config/service change occurs in this phase.

### Phase 1 — official sources and live command contract

1. Read fresh official documentation relevant to this target.
2. Load current `hermes-agent`, `hermes-maintenance`, and relevant local-operations Skills.
3. Read current `hermes update --help`, `--check`, and `--plan` behavior.
4. Read exact target-source implementations for update, snapshot, migration, service discovery/restart, Profile paths, Cron/Kanban state, and changed features.
5. Record discrepancies between docs, installed CLI, and target source. Resolve them before action.

Unknown executables are probed only inside private state with a bounded timeout, complete process-group cleanup, and residue readback.

### Phase 2 — immutable live baseline

Capture and machine-validate:

#### Git/update

- install kind, CLI version/interpreter, branch, HEAD, remotes, upstream refs, merge-base, worktree status, worktrees, stash, tracked diff, and running code generation;
- official `update --check` and `update --plan` output;
- exact current deployed difference surface against its recorded upstream base.

#### Profiles/Gateways

- every discovered Profile home and alias;
- config schema/hash and semantic inventory;
- redacted credential-key set;
- SOUL/USER/MEMORY/Skills existence and boundary state;
- Gateway unit/supervisor, PID, start time, executable, source generation, platform state;
- model/provider/fallback/reasoning/vision/Web/MCP/TTS/STT/tools/platform routes.

#### Cron/Kanban/Sessions

- every job/card/board owner, identity, schedule/state, delivery, script/prompt/workdir/skills/tool/model selection, active lease, worker, idempotency key, and formal output;
- enabled/paused admission state exactly as found;
- state database schema and SQLite quick/integrity checks;
- current/resume-pending/process-bound/undelivered Session protection.

#### Runtimes/services/data

- every relevant Python/Node/browser/media/Office executable, package contract, realpath/version/hash, process/service consumer, and hidden fallback;
- systemd units, processes, listeners, containers, databases, GPU/RAG/MCP/web services, and real health paths;
- protected business data, formal evidence, backup/recovery state, and storage capacity.

Classify every warning as current regression, baseline-equivalent telemetry, optional/unconfigured capability, or blocker. A stale status is not a current failure.

### Phase 3 — latest target resolution

1. Fetch official refs without switching production.
2. Resolve latest target according to current authorization and official update channel; record immutable full SHA, version/tag relationship, signatures/metadata where available, release notes, migrations, dependencies, and changed paths.
3. Do not choose a subjective waiting period or older target unless the owner explicitly changes target policy.
4. Generate target-impact map against active local invariants and real consumers.
5. If no update exists, continue only the explicitly required live verification/cleanup and finish `ALREADY_LATEST`; do not manufacture changes.

### Phase 4 — isolated untouched candidate

1. Create Candidate only in bounded transaction scope, outside every production Profile home.
2. Start from untouched target source.
3. Build with target-supported interpreter/runtime and official package-manager behavior. Determine versions dynamically from current compatibility, lockfiles, and consumers.
4. Permit network/downloads only in the authorized build phase. Record sources and hashes.
5. Deny Candidate access to production Cron/Kanban dispatch, production platform delivery, writable production databases, and production Session stores.
6. Run untouched-target syntax/import/CLI/config tests before any local semantic port.
7. Never copy old venvs, `node_modules`, browser profiles, whole source files, or mutable production databases into Candidate as runtime proof.

### Phase 5 — local semantic retirement and minimal port

For every active entry in `LOCAL_PATCHES.md`:

1. Rediscover target owner symbols, sibling paths, callers, tests, docs, config/plugin/service alternatives, and current consumers.
2. Reproduce the invariant against untouched Candidate.
3. Assign exactly one primary status:
   - `UPSTREAM-ABSORBED`;
   - `EXTERNALIZED`;
   - `DEPLOYMENT-CONTRACT`;
   - `ACTIVE-SOURCE`.
4. For retained source, port only the smallest already approved semantic hunk and its focused regression.
5. Split old mixed entries into independent invariants.
6. Generate a target-specific allowlist and compare it mechanically with actual Candidate diff.
7. Any new semantic, expanded file surface for a new behavior, or ambiguous necessity blocks automatic cutover.

CI-only and package-lock differences are audited separately from production runtime patches. An inaccessible fork runner or optional diagnostic cannot force production source change.

### Phase 6 — dependency and runtime conservation

#### Python

- Discover target-supported Python range and every real consumer; never freeze the previous interpreter as permanent.
- Build a fresh Candidate environment through the exact selected interpreter/package manager.
- Treat Python virtual environments as non-relocatable: console-script shebangs embed the build path. A Candidate venv may prove the lock, but production must be synchronized or recreated at its final canonical path while Gateways are stopped; never rename a built venv across paths.
- Preserve approved external consumer packages through a formal input/hash contract rather than silently adding them to upstream metadata.
- Synchronize the Candidate from that external hash contract. Project-level `uv sync`, including `--all-extras`, is not production dependency conservation and may not substitute for the external contract.
- Run the external runtime verifier against Candidate, then use the Candidate interpreter to execute clean import/startup smokes for every enabled no-agent Cron Runner before Cron admission is restored. A green Hermes suite or `cron doctor` cannot prove Runner imports.
- Run dependency integrity, clean imports, CLI protocol, and actual consumer smokes.
- A separate Browser Use/tool environment remains only if current dependency **and real stdin/CLI protocol** compatibility cannot coexist and that exception was already authorized.

#### Node and web/desktop

- Discover the target's package manager, engine range, lockfiles, workspaces, and actual Node consumers.
- Project-local dependency trees may exist; hidden second Node runtimes/launchers may not.
- Never use broad force-upgrade commands such as `npm audit fix --force`.
- Run installation, audit, typecheck, unit tests, build, and real application smoke as separate evidence layers where affected.

#### Browser/media/Office/services

- Inventory and verify realpaths, hashes, versions, consumers, and launchers.
- Do not upgrade a browser, Lightpanda, FFmpeg, LibreOffice, jq, MCP, database, container, RAG service, or website merely because inventory found it.
- If target compatibility requires a component change, build/test it independently and preserve a single approved entry after cutover.
- Validation must not trigger hidden Playwright/browser/runtime downloads.

### Phase 7 — configuration and state migration rehearsal

1. Run target `config check` against verified copies of every discovered Profile.
2. If migration is required, generate and semantically compare candidate copies before any live write.
3. Explain every changed key, default, deletion, normalization, or schema version.
4. Preserve model/provider/fallback/tool/platform/credential scopes and crawler's model boundary.
5. Test Session/Cron/Kanban schema/state migration against consistent database copies.
6. A migration that changes unapproved production semantics blocks cutover.

### Phase 8 — Candidate verification

Apply the current risk-based matrix from the `hermes-maintenance` Skill:

- source identity, clean diff, and local invariant regressions;
- affected full suites and clean-process CLI/import checks;
- all discovered Profile config/model/tool/platform boundaries;
- safe representative Cron/Kanban/Session behavior;
- affected MCP/browser/media/Office/web/database protocols;
- no production writes, sends, publications, purchases, or duplicate side effects;
- no Candidate process/listener/browser/socket/lease/runtime residue.

Passing package installation, unit tests, process liveness, or HTTP 200 alone does not authorize cutover.

### Phase 9 — pre-cutover external recovery proof

Before stopping any Gateway:

1. Verify controller service is outside the source/runtime being replaced.
2. Verify shared lock/state durability and resume behavior.
3. Verify rollback source/runtime/config objects exist, are readable, and can be atomically restored.
4. Verify controller can independently stop/query/start each discovered Gateway unit.
5. Verify `default` can be started first and its control channel checked without relying on this Agent turn.
6. Arm a one-shot external continuation before cutover. It must wait for the new `default`, claim the transaction once, read durable state, continue from the first unproved phase, and deliver to the recorded origin; it must not merely announce that restart began. A generic post-restart recovery notice is not transaction state and may never replace this readback or prompt the owner for “what next” while a durable transaction remains unfinished.
7. Arm bounded recovery behavior before cutover begins. Read back the live controller unit and require `Type=exec`, `Restart=no`, no timer/path trigger, and no dependency that automatically starts it after failure. Reject cutover if the controller can auto-reenter. Prove in a private fleet fixture that a failed restored-generation health check records terminal recovery failure and a second invocation performs zero additional stop/start/publication actions.
8. Snapshot exact Cron/Kanban admission state for restoration.

### Phase 10 — freeze admission and force closure

The owner's maintenance policy does not wait indefinitely for Hermes background work.

1. Freeze new Cron/Kanban/Gateway task admission through current supported controls.
2. Persist current task/lease/execution state and mark interruption truthfully; do not fabricate completion.
3. Stop task-admitting Profile owners first and `default` last.
4. Send bounded graceful termination where useful, then terminate all authorized Hermes worker scopes and Gateway cgroups, including detached Hermes Cron/Kanban/process workers discovered from live ownership.
5. Verify zero in-scope survivor by cgroup/process/start identity, not name alone.
6. Do not terminate MySQL, Redis, Qdrant, Docker, SSH, RAG, websites, or external business services unless current authorization explicitly includes them and ownership is proven.
7. Do not automatically replay interrupted externally side-effecting business tasks without their own recovery/idempotency contract.

The maintenance controller itself remains outside the terminated scope.

### Phase 11 — consistent rollback material

After quiescence and before cutover:

- create official per-Profile snapshot evidence where supported;
- create additional consistent recovery material for protected files/databases omitted or insufficiently covered by quick snapshots;
- use full backup only when size/time/scope is appropriate and verified;
- hash/read back configuration, credentials metadata, units, source/runtime manifests, admission state, and database backups;
- run SQLite integrity checks on copies;
- never assume file existence means recoverability;
- do not copy secrets into logs or receipts.

### Phase 12 — final target check and atomic cutover

1. Resolve the authorized target again without changing target policy. Fetch only when the current authorization calls for a moving latest-upstream target.
2. For a moving target, invalidate/destroy Candidate if the target moved. For an owner-frozen exact SHA, require exact equality with that SHA and do not chase a newer remote tip.
3. Reconfirm Candidate diff allowlist and terminal verification.
4. Atomically replace the canonical source/runtime at the existing production entry.
5. Do not introduce permanent versioned production launchers or leave old and new environments simultaneously consumable.
6. Apply only the verified mandatory configuration/state migration.
7. Update governance candidates only after deployed bytes are known; failed Candidate evidence never overwrites production governance.

### Phase 13 — ordered start and production verification

Start order is dynamically derived from discovered ownership, with immutable control rules:

1. Start `default` first.
2. Verify new PID/start identity, canonical source/runtime, configuration, primary model route, Telegram/control-channel availability, and safe core tool behavior.
3. Start non-admitting named Profiles one at a time and verify each before proceeding.
4. Start Cron/Kanban-admitting Profile owners last.
5. Verify every Profile's independent home, model/provider/fallback, redacted credential scope, persona, tools, MCP/browser/media routes, platform state, and Session persistence as applicable.
6. Verify Cron/Kanban definitions and enabled states match baseline except approved migrations.
7. Restore admission exactly only after all prerequisite Profiles are healthy.
8. Verify safe representative scheduling/worker paths and register first-natural-run monitoring for low-frequency/publishing jobs.
9. Release the armed continuation worker only after `default` and required named Profiles are healthy. The old Agent turn may disappear; the worker owns all remaining closeout until a terminal state and delivery receipt exist.

The current chat is supporting evidence only; the external controller remains the recovery authority and the external continuation worker remains the execution authority until closeout. Never end the pre-restart turn with work still pending unless that worker is already armed and independently verifiable.

### Phase 14 — automatic rollback on hard failure

A hard failure includes new regression in source correctness, dependency compatibility, Profile isolation/model routing, credentials scope, Cron/Kanban semantics, data integrity, platform delivery, required service protocol, unique production entry, controller recovery, or cleanup.

Recovery order:

1. freeze/keep admission closed;
2. stop newly started affected Gateway/process scopes;
3. restore known-good source/runtime/config atomically;
4. reconcile configuration/state migration; prefer source/runtime rollback and do not blindly overwrite legitimate post-backup business writes;
5. start and verify `default` first, then named Profiles, then admission;
6. verify known-good fleet and business state;
7. remove failed Candidate and unneeded executable rollback residue;
8. record `RECOVERED_RETRY_PENDING` and compact failure receipt;
9. allow a later eligible run to retry the then-latest upstream. Do not let the failed target become a permanent block.

If any recovery step or restored-generation health check fails, atomically record the exact failed prerequisite and enter `FATAL_RECOVERY_FAILURE`; do not stop or restart the fleet again automatically. Keep the durable recovery material and one-shot recovery capability available, but leave the controller inactive and alert urgently. A later recovery attempt requires explicit state inspection and authorization; process-manager restart policy is never the recovery mechanism.

### Phase 15 — governance convergence

From live deployed evidence:

- update `LOCAL_PATCHES.md` with actual remaining active source, package, external, deployment, CI, regression, and retired entries;
- ensure this Runbook contains reusable method only, not cycle authorization, current target, rollback identity, task log, or test totals;
- generate per-cycle baseline/result/receipt outside these reusable documents;
- update the `hermes-maintenance` Skill only when a newly proven reusable method changes;
- compare governance allowlist with actual deployed diff and consumers;
- reload/read back governance before closeout.

A governance mismatch is a release failure, not harmless documentation lag.

### Phase 16 — two-pass cleanup and final readback

Classify before deletion. Then:

1. stop transaction-owned processes/resources;
2. remove Candidate, rollback copy, old executable environment, worktree, test Profile/Home/Session/board/database, browser profile, partial download, raw log, socket, lease, transient unit, and phase/lock state no longer required;
3. preserve protected business data and compact formal non-executable receipt;
4. scan active roots, services, processes, listeners, launchers, and links;
5. run final fleet verification, which may regenerate caches;
6. remove regenerated transaction residue;
7. repeat the scan and unique-entry proof;
8. read back canonical source/runtime, all Gateways, admission, Cron/Kanban/Sessions, protected services/data, governance, and receipt;
9. release the global lock only after terminal state is durable.

Only then report `UPDATED_LATEST`, `ALREADY_LATEST`, or a verified recovery state.

## 8. Verification requirements by domain

### 8.1 Source and governance

- target SHA resolved twice and deployed identity equals final authorized latest target;
- actual diff equals generated allowlist;
- every active invariant has untouched-target failure and retained-candidate proof, or is correctly retired/externalized;
- no unlisted source difference;
- governance matches deployed bytes and current consumers.

### 8.2 Runtime uniqueness

- one canonical Hermes source/environment/launcher;
- every approved project/tool exception enumerated and unique;
- service entry and active process executable/source identity agree;
- no hidden package-manager/browser runtime or lazy installer is reachable in production.

### 8.3 Profiles

For every discovered formal Profile:

- independent home and database;
- target-schema config and explained migration;
- redacted credential-key conservation;
- model/provider/fallback and no unintended fallback;
- crawler model boundary intact;
- persona/memory/Skill separation intact;
- Gateway generation and safe representative tool/platform routes;
- Session create/finalize/search/resume behavior where applicable.

### 8.4 Cron/Kanban/Sessions

- exact definitions/owners/enabled states/schedules/deliveries/scripts/prompts/workdirs/tool/model settings conserved unless approved migration;
- historical status ignored as launch gate;
- current-run idempotency and duplicate-side-effect prevention;
- state database integrity and protected active/resume-pending/process-bound records;
- representative safe scheduler/worker result, artifact/state transition, delivery readback where authorized, and zero residue;
- first-natural-run monitoring for unsafe-to-force tasks.

### 8.5 Services and applications

- only affected or fleet-critical paths tested;
- protocol/business checks rather than import/version only;
- unaffected MySQL/Redis/Qdrant/RAG/MCP/web/GPU/media/Office infrastructure remains healthy and unchanged unless explicitly in scope;
- no optional integration enabled to satisfy a test.

### 8.6 Recovery and cleanup

- external controller survives chat/Gateway loss;
- phase resume is idempotent;
- rollback restores and verifies known-good production;
- no blind business-data rollback;
- one production entry and zero transaction residue after two passes;
- formal receipt and protected business evidence remain correctly separated.

## 9. Retry and notification policy

- `UPDATED_LATEST` / `ALREADY_LATEST`: send one concise success summary with old/new identity, target, Profile/Gateway result, Cron/Kanban conservation, important retired/retained patches, and residue result.
- `RECOVERED_RETRY_PENDING`: send one failure/recovery summary naming failed phase/fingerprint, known-good verification, cleaned Candidate, and next eligible retry policy.
- `FATAL_RECOVERY_FAILURE`: urgent alert with exact unhealthy boundaries and external recovery state; never claim completion.
- Repeated identical failures do not justify repeated destructive loops. Keep production healthy, perform lightweight latest-upstream/relevant-fix checks, and rebuild only when inputs changed or the next scheduled cycle becomes eligible.
- Historical failure/success never permanently blocks future cycles.

## 10. Explicit prohibitions

- no old authorization reuse;
- no hard-coded future version/SHA/dependency/path/count/test total;
- no direct production source edit outside already approved minimal semantic port;
- no whole-file transplant;
- no cross-Profile model/config normalization;
- no crawler model change;
- no secrets in logs/receipts;
- no testing against writable production databases when a consistent copy suffices;
- no task-time `pip`, `uvx`, `npx`, Playwright/browser bootstrap, or hidden lazy installation;
- no blanket component upgrade, broad force dependency repair, or optional capability enablement;
- no current chat as sole restart/rollback authority;
- no Gateway restart that relies on the user sending another message to resume verification or cleanup;
- no “process running”, “tests green”, “message sent”, or “report produced” as completion by itself;
- no deletion by filename, age, or parent directory without consumer/role classification;
- no retention of old executable Candidate/rollback environment after successful closeout;
- no automatic replay of an interrupted side-effecting business task without its own idempotency/recovery contract.

## 11. Definition of done

A maintenance cycle is done only when all of the following agree:

- external controller terminal state;
- live deployed source/runtime identity;
- all required Profile/Gateway checks;
- Cron/Kanban/Session admission and integrity;
- affected real protocol/business-path evidence;
- known-good recovery proof or successful latest cutover;
- `LOCAL_PATCHES.md`, this Runbook, Skill, and compact receipt;
- two-pass unique-entry/residue readback;
- final notification result.

Completing the plan, reaching a rollback, sending a notice, or finishing an Agent turn is not completion.

# LOCAL_UPGRADE_RUNBOOK.md — Hermes production upgrade contract

## 1. Purpose, authority, and non-authorization

This Runbook is the reusable operating contract for upgrading the production Hermes fleet. The document itself contains **no standing authorization** to start an upgrade, stop production, modify source, change configuration, install packages, restart Gateways, or schedule a Timer. A cycle may act only under either (a) a current explicit owner instruction, or (b) an enabled external maintenance controller whose recurring scope and side effects were explicitly approved by the owner. The controller must preserve that approval reference and may not expand it.

The reusable procedure deliberately contains no permanent target SHA, dependency version, Cron count, PID, test total, or one-time business-task instruction. Appendix A is the explicitly retained historical incident record required by the owner; its dated identities and test totals are forensic evidence only and never current authority.

Authority order:

1. current explicit owner instruction;
2. latest official Hermes documentation and the target version's own CLI/source behavior;
3. live production state and real consumers;
4. `LOCAL_PATCHES.md` for already approved deployed semantics;
5. the `hermes-maintenance` Skill and this Runbook;
6. historical receipts, which are evidence only.

If any lower layer conflicts with a higher layer, stop the affected action, preserve or restore known-good production, and repair governance within the authorized scope. Never treat an old target, old authorization, old failure, or old success as current authority.

## 2. Per-cycle production state

Outside the dated incident appendix, this reusable Runbook contains no cached production identity, Profile count, package count, task count, remote tip, target SHA, or process state. Every cycle records those facts in its own immutable baseline, state and result artifacts and re-reads the live system before action. A previous cycle's receipt is evidence only; it is never current authority.

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

### 4.6 Browser runtime and optional-backend policy

- Treat browser automation as four separate layers: model-facing tool, Browser Use/Browser Harness driver, selected browser source, and optional `agent-browser` backend. Absence of one optional layer does not invalidate another route that passed a real navigation.
- This deployment's formal route is Browser Use/Browser Harness through the shared stable Chrome entry. PM `agent-browser` and PM Chromium are intentionally declined optional components. A `? ... not installed` line from `hermes pm doctor` with exit zero, or the optional warning row in `hermes doctor`, is not an upgrade defect and must never trigger an installation recommendation by itself.
- Before proposing `hermes pm install agent-browser --tools-only`, read the live PM dependency graph. If the package closure includes Chromium while an independently managed verified Chrome already exists, installation creates a duplicate browser owner and is prohibited without an explicit owner requirement for that backend and a complete migration/retirement plan.
- Do not rewrite Profile, Cron or Kanban definitions merely to preserve the shared browser surface. Validate the actual consumers: one harmless `browser_exec` navigation under the selected route, unattended task-private runtime/profile behavior, PAC where required, random CDP allocation and zero process/socket/profile residue.
- Never delete the existing browser runtime while any Runner, Browser Harness session or independently supervised workload consumes its stable entry. A compatibility symlink to the same inode/bytes is not a duplicate installation; a distinct engine such as Lightpanda is not a duplicate Chromium.

### 4.7 Session storage and capacity advisories

- Treat a large `state.db` warning as a diagnostic, not a cleanup mandate. Read the installed optimizer/prune implementation and record integrity, FTS version, page/freelist use, table/index contribution and official dry-run candidates before any stop window.
- Run official online maintenance first. Test any offline VACUUM or row-classification idea against a live-consistent copy; compare integrity and physical saving. Similar text is not deletion proof when lifecycle, compaction, display, platform or disposition differs.
- Preserve real history when safe candidates are absent or reclamation is immaterial. Do not stop/restart the Gateway merely to silence Doctor, and do not invent a retention policy. Report the capacity advisory as retained-history impact.

### 4.8 Secrets and Profile-local provider routes

- MCP `Authorization` values live only in each Profile's mode-`0600` `.env`; `config.yaml` contains `${VAR}` substitution. Validate config parsing, standalone MCP resolution and live/fresh-session behavior as separate layers, then delete credential-bearing rollback copies.
- Keep a Profile-local provider adapter physically and configurationally absent from every other Profile. A provider capability is accepted only after a fresh owning-Profile session uses the selected backend and its state database shows the real tool chain.
- Never infer that a successful browser/web fallback proves Firecrawl or another named backend. Preserve backend identity in the probe and inspect the recorded tool call. Remove paid-test media and temporary sessions/artifacts after evidence is captured.

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
- Preserve approved external consumer packages in a PM-managed plugin manifest rather than silently adding them to upstream metadata or manually installing into the selected venv.
- Resolve the selected PM environment at launch from the active install metadata; never embed an environment ID in a production script, Cron prompt, Profile config, or systemd unit.
- Every external unit must declare any non-system executable directories it consumes (for example a package-manager-owned compiler) in its own `PATH`; an interactive-shell PATH or a previous process generation is not deployment evidence.
- Install/synchronize the Candidate through Hermes PM from that external manifest. Project-level `uv sync`, including `--all-extras`, is not production dependency conservation and may not substitute for the PM/plugin contract.
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
- installed optimizer/prune semantics, FTS version, page/freelist contribution, safe dry-run candidates and copy-only VACUUM benefit before any Session-store downtime or deletion;
- retained-history size advisories classified separately from corruption, with no content-only deduplication or invented retention policy;
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
- no literal MCP Authorization values in config, Git, receipts or retained rollback copies;
- no testing against writable production databases when a consistent copy suffices;
- no Session message deletion or Gateway downtime solely to make a capacity warning green;
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

## Appendix A — 2026-09-30 through 2026-10-02 incident record and permanent lessons

This appendix is historical evidence for the failed upgrade cycle, not reusable authorization and not a substitute for a fresh per-cycle plan. It is retained because the owner required the errors, impact, causal chain, repairs and prevention controls to be recorded in the Runbook itself.

### A.1 Why production was stable before the upgrade but failed after it

The upgrade did not introduce one isolated defect. It changed the selected PM environment and process generation while production had accumulated undeclared external consumers and implicit launch assumptions. Before cutover, those consumers happened to resolve the old PATH, old internal venv, shared Profile state and interactive Browser Harness defaults. After cutover, the same hidden assumptions resolved differently. The upgrade therefore exposed a cross-layer contract failure:

1. several repository-external runners selected `shutil.which("hermes")`, an internal venv, or inherited PATH instead of the stable launcher;
2. isolated Agent homes did not carry the formal PM install registry, so the launcher could fall back to a bare tools Python that lacked provider dependencies;
3. the read-only Bubblewrap root omitted the PM lock and environment lease write surfaces required by the official launcher;
4. Browser Harness runtime, socket, daemon and Chrome ownership were inherited from an interactive environment instead of assigned to the run;
5. business Agent subprocesses received broader tools and environment than required, which enlarged the credential and filesystem exposure surface;
6. the WeKnora full-build carrier was first coupled to disposable Hermes worker scopes, then shadowed by a transient unit; the persistent unit was not a fully governed asset at cutover;
7. the cutover admission gate covered config syntax and selected unit/process checks but did not enumerate every Profile, Cron definition, Kanban board, external systemd unit, runner interpreter, sandbox mount and credential boundary before restoring work;
8. weak indicators—exit code zero, an active scope, a live outer PID, one journal line or a self-authored receipt—were treated as business acceptance;
9. independent pre-existing workflow defects were uncovered during recovery (Consulting prompt interpolation, MA Crawl status vocabulary, Agency Info recovery/readiness/qualification conservation, and stale Competitor provider tests). Those defects were not all caused by the Hermes upgrade, but the incomplete pre-cutover contract allowed them to become entangled with upgrade recovery.

The decisive cause was therefore **incomplete fleet/runtime contract capture followed by premature admission**, not “the new Hermes version is generally unstable.”

### A.2 Incorrect operations and actual impact

- Work was restored before real sandbox, Browser Harness, interpreter, credential-boundary and checkpoint-resume probes had all passed. Industry Intelligence, Competitor Info, IPO Crawl, Consulting Intelligence and WeKnora then had to be stopped and frozen again.
- Agent subprocesses were allowed to inspect more of the host environment than their task required. Two abnormal recursive scans were terminated, and Competitor/IPO worker scopes were stopped. No resulting business success was claimed.
- A deletion-after state was initially reported as a deletion-before fact for the MA preacceptance records. The corrected evidence is that both named projects had one row before deletion and zero afterward.
- A stale/incorrect pytest node selection returned exit 4, and one combined run was allowed to remain as a compressed exit-1 summary instead of immediately extracting the failing assertions. Both were invalid evidence.
- A fleet-wide `gateway restart --all` was launched from inside the multiplexed Gateway's own execution tree. It terminated the executor, interrupted three Agent sessions and the active monitor, and left the shared Gateway unavailable from 2026-10-01 23:46:39 to 2026-10-02 00:04:31 (about 17 minutes 52 seconds). No Cron execution was in flight and the independently supervised full-index unit survived, but this was an avoidable fleet outage. The permanent control is to treat `--all` as an externally supervised fleet cutover only, never invoke it from a served conversation, and never restart any Gateway when the owner has forbidden restart.
- The first Graph failure conclusion confused parent-supervisor survival with recovery of the failing derived stage. The parent PID and journal did recover automatically, but the same Graph JSON failure repeated at 06:58:03, 06:58:29 and 06:58:55. The underlying raw-newline class closed only after a separately tested, reversible category-level controller repair and live Graph receipt verification. Future conclusions must join supervisor state to the exact latest stage span, queue state, failure count and receipt.
- A later deterministic `Content Exists Risk` rejection exposed two additional gaps in sequence. First, converting an unsupported failure into repeated native `run_now` calls preserved the parent but still created a tight stage-local retry loop. Second, the successful digit-preserving Chunk update was initially reported as a readback mismatch because the official API removed one trailing line break. The corrected controller recognizes the seven-or-more-digit registration-identifier class, verifies digit conservation, uses the same exact-or-trailing-whitespace readback equivalence as the Graph JSON path, and requires a live zero-failure complete receipt before acceptance. Future provider refusals must be classified as progress, deterministic repeat or unsupported input; parent liveness alone never closes them.
- The first unsupported-Graph regression invocation named a nonexistent pytest class and exited 4. A later combined manual recovery command updated the Chunk successfully but then exited 1 because a follow-on helper was called with the wrong argument shape; another inspection attempted a nonexistent client method. Each partial side effect was separated and read back before any success claim. Future recovery commands must be split at state-changing boundaries and use the live client schema before invocation.
- The closeout JSON was written with an incorrect deployment/publication commit SHA even though local and remote branch heads were correct. The receipt was corrected only after exact full-SHA readback. Future closeout generation must obtain the SHA programmatically from both targets and reject inequality or a value not equal to either target.
- Delayed Gateway delivery made pre-repair alerts appear after the repair. The monitor's event timestamp, not notification arrival order, is authoritative. A historical `inactive/dead` event with `Result=success` was also a requested investigation stop, not a new crash.
- The WeKnora controller's stopped state was initially discussed as if it could be a spontaneous exit. Two exact journal windows later proved both observed exits followed explicit systemd stop operations and ended through `InterruptedError: stop requested`; no OOM event was found. The controller did not spontaneously crash in those observations.
- Sensitive same-user shell snapshots were generated by tooling. After classification showed mode `0600`, no live process references and no evidence of external disclosure, the two remaining unintended copies were removed without printing their values. Credential values remain `[REDACTED]` in all records.
- Restoration and closure claims were made from partial surfaces. The cycle was returned to `NOT_FULLY_CLOSED`; at that stage four affected Cron jobs and the WeKnora full build were frozen until their remaining gates passed. Later resume decisions are recorded separately and do not rewrite that historical state.

### A.3 Repairs already verified

- Production Hermes calls use `/home/dionysos/.local/bin/hermes`; production Python calls use `/home/dionysos/.hermes/services/python-runtime/python`, which resolves the selected PM environment dynamically.
- Isolated Agent homes expose the formal install registry read-only and only the install lock and selected environment lease directories as writable.
- Competitor subprocesses no longer receive general terminal access or crawler credentials. A real Bubblewrap probe proved the crawler environment file was masked, Qixin credentials were absent, and only the explicitly required search credential remained.
- IPO Browser Harness received run-owned runtime/temp directories and a stable auditable name. A real Chrome/CDP probe used an OS-assigned loopback port and left no process group, listener or runtime directory.
- The complete current WeKnora test directory passes 144 tests plus 7 subtests; the focused 15-second full-build monitor is included and its dedicated three-test boundary also passes. The selected-PM Tender/DLOM cohort passes 144 tests plus 7 subtests. Earlier affected-crawler regression totals remain historical evidence for their then-current inputs rather than a substitute for these current suites.
- All eight formal Profile configurations passed independent config checks; the default multiplexed Gateway is the sole dispatcher owner; Gateway and PAC are active with zero restarts at the audit readback.
- Root, crawler and writer Cron definitions were enumerated by owning Profile. Competitor Info execution `4e98c424917746eda09c771d0619e19f` and Consulting Intelligence execution `56af312ab32a44fb8ae47eb74ba3802f` both completed with `error=null`; their formal receipts and vanished worker PIDs were read back. Tender and DLOM remain paused/disabled; their compatibility migration does not itself resume business scheduling.
- Four Hermes Kanban databases have zero nonterminal tasks. A fifth `kanban.db` hit belongs to the business knowledge-base application and is not a Hermes task board.
- The old PM environment has no directory, symlink, process command, mapping, open-file or executable/config consumer. Historical logs and state-database text remain forensic evidence only.
- WeKnora readiness currently binds controller commit, controller script SHA-256, official runtime commit, deployed image, embedding model and regression evidence before every write-capable entry point. The persistent full-build unit uses the dynamic Python launcher, explicit PATH and control-group termination. Its parent supervisor remains alive while failed apply children retry from the durable journal every 15 seconds; requested stops do not emit failure retries. The original 60-second service/journal progress reader was retired and its semantics were extended in the sole current persistent 15-second monitor, which reports service loss, restart growth, apply-cycle failure and journal corruption. The incremental unit remains disabled and inactive.

### A.4 Historical pre-activation release matrix

This section is the preserved pre-activation snapshot of the 2026-09-30 upgrade cycle, not a statement of today's runtime. Its pending activation was subsequently exercised and recorded under `post_reload` in `/home/dionysos/.hermes/hermes-upgrade-20260930-result.json`. Consult that receipt and a fresh process/config/tool readback before acting. A historical reload authorization is consumed, not reusable; the 2026-10-03 audit explicitly forbids every Gateway restart.

- **Source/governance — PASSED before final activation:** the owner-authorized upstream target remains frozen; no pull, rebase or attempt to track moving upstream was performed. The patch ledger and Runbook now cover the browser decision, npm/Desktop compatibility, Session-store preservation, externalized MCP secrets, Profile-local subscription adapters and WeKnora recovery contract. Final source publication is gated on the post-reload evidence line below.
- **Fleet — PASSED on disk and standalone paths; one activation transition pending:** all eight Profile configs parse, all eight default-model fresh CLI sessions returned the requested control result, and all eight standalone `jz_rag` MCP tests enumerate seven tools. Every MCP Authorization header is environment-substituted and every Profile `.env` is mode `0600`. The single default multiplexer serves all eight Profiles; its old PID predates these config/source repairs, so one owner-authorized, exact-profile, drain-aware reload is required to bind the live process.
- **Cron/Kanban — PARTIAL WITH NONBLOCKING DIAGNOSTICS:** all Profile definitions and four Hermes boards were read back; nonterminal cards are zero. Cron Doctor still reports catch-up advisories whose exact schedules/executions remain preserved for natural-fire reconciliation. They are not relabelled as failed business runs and are not manually fired merely to make diagnostics green.
- **PM/runtime — PASSED:** one canonical install (`4e34beaf8bad4aa9`), one selected environment (`634f2516107a4283b02eddd4a2889bb4`), Python `3.14.7`, Node `26.7.0`, npm `12.0.2`, stable Hermes/Python launchers and zero active old-environment consumers were verified. PM Doctor exits zero; intentionally absent optional packages remain inventory, not failures.
- **npm/Desktop — PASSED:** root npm audit reports zero vulnerabilities. Desktop typecheck/lint exits zero; UI passes `1124` files / `9930` tests; Electron-platform passes `336` files / `3181` tests with documented skips; the Electron `41.10.6` Linux package build completes. Existing lint warnings and optional HUD X11 native-build degradation are non-error output and were not hidden.
- **Session storage — PASSED FOR SAFE MAINTENANCE / ADVISORY RETAINED:** official optimize-storage ran; five principal Profiles had no 90-day or never-active prune candidates. A consistent-copy VACUUM passed integrity before/after and reclaimed only about `1.057%`. Content-similar rows had lifecycle/identity differences, so no real history was deleted and the large-store Doctor advisory remains truthful.
- **Provider routes — PASSED at their authorized boundaries:** Crawler MiniMax cold-start discovery passed focused tests and a fresh session; Crawler Firecrawl session `20261002_131841_ab8c9b` returned `FIRECRAWL_EXTRACT_OK` with the real extractor result in Crawler `state.db`; auditor2 Alibaba Token Plan CN search, extraction and image generation passed real calls, and test media/backups were removed. The Alibaba adapters remain absent from every other Profile.
- **Browser — PASSED for the formal route:** Browser Use/Browser Harness navigated successfully through the one stable Chrome `152.0.7977.75` binary, then its test daemon/process/listener residue was removed. PM `agent-browser` and PM Chromium remain intentionally absent. The separate active MA Crawl browser is run-owned business work and was neither stopped nor misclassified as test residue.
- **WeKnora controller/readiness — PASSED:** current controller SHA is `baf5ce4b6d2878dc07a352353e59a5eea040965fffdf3bad8899b704fd9fcd83`; readiness identity matches controller/source/image/model. The controller suite passes 85 tests plus 7 subtests, the complete directory passes 144 tests plus 7 subtests, and the focused monitor passes 3 tests.
- **WeKnora full index — RUNNING/ACCEPTED CURRENT BOUNDARY:** the durable parent remains active with restart count zero under the selected PM runtime. The current 3,226-upload journal advanced from five intents/two verified after final repair to at least 100 intents/99 verified by 13:53 CST. Full corpus completion remains a multi-day business gate; the incremental unit remains intentionally disabled and inactive.
- **Business scope — PRESERVED:** completed Competitor, Consulting and MA Crawl receipts remain closed; current run-owned business workers and browsers were not killed by audit cleanup. Tender current testing remains outside this upgrade audit; DLOM remains disabled. No paused schedule was resumed merely for verification.
- **Cleanup — PASSED WITH PROTECTED HISTORY EXCLUSIONS:** obsolete upgrade workspaces, duplicate executable environments, credential-bearing temporary backups, paid-test media and test browser residue were removed. Business history, databases, formal manifests, model/index state and live run-owned work were preserved. Docker has eleven named images and zero dangling images; broad prune was not used.
- **Final activation controller — BOUNDED TRANSITION CONTRACT:** after source publication, the external one-shot controller uses `hermes --profile default gateway restart` without `--all`, waits for in-flight turns, verifies a replacement PID, current unit definition, all eight served Profiles, Profile config/MCP checks, Cron/Kanban/services and zero new test residue, and writes the real outcome to `/home/dionysos/.hermes/hermes-upgrade-20260930-result.json` before sending the final receipt. This Runbook records the required transition and deliberately does not pre-assert its runtime outcome.

### A.5 Permanent prevention controls

1. Build the executable-consumer graph before changing a PM environment: every Profile, Cron, Kanban dispatcher, external unit, runner, interpreter, sandbox, browser and credential source must map to one stable entry.
2. Freeze admission until the matrix is complete. Syntax checks and process liveness may support a gate but can never close it.
3. Require real runner-level probes for every distinct launch class: ordinary Profile, Cron script, Kanban worker, isolated Agent, Bubblewrap, Browser Harness and external systemd unit.
4. Prove checkpoint/resume semantics before stopping a long writer. A durable intent is not a verified completion, and a completed remote object may still require lost-ack reconciliation.
5. Treat operator stop, crash, OOM, provider refusal, tool failure and business-semantic rejection as different states backed by PID/cgroup/journal/kernel/business evidence.
6. Never restore all paused jobs as a batch. Restore one authorized job from its own checkpoint, obtain two-point business progress and side-effect readback, then advance to the next.
7. Preserve forensic history while removing executable residue. A historical environment ID in a log is not an active consumer; an executable reference, process mapping or enabled unit is.
8. After a failed upgrade, keep the formal result `NOT_FULLY_CLOSED` until production work, documentation, cleanup and final notification all agree.
9. Browser diagnostics must distinguish optional-component inventory from functional health. On this deployment, Browser Use/Browser Harness plus the stable external Chrome runtime is the accepted production path; PM `agent-browser`/Chromium remains intentionally absent. Do not repeatedly ask the owner to install it, do not count that absence as an error, and do not install it to silence a warning. Reopen only on an explicit new backend requirement followed by full consumer migration and single-runtime proof.

### A.6 2026-10-03 verification corrections and incomplete gates

The renewed 19-item, three-pass audit is still in its first pass. This section records verified corrections, not a closure receipt. No Gateway restart is authorized or performed in this audit.

- An initial statement that three Hermes files were uncommitted was unsupported. Fresh `git status --porcelain` was empty before the governance corrections; the statement was explicitly withdrawn. Always obtain the current worktree state before claiming pending changes.
- LP-023 and LP-024 had documented necessary deltas whose paths were missing from the ledger's top-level allowed surface. The missing exact paths were added; a mechanical comparison with the fixed authorized baseline found 30 changed paths and zero unlisted paths. No runtime source delta was added by this correction.
- The historical pre-activation matrix in A.4 was incorrectly labelled current. It is now explicitly historical and points to the actual `post_reload` receipt; consumed reload authority must never be replayed.
- Checking only the `monitor_full_index.py` process and a guessed same-name unit did not establish that no background monitoring had ever existed. A separate `weknora-final13-full-index-monitor.service` was prematurely added and enabled. It was then stopped, disabled and deleted; its default-target link disappeared, its PID exited, and systemd read back `LoadState=not-found`. The original monitor and controller hashes remain unchanged. The original full-build supervisor PID 58637, apply PID 58670 and Gateway PID 655113 remained alive; the full-build restart count remained zero. Do not infer a missing component from a name-only process search, or treat an existing retry supervisor as equivalent to a separate health/alert observer.
- The real original observer is `proc_3072b70330d3`, formerly PID 141482, using the existing `scripts/monitor_full_index.py --interval 15`. Its last retained health event is 2026-10-02T14:03:03.574232+08:00. The root process receipt records exit -15, `completion_reason=killed` and `termination_source=gateway_shutdown`; the Profile copy has the same output/exit but lacks the termination source. PID 141482 is absent at the fresh audit. This is a process-ownership and restoration gap, not permission to invent a replacement implementation. The existing controller's durable apply supervision remains active, but does not close the observer-restoration gate.
- A combined native pytest invocation inherited live Gateway flags and ran outside the official per-file isolation contract: 481 tests passed, 52 failed and 8 skipped. A read-only checkout mount, fresh per-file processes, scrubbed environment and isolated cgroup recovered the relevant source checks without changing runtime code. The nested Bubblewrap attempt and read-only test-cache writes were test-topology failures, not production acceptance; the remote-image regression passed in its writable scratch-only cache, and all four original skill-sandbox assertion functions then passed natively against task-private fixtures. Keep the exact invocation and evidence class; do not relabel these mixed probes as one all-green pytest run. Test outputs and empty test directories were cleaned after checking live references.
- Both an incorrect line-numbered JSON parse and a repeated `read_file` response carrying an unchanged marker interrupted a scratch-ledger update; no target was written by either failed parse. The update resumed from the already loaded persistent object. Reuse the known read result rather than treating a dedup marker as file content.
- The eight fresh config checks and eight standalone RAG MCP connection tests passed, discovering seven tools each. This proves those boundaries only, not all live Gateway tool exposure, every model/media call, complete package necessity, whole-system privileged health, or the requested three full audit passes. Four Doctor capacity findings and two default Cron catch-up findings remain visible. Do not delete real history, edit execution history, install declined browsers or create operational layers merely to manufacture a green report.
- MinerU exit 137 with `OOMKilled=false` is not a proven OOM incident; its existing idle watchdog and on-demand launcher must be evaluated together before treating a stopped container as a fault. Current parsing acceptance later passed via the existing production entry: version 3.4.5, three scanned pages, three tables, source amounts/formula/Chinese/English matched, QC passed without repair. The sole named audit job was purged after evidence capture; the conversion lock protected restoration to the pre-test idle/stopped state. No container image or configuration was replaced.
- Audit command-interface mistakes were corrected without production changes: `read_file`'s wrapped programmatic response was incorrectly indexed as bare content; an unsupported `cleanup-job.sh --purge` argument was incorrectly assumed to remove durable job output (the script accepts only JOB_ID and removes temporary work); an OfficeCLI resident's PPTX was read directly before using its documented close/save flush boundary. Read the actual return schema, exact script interface, and producer's flush contract before asserting a write or cleanup succeeded.
- Paid TTS validation incorrectly called unactivated PATH `ffprobe` from a direct shared-Python audit process; the exception prevented recording complete audio acceptance, despite at least one synthesis command returning zero. Owned media/text were removed and no media was delivered. PM Doctor then proved managed FFmpeg/ffprobe 9.0.1 already installed; official `pm.activate()` exposed both and reported no problems. This was an audit harness prerequisite failure, not a missing-package or TTS-service diagnosis. Validate all offline decoder/cleanup prerequisites before spending generation quota; do not install duplicates or silently repeat paid probes. The eight-profile pre-paid dry run covered 21 characters each, 168 in total; complete TTS decoding acceptance remains open.

### A.7 2026-10-03 voice credential restoration and repeated audit/continuity errors

- The operator initially reported that all eight Profiles lacked `DASHSCOPE_API_KEY` after inspecting isolated shells and their `.env` files. That conclusion omitted the formal Gateway credential source. The existing unit loads `/home/dionysos/.hermes/secrets/voice-cloud.env`; a read of Gateway PID 655113's start environment confirmed the ASR key is present, and the source file contains the existing dedicated `DASHSCOPE_API_KEY` and `MINIMAX_CN_API_KEY` (values `[REDACTED]`, mode `0600`). The broad credential-loss/voice-service-failure claim was withdrawn. Shell absence is not Gateway absence; inspect service injection, launch environment, Profile scope and child passthrough separately.
- The installed multiplex boundary resolves command-provider passthrough against the owning Profile's secret scope, not arbitrary launch-process environment. The eight configurations had no enabled source supplying the shared dedicated voice file to those scopes. The upgrade's acceptance did not cover this credential handoff. This is a missing production configuration/acceptance boundary, not evidence that the original provider keys, models or voices stopped working.
- After the owner's explicit restoration instruction, the official `secrets.command` source was configured in all eight Profiles via `hermes --profile <id> config set`, using the existing stable Python to emit the existing dedicated voice dotenv file. `enabled: true`, `helper_timeout_seconds: 3`, `override_existing: false` are explicit. A read-only candidate proved both keys resolve before any write; one mode-0600 configuration rollback copy per Profile was retained. Semantic comparison proved every other configuration block, including the complete STT and TTS settings, stayed unchanged. No Token Plan key was borrowed, no credential value printed/copied into YAML, no official source or skill modified, and no Gateway restarted.
- Real acceptance used the installed Profile-home override, official secret-source hydration, multiplex secret scope, command TTS dispatcher and `transcribe_audio(source='gateway')`, with PM activated before decoding. All eight original voices/models produced fully decoded MP3; all eight original Alibaba ASR calls returned the exact words `语音恢复验收，今天正常工作。` (punctuation-only differences in two responses), `provider=aliyun`, `success=true`, with no local fallback. Eight config checks returned zero. This proves the configured per-Profile dispatch boundary, not eight newly captured Telegram inbound voice events. A separate current-session `text_to_speech` call succeeded with `provider=dynamic-minimax`; its 53,556-byte output independently decoded. Gateway remained PID 655113 with its prior start time; no restart occurred.
- Despite the earlier PM lesson, a subsequent fresh cleanup/readback shell AGAIN omitted `pm.activate()` and failed with `FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'`. Eight config checks, settings conservation and removal of the eight test MP3 had already succeeded before that exception. The corrected fresh shell activated PM, decoded the retained live delivery file and rechecked the eight exact-word results; no paid API call was repeated for this decoder retry. Prevention must be executable at every fresh audit-process entry, not only mentioned in prose: activate PM and verify decoder paths before any real media call or media readback.
- During the resumed Docker inventory, `docker ps --format json` was incorrectly assumed to be safe metadata. Its `Command` field included Redis credential arguments and entered the internal tool transcript. The locally retained Docker audit JSON was immediately sanitized by deleting every `Command` field and set to mode `0600`; no credential is repeated here (values `[REDACTED]`). The internal transcript remains historical evidence and was not silently rewritten; no external disclosure is established by this observation. Future Docker probes must select only Name/Image/State/restart fields before printing or persisting results; never print complete container commands, Config.Env or raw inspect payloads. This is an operator diagnostic-output error, not a Docker runtime fault.
- The voice subtask was reported finished and the conversational turn ended while the parent 19-item/three-full-pass audit remained incomplete. This was a scope-continuity error: a focused repair does not replace the original contract. The latest voice repair and repeated PM error were NOT recorded in this Runbook at the time of that reply; this section remedies the omission rather than retroactively claiming they had been recorded. The parent audit remains open, and every pass/item requires its own actual evidence; a repeated inventory command is not three completed full audits.

The audit may close only after the original 19-item contract, its later owner corrections, actual consumer ownership, cleanup records, runtime readback and three full-pass evidence agree. Evidence gaps stay open; no absolute future-success claim is made from a partial audit.

- RAG MCP exposure regression and repair (verified 2026-10-03): every Profile's `platform_toolsets` explicitly listed `oss`, and the installed `_merge_mcp_servers` rule turns an explicit non-empty MCP-name list into an allowlist - `jz_rag` was therefore configured but not selected, and a real fresh-process platform-schema probe showed zero `mcp__jz_rag__*` tools reaching the model on cli/telegram/dingtalk for all 8 Profiles. Connection health (`mcp test`) had been mistaken for model-facing availability. Repair: append the documented `jz_rag` alias to exactly those three platform lists per Profile via official `hermes config set` (24 fields), with pre-write semantics snapshots, protected-object hashes, and a read-only candidate proof; nothing else changed. Post-write acceptance through the actual dispatch boundary (`handle_function_call` with the platform-selected toolset): all 8 Profiles search 13 registry-exact knowledge bases in hybrid mode, retrieve real passages, and re-read the retrieved chunk from its document with identical content and index. Verification boundary: per the installed loader, new sessions/prompts read the fresh config, while already-existing conversations keep their frozen schema until `/reload-mcp` erases and re-discovers MCP tools in that conversation; the live Gateway process was not restarted, and this audit performs no restart. Future upgrades must treat explicit MCP-name lists in `platform_toolsets` as allowlists and re-run a model-facing schema probe per platform, never only a connection test.

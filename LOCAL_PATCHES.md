# LOCAL_PATCHES.md — deployed Hermes delta ledger

## 1. Scope and authority

This file records only local source deltas that remain necessary on the authorized upstream base, their focused regressions, and compact no-port decisions that prevent retired code from returning. It is not a deployment receipt, incident log, runtime inventory, authorization record, or service runbook.

**Policy:** upstream first. Retain a source delta only when the exact target lacks equivalent behavior, no supported configuration/plugin/service boundary preserves the invariant, a current consumer exists, and a focused regression fails without the delta. Re-check all conditions on every upgrade.

## 2. Comparison contract

- Authorized upstream base: `v0.22.5` / `bf0203a794a07aac3ff764972ab9087baa4e4f4e`.
- Compare the candidate and later deployment against that exact commit, never against a moving branch or symbolic channel.
- Current HEAD, worktree state, process state, test transcripts, package-manager generations and remote tips belong in the cycle receipt, not here.
- This ledger does not authorize an update, fetch, merge, rebase, restart, publication or production cutover.

## 3. Allowed difference surface

### 3.1 Runtime source

1. `cron/executions.py`
2. `cron/scheduler.py`
3. `cron/scheduler_script.py`
4. `hermes_cli/config_home.py`
5. `hermes_cli/kanban_db_dispatch.py`
6. `tools/browser_use_cli.py`
7. `tools/kanban_tools.py`

### 3.2 Focused regressions

1. `tests/cron/test_cron_script.py`
2. `tests/cron/test_run_one_job.py`
3. `tests/hermes_cli/test_config.py`
4. `tests/hermes_cli/test_kanban_core_functionality.py`
5. `tests/hermes_cli/test_kanban_gateway_restart_handoff.py`
6. `tests/hermes_cli/test_kanban_skill_readonly_sandbox.py`
7. `tests/tools/test_browser_use_cli.py`
8. `tests/plugins/test_kanban_model_override.py`
9. `tests/tools/test_kanban_tools.py`

### 3.3 Governance

1. `LOCAL_PATCHES.md`
2. `LOCAL_UPGRADE_RUNBOOK.md`

No frozen-target npm/Desktop compatibility delta remains on this target. Deployment configuration, PM facts, external dependency overlays, runtime symlinks and service units are deployment contracts, not source patches.

## 4. Active local source deltas

### LP-001 — unlimited Cron pre-run script duration

- **Files:** `cron/scheduler_script.py`, `cron/executions.py`.
- **Invariant:** exact numeric zero for `cron.script_timeout_seconds`, `HERMES_CRON_SCRIPT_TIMEOUT`, or the module test override means no wall-clock deadline; positive and invalid values retain upstream behavior.
- **Consumer:** long stateful Cron runners whose checkpoint/recovery contract owns completion.
- **Necessity:** the exact target accepts only positive values and otherwise restores its default timeout; a large finite number is not unlimited.
- **Minimality:** return `None` only for exact zero, carry that through deadline/communicate handling, and prevent live-owner stale reclamation from inventing a deadline.
- **Regression:** the three `script_timeout_zero_means_unlimited_*` tests in `tests/cron/test_cron_script.py`.
- **Retire when:** upstream defines and tests equivalent unlimited semantics including execution-ledger ownership.

### LP-003 — per-profile Kanban worker fan-out

- **File:** `tools/kanban_tools.py`.
- **Invariant:** every worker retains lifecycle tools, while `kanban_create` and `kanban_link` are hidden and rejected when `kanban.worker_can_create_tasks: false`.
- **Consumers:** orchestration profiles may fan out; restricted specialist profiles may not.
- **Necessity:** removing the Kanban toolset also removes lifecycle tools; the target has no equivalent per-worker create/link policy.
- **Minimality:** one config reader, one offer-time gate and defense-in-depth handler checks; default `true` preserves upstream behavior.
- **Regression:** `test_kanban_worker_can_hide_create_and_link`.
- **Retire when:** upstream separates worker lifecycle authority from create/link authority per profile.

### LP-004 — read-only Skill trees inside Kanban workers

- **File:** `hermes_cli/kanban_db_dispatch.py`.
- **Invariant:** a dispatched worker may read but cannot modify any visible default, profile, external or symlink-target Skill tree.
- **Consumer:** all Linux Kanban workers in this deployment.
- **Necessity:** same-user mode bits are reversible by a worker; toolset filtering does not block generic file/shell writes; the target has no equivalent filesystem boundary.
- **Minimality:** wrap only workers that can see an existing Skill root; `--ro-bind` only those roots/targets and fail closed if a required mount cannot be established. A profile with no Skill roots needs no mount.
- **Regression:** `tests/hermes_cli/test_kanban_skill_readonly_sandbox.py`.
- **Retire when:** upstream provides an equivalent worker filesystem/identity sandbox covering all write paths.

### LP-005 — Kanban worker routing-environment scrub

- **File:** `hermes_cli/kanban_db_dispatch.py`.
- **Invariant:** a detached worker inherits no interactive Session or Gateway routing identity.
- **Consumer:** every Kanban worker launched from a Gateway or interactive parent.
- **Necessity:** the target removes current `_VAR_MAP` keys but not all future `HERMES_SESSION_*` / `HERMES_GATEWAY_*` names and the two legacy keys.
- **Minimality:** one prefix/key removal loop before worker-owned values are injected.
- **Regression:** routing-family assertions in `test_default_spawn_does_not_auto_load_any_skill`; the test isolates sandbox and restart-safe wrappers so it measures this boundary only.
- **Retire when:** upstream applies a prefix-complete dispatcher-child routing sanitizer.

### LP-006 — unattended Browser Use run ownership

- **File:** `tools/browser_use_cli.py`.
- **Invariant:** unattended Cron/Kanban Browser Use gets a run-private Harness runtime/name/workspace and, when no CDP is supplied, a run-private governed Chrome on an OS-assigned loopback port with its own profile/cache; downloads and lazy installs stay disabled, task workspaces are never cleanup targets, and only owned temporary state/processes are removed.
- **Consumers:** the live Gateway exports `HERMES_RUN_OWNED_BROWSER`; Kanban workers also activate through `HERMES_KANBAN_TASK`.
- **Necessity:** the exact target namespaces Harness directories per Profile but not per unattended run, and its local-Chromium route requires the deliberately declined `agent-browser` backend.
- **Minimality:** keep only the existing run-owned gate, guard environment, governed-Chrome lease/cleanup and four focused `TestRunOwnedBrowserLease` regressions; all unrelated v0.22.5 Browser routing remains upstream.
- **Regressions:** `TestRunOwnedBrowserLease` in `tests/tools/test_browser_use_cli.py`.
- **Retire when:** upstream owns equivalent per-run Harness/browser isolation, governed executable selection, no-download policy, random CDP allocation and complete teardown without requiring the declined backend.

### LP-008 — preserve an explicitly read-only Profile Skill root

- **File:** `hermes_cli/config_home.py`.
- **Invariant:** an existing Skill root with no write bits remains read-only across config loading; fresh or writable roots retain normal secure-directory handling.
- **Consumer:** Profiles whose official Skill copies are intentionally soft-locked against accidental writes.
- **Necessity:** the target normalizes a real Skill root to owner-writable mode.
- **Minimality:** one special case for `home / "skills"`; ownership repair remains and every other directory follows upstream.
- **Regressions:** `test_preserves_explicit_read_only_skills_root` and the fresh writable-root control.
- **Retire when:** upstream exposes and honors a profile-scoped read-only Skill-root policy.

### LP-009 — use the upstream neutral settlement path after a lost Cron fire claim

- **File:** `cron/scheduler.py`.
- **Invariant:** losing the durable fire claim before execution starts is settled through the target's owner/state-fenced unstarted-execution helper, not recorded as an ordinary failed execution.
- **Consumer:** frequent schedules that serialize long runs.
- **Necessity:** the target already supplies `settle_unstarted_execution` and uses it on adjacent pre-start failures, but the lost-claim branch still calls `finish_execution(... success=False)`.
- **Minimality:** change only that branch to call the existing upstream helper; do not carry the former local discard helper or its duplicate ledger implementation.
- **Regression:** `test_process_due_job_settles_lost_fire_claim_with_upstream_helper`.
- **Retire when:** upstream routes the lost-claim branch through equivalent neutral/fenced settlement or creates receipts only after claim success.

## 5. No-port decisions

### LP-002 — remote Gateway image URLs

- **Classification:** `UPSTREAM-ABSORBED`.
- **Decision:** do not port the old `gateway/run_turn_runner.py` partition hunk or its local-only regression. The exact target partitions remote URL images from local image paths at the native-vision boundary.
- **Re-entry trigger:** only new behavioral evidence showing that the exact active target again sends remote URLs through the local-path channel.

### FC-001 — old npm/Electron compatibility delta

- **Classification:** `FROZEN-TARGET-COMPATIBILITY`, now retired.
- **Decision:** do not mechanically port old package manifests, lockfiles or Desktop tests. Resolve and test the target's own dependency graph.
- **Re-entry trigger:** a current target-specific advisory or build incompatibility proved against the current target and separately authorized as a compatibility delta.

### LP-007 — Kanban timeout process-tree reaping

- **Classification:** `NO-CONSUMER`.
- **Decision:** retire the local descendant-reaper hunk and its implementation-only regression. No unfinished task uses `max_runtime_seconds`, and no enabled producer currently creates finite-runtime tasks; historical completed or archived rows are not consumers.
- **Re-entry trigger:** a current producer is authorized to create finite-runtime workers and untouched upstream behavior demonstrably leaks their descendants.

## 6. Verification contract

For every authorized target cycle:

1. Reconcile `git diff --name-status <authorized-base>...<candidate>` against section 3 in both directions.
2. Prove every active LP with red-on-untouched-target and green-on-candidate evidence at the stated invariant boundary.
3. Prove every no-port decision on untouched target behavior; do not retain an obsolete internal-shape test merely because it fails to apply.
4. Run touched-file tests, repository-owned full suites, required static checks, PM dependency checks, Profile/Gateway/Cron/Kanban checks and real consumer smokes.
5. Verify no installed official Skill changed, moved, disappeared or became shadowed.
6. Record changing hashes, counts, process identities, PM generation IDs and one-cycle exceptions only in the cycle receipt.

Any path outside section 3 is a release blocker until it is restored to the authorized base or separately classified and authorized.

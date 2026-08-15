# LOCAL_UPGRADE_RUNBOOK.md — Hermes production upgrade and runtime-conservation contract

**Authority:** release-blocking and equal in importance to `LOCAL_PATCHES.md`.
**Scope:** Hermes core, seven formal Profiles, all formal Cron jobs, all formal Kanban workflows, Python/Node/browser runtimes, Gateway/platform delivery, TTS/STT, Browser Use and Lightpanda.
**Current target:** Hermes v2026.8.13 / `f80f453ae0679347e38abc917c7f94f717bf96c5`.
**Production rollback identity at start of this upgrade:** `0c4c555d3ca25c5f9c0e5a79842cd760cefdc191`.

This is an executable operating contract, not a narrative. An upgrade is not complete because code was copied, tests passed, a process started, or a browser opened. It is complete only after the exact upstream identity, minimal local delta, unique runtimes, all Profile routes, all Cron/Kanban business outcomes, delivery side effects, cleanup, rollback materials and this record have been independently read back.

---

## 1. Non-negotiable invariants

### 1.1 Upstream-first source policy

1. Resolve an immutable upstream tag and full commit SHA. Never upgrade to floating `main`.
2. Start the candidate from untouched upstream.
3. Re-audit every entry in `LOCAL_PATCHES.md` against the new upstream implementation, sibling call paths, tests, official documentation and real production invariant.
4. Retire any patch absorbed upstream or replaceable by config, plugin, shared service asset, Cron/Kanban contract or deployment procedure.
5. Port only the smallest semantic hunk of patches proved indispensable. Copying an old whole file is forbidden.
6. No unlisted source difference may reach production.
7. Do not add a new local core feature to make an upgrade pass. If no authorized non-source solution exists, stop the upgrade and report the blocker.

### 1.2 One-environment policy

The closed production topology contains:

- **one canonical Python environment** for Hermes and Hermes-owned Python services;
- **one Node executable/toolchain** for Hermes-owned Node consumers;
- **one centrally governed browser-runtime root**, containing exactly one approved Chrome/Chromium binary and one approved Lightpanda binary when both engines are required;
- multiple browser processes are allowed only to provide the required Profile/task isolation, but every process must execute the approved central binary;
- Coder-owned website project environments are the only explicit Python exception.

A temporary next-generation Python environment is allowed only during the bounded build/validation window required for safe atomic cutover. It must be under `~/.hermes/tmp/<upgrade-id>/`, must not serve production, and must be removed after success or rollback. Extraction caches and downloaded package archives are not executable environments, but any cache containing a runnable `pyvenv.cfg` is treated as an environment and removed at closeout unless proven required.

### 1.3 No runtime download during automation or validation

Cron, Kanban, Gateway and test/validation processes must fail closed if an approved executable is unavailable or has the wrong identity. They must never invoke or fall back to:

- `uvx`, `pip`, `pip3`, `uv pip install`, `uv tool install`;
- `npx`, `npm install`, `pnpm install`, `yarn`;
- Browser Use installer/bootstrap commands;
- Playwright browser download/install commands;
- Agent Browser browser download/install commands;
- Lightpanda download/install commands;
- any lazy dependency installer.

Required environment guards include:

- `HERMES_SKIP_NODE_BOOTSTRAP=1`
- `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1`
- `UV_PYTHON_DOWNLOADS=never`
- Profile `security.allow_lazy_installs: false`

Runtime PATH for Cron/Kanban/browser workers must expose approved fixed launchers before generic user paths. A missing launcher, package mismatch, binary hash mismatch or unavailable CDP endpoint is an explicit failed run, never an installer fallback.

### 1.4 Browser allocation contract

- Interactive Profiles may use their assigned long-lived CDP endpoints.
- Every browser-using Cron or Kanban run receives a clean run-specific HOME/profile/user-data directory and a free loopback port allocated through the central lease mechanism.
- Port reuse by convention or arithmetic is forbidden. Allocation must avoid time-of-check/time-of-use races and record owner, PID/PGID, engine, port, start time and lease path.
- Chrome and Lightpanda are engines under one central runtime root; Browser Use is the official CLI/client in the one canonical Python environment and connects to the allocated CDP endpoint.
- Browser Use must follow the upstream Hermes integration contract: `browser-use` CLI plus `BU_CDP_URL` or `BU_CDP_WS`; production must not fall through to Hermes' `uvx browser-use` convenience path.
- Lightpanda is preferred where the workload passes its compatibility decision; Chrome is the explicit fallback for unsupported sites/features. Fallback uses the same central binary and lease contract, not an additional download.
- Cleanup must terminate the complete process group, release the lease, remove run-specific browser state, and prove no listener/PID remains.

### 1.5 Verification contract

Every release must verify:

- repository identity and allowed diff;
- Python, Node and browser executable identity;
- seven Profile message routes, models, fallbacks, vision, tools, STT/TTS and platform delivery;
- all formal Cron jobs by real data/business result, not `last_status=ok` alone;
- all formal Kanban workflows by card transitions, worker permissions, artifacts, publication/delivery and cleanup;
- no empty browser call, duplicated run, leaked lease, leaked session, modified Skill, lost credential scope, missing package or silent delivery failure.

---

## 2. Official-source rule before every command

Never guess a CLI flag. Before first use in an upgrade session:

1. Prefer the product's version-matched official documentation.
2. Read the exact upstream source that constructs or parses the command.
3. Use local `COMMAND --help` only when the product documents that help command as terminating; wrap every unfamiliar binary probe in a short external timeout and process-group cleanup.
4. Save the official URL/tag/source symbol and exact command in the execution record.
5. If documentation and binary behavior disagree, stop and inspect source/release notes; do not experiment against production.

Authoritative references used for this upgrade:

- Hermes browser feature: <https://hermes-agent.nousresearch.com/docs/user-guide/features/browser>
- Hermes source at immutable target commit, especially `tools/browser_use_cli.py` and browser configuration/resolution modules.
- Browser Use CLI: <https://docs.browser-use.com/open-source/browser-use-cli>
- Lightpanda serve command: <https://lightpanda.io/docs/run-locally/commands/serve>
- Lightpanda immutable release/README and checksum source for the selected binary.

### Mandatory safe-probe wrapper

An unfamiliar executable is never probed naked. The probe must have:

- a temporary private HOME;
- a random unoccupied loopback port if it starts a server;
- a short explicit timeout;
- a new process group/session;
- TERM followed by KILL of the whole group on timeout;
- listener, process and temporary-directory readback.

The 2026-08-15 Lightpanda incident proved why: an undocumented naked `lightpanda --help` invocation did not return, occupied the Agent tool call for about 30 minutes, and triggered Hermes' 1800-second idle recovery. Production services did not restart, but the upgrade execution round was lost. Never repeat this pattern.

---

## 3. Upgrade workspace and rollback layout

Use one upgrade id, for example `hermes-v0201-YYYYMMDD-HHMMSS`.

- Formal source checkout: `~/.hermes/hermes-agent`
- Temporary worktrees/builds/tests: `~/.hermes/tmp/<upgrade-id>/`
- Formal rollback and audit material: `~/.hermes/backups/<upgrade-id>/`
- Shared formal service assets: `~/.hermes/services/`
- Shared formal knowledge/data: `~/.hermes/kb/`
- Reusable non-executable caches: `~/.hermes/cache/`

Before changing anything, capture:

- exact Git HEAD, branch/detached state, tag, remotes and `git status --porcelain`;
- signed/immutable upstream target and full SHA;
- package distributions and interpreter identity of every discovered Python environment;
- Node executable realpath/version and every active Node consumer;
- browser executable realpaths, versions, hashes, caches, systemd units, listeners, PIDs and profile user-data roots;
- seven Profile config hashes plus redacted key-name inventory;
- all Gateway/browser/systemd unit text and active state;
- all Cron definitions, enabled state, next/last run, current leases and output roots;
- all Kanban boards, task counts/states, active workers, launchers, supervisors and formal artifacts;
- SQLite consistent backups for every Profile/session/Cron/Kanban database;
- filesystem permissions and hashes for all Skill roots.

Sensitive values are never printed. Record only key names and `[REDACTED]`.

Rollback materials must be read back before proceeding. A path existing is not proof of a usable backup.

---

## 4. Phase A — immutable upstream and local-patch retirement

1. Fetch only the intended upstream refs without switching production.
2. Verify tag-to-commit mapping and commit metadata.
3. Create a detached worktree from the exact target.
4. Compare the production tree to its own recorded upstream base, not blindly to the new tag.
5. For each LP:
   - identify exact old symbols and caller graph;
   - identify target symbols and all sibling paths;
   - read upstream tests and changelog;
   - run untouched-target reproducer in isolated `HERMES_HOME`;
   - test non-source alternatives;
   - set status in `LOCAL_PATCHES.md`;
   - if retained, transplant only the minimal semantic hunk and its regression.
6. Confirm allowed file surface with `git diff --name-status <target>`, `git diff --check`, and an explicit allowlist comparison.
7. Run focused regressions and the relevant full suites in an isolated test home with Node/browser downloads disabled.
8. Run an `env -i` clean-process CLI/import identity check.

For the v2026.8.13 upgrade, LP-010, LP-013, LP-014 and LP-016 were proven upstream-absorbed with 164 official-target tests passing. LP-007 and LP-008 were retired through deployment alternatives. The allowed runtime source surface was reduced to seven files listed in `LOCAL_PATCHES.md`.

---

## 5. Phase B — build the single canonical Python environment

### 5.1 Inventory first

Search the complete Hermes tree, including hidden and ignored directories, for every `pyvenv.cfg`. For each environment record:

- path and whether it is formal, temporary, cache or Coder website exception;
- Python executable realpath/version;
- installed distributions with exact versions;
- disk footprint;
- active process/service/MCP/Cron/Kanban consumer;
- package requirements/lock source;
- migration and smoke-test owner.

Do not delete an environment until every consumer has been remapped and tested against the canonical candidate.

### 5.2 Canonical location and interpreter

The final canonical environment is `~/.hermes/hermes-agent/venv`, using Python 3.11.15. All seven Profiles execute this same `hermes` entry point. Hermes-owned Python systemd services and MCP commands must also reference this interpreter unless they are explicitly documented Coder website exceptions.

### 5.3 Dependency conservation

1. Export exact distributions from every formal environment.
2. Normalize package names and build a conflict matrix.
3. Derive one combined, externally stored input manifest under `~/.hermes/services/python-runtime/`.
4. Resolve for CPython 3.11 on the actual Linux platform with network permitted only in this authorized build phase.
5. Produce a hash-locked manifest; do not modify upstream `pyproject.toml` or `uv.lock` for local service packages.
6. Build one temporary candidate environment with Python downloads disabled.
7. Synchronize from the hash lock; no unpinned residual package may survive.
8. Run `pip check` equivalent, import checks and real smoke tests for Hermes, PDF/OCR/Office, OSS, RAG, MiniMax MCP, PPT Master, STT/TTS, Browser Use and every other consumer.
9. If package constraints conflict, stop. Do not hide a second venv.
10. At cutover, archive the old environment as a non-executable compressed rollback artifact, atomically place the new canonical environment, remap consumers, verify, then remove every non-exempt executable environment.

### 5.4 Browser Use placement

Browser Use is installed in the canonical Hermes Python environment, not in a separate venv and not in system `/usr/bin/python3`. Its exact version and dependency hashes belong in the external canonical lock. The `browser-use` console script must resolve to `~/.hermes/hermes-agent/venv/bin/browser-use` for Gateway, Cron and Kanban contexts.

Before production use, verify from official source/documentation:

- installed distribution/version;
- console-script entry point;
- Hermes' exact command construction;
- CDP environment variable precedence;
- no executable path reaches `uvx` fallback;
- no Playwright/browser binary was downloaded during package synchronization.

---

## 6. Phase C — one Node toolchain

Inventory every `node` executable realpath, version manager, global package root, package manager and active consumer. Distinguish one runtime/toolchain from project-local dependency trees: multiple `node_modules` trees may be package layouts of one source workspace, but no second Node binary/version manager or hidden bootstrap runtime may remain.

- Select one approved Node executable and package manager already used by official Hermes.
- Point Hermes TUI/Desktop/build helpers, Agent Browser, LSP/MCP and formal scripts to that executable.
- Disable automatic Node bootstrap with `HERMES_SKIP_NODE_BOOTSTRAP=1` in production and validation.
- Build/install dependencies only during the authorized maintenance phase from lockfiles.
- Validate every Node consumer before removing duplicate runtimes/caches.
- At closeout prove all active Node processes resolve to the same approved executable.

Coder website dependency trees remain project assets, but they may not carry a second unmanaged Node runtime binary unless separately authorized.

---

## 7. Phase D — central browser runtime, Browser Use and Lightpanda

### 7.1 Formal runtime root

Use one formal root under `~/.hermes/services/browser-runtime/` with:

- `bin/` — fixed, checked launchers;
- `chrome/<version>/` — the single approved Chrome/Chromium executable;
- `lightpanda/<version>/` — the single approved Lightpanda executable;
- `manifests/` — source URL, release, size, SHA-256 and verification records;
- `leases/` — runtime ownership records;
- `runs/` — ephemeral per-run HOME/user-data/state, removed after use.

Browser Use itself remains in the canonical Python environment. There is no Browser Use venv inside this root.

### 7.2 Installation

- Read official release/install instructions before every download or command.
- Download each binary once into a `.part` file during the authorized maintenance phase.
- Verify expected size, cryptographic hash and executable format against the official release source.
- Atomically rename into the versioned formal location and update fixed launchers only after verification.
- Never run an installer that silently downloads Chromium.
- Search all relevant cache roots before and after installation; unexpected browser artifacts fail the phase and are removed before retry.

### 7.3 Engine decision

Lightpanda is preferred only for workloads that pass a real compatibility probe: navigation, JavaScript, required DOM/API behavior, authentication/session handling, downloads/uploads if used, and clean CDP closure. Chrome remains the documented fallback for unsupported workloads. The decision is per workload class, not based on one successful `example.com` navigation.

### 7.4 Fixed Profile browsers

Seven formal Profiles retain isolated long-lived CDP processes and user-data roots where their interactive behavior requires persistence. They all execute the one central Chrome/Lightpanda binary. Profile-to-port mapping is configuration and must be backed up and preserved; the crawler's actual fixed endpoint must agree across config, service unit and task rejection rules.

### 7.5 Random Cron/Kanban browsers

Every browser-using job/board launcher must:

1. run a preflight that validates fixed launcher, package version and binary hash without installation;
2. create a private run root and HOME;
3. allocate a loopback port through a race-safe lease;
4. start a new process group using the selected central engine;
5. wait for a bounded CDP readiness check;
6. export only that run's `BROWSER_CDP_URL`, `BU_CDP_URL` or `BU_CDP_WS` to the worker;
7. run the business task with installer paths unavailable and lazy installs disabled;
8. validate the actual business artifact/result;
9. terminate the process group, verify listener disappearance, release lease and delete ephemeral state;
10. report cleanup failure as task failure.

Retries must reuse the task's idempotency contract but receive a new clean browser allocation. Parallel runs may not share user-data directories or ports.

---

## 8. Phase E — Cron and Kanban adaptation

### 8.1 Cron

Inventory all formal jobs from each Profile's real Cron store. For every job record:

- id/name/Profile/enabled state/schedule/delivery destination;
- script, prompt, skills, workdir and toolsets;
- browser need, engine decision and fixed/random policy;
- idempotency/claim/heartbeat/timeout behavior;
- formal output and side-effect destinations;
- last real successful business artifact and validation method.

Patch shared Runner/launcher mechanisms by workload class, not individual data rows. Preserve disabled jobs as disabled. Before production cutover, shadow-run browser jobs with non-publishing outputs or exact idempotency protection, then inspect content and cleanup. After cutover, real production validation must inspect each job's actual returned data and formal artifact, not only scheduler status.

### 8.2 Kanban

Inventory every formal board, launcher, supervisor, worker Profile, card contract, skills, workspaces, publications and deliveries. Preserve:

- Profile-scoped worker toolsets and fan-out permission;
- Skill read-only mount boundary;
- worker session/routing environment scrub;
- blocked/ready lifecycle and idempotency keys;
- random isolated browser allocation;
- worker PID/PGID, timeout, requeue and cleanup;
- artifact and publication readback;
- no duplicate card, run or delivery.

A successful worker exit is not completion. Verify card state, required comments/evidence, formal artifacts, publication/delivery side effects and absence of residue.

---

## 9. Phase F — staged production cutover

Never switch all Profiles at once.

1. Confirm no active business run on the Profile to be switched.
2. Stop or drain only that Profile's Gateway/dispatcher using its existing user-owned service mechanism; do not use sudo for dionysos-owned units.
3. Switch shared source/canonical environment only at the controlled boundary defined in the cutover plan.
4. Start least business-critical/no-active-run Profile first.
5. Validate service process identity, imports, model route, fallback, tools, message reply, Browser Use/CDP, TTS/STT and delivery.
6. Continue with writer/coordinator and other Profiles only after the prior Profile is clean.
7. Switch crawler last because it owns the most business automation.
8. Preserve disabled jobs as disabled; do not trigger all recurring jobs blindly.
9. If any regression appears, stop expansion, roll back the affected boundary and diagnose from original logs/state.

Production services owned by user `dionysos` and managed by systemd `Restart=always` are restarted without sudo, using the verified existing service-control pattern. Root-owned services require separate authorization.

---

## 10. Real validation matrix

### 10.1 Repository and environment

- exact target commit and local release commit;
- clean worktree;
- diff name allowlist and `git diff --check`;
- one non-exempt `pyvenv.cfg` final result;
- every Python consumer points to canonical interpreter;
- every Node process points to approved Node executable;
- one Chrome binary hash and one Lightpanda binary hash under central root;
- no Playwright/Agent Browser/browser-use duplicate browser cache;
- no `uvx`/installer command reachable from automation.

### 10.2 Each Profile

For default, coordinator, crawler, coder, writer, supporter and auditor1:

- Gateway active with expected PID/start identity;
- correct HERMES_HOME isolation;
- primary model/provider and actual API response;
- fallback route under a controlled non-destructive failure test where feasible;
- vision/image path;
- Web and core tool visibility;
- Profile-specific toolsets and denied tools;
- Browser Use against assigned CDP;
- STT input and TTS output/delivery;
- platform message round-trip;
- credentials key visibility without exposing values;
- session persistence/finalization.

### 10.3 Each Cron/Kanban task

- actual source/data fetched or actual operation performed;
- result non-empty where the business contract requires data;
- structured output and formal artifact content inspected;
- delivery/publication read back at destination;
- idempotency and no duplicate execution;
- expected database transitions;
- no browser listener/process/run-root/lease/session residue;
- no Skill/config/source mutation;
- no download/cache growth outside approved build artifacts.

---

## 11. Rollback

Rollback is prepared before cutover and exercised at least at the command/path level in staging.

- Source rollback: immutable previous commit/worktree and archive.
- Python rollback: compressed non-executable archive of old canonical environment plus exact manifest; restore atomically, never run both in production.
- Config rollback: seven Profile files and systemd units with hashes and permissions.
- State rollback: consistent SQLite backups, with restore scope explicitly chosen to avoid losing legitimate post-cutover user messages or business writes.
- Browser rollback: previous launcher target and binary manifest; preserve user-data roots unless the failure is caused by corrupt profile state.
- Task rollback: restore Runner/launcher/supervisor/config contracts and cancel only upgrade-created shadow runs/leases.

A rollback must not overwrite new business data blindly. Choose source/runtime rollback first; database rollback only when schema/data corruption requires it and after reconciling post-backup writes.

---

## 12. Closeout and residue removal

Before declaring completion:

1. Re-run the complete validation matrix.
2. Confirm all temporary candidate venvs, test homes, worktrees, partial downloads and orphan caches are removed or retained only as documented non-executable evidence.
3. Confirm all temporary browser processes, listeners, process groups, leases, HOME/user-data directories and lock files are gone.
4. Confirm canonical package lock, browser manifests, `LOCAL_PATCHES.md` and this Runbook match the deployed bytes.
5. Confirm all Profile config/Skill permissions are restored; specially locked Skill trees are read-only again.
6. Confirm Git status is clean and no untracked test/report file is mixed into production source except the two formal governance documents.
7. Read back formal service status, Cron state, Kanban state, delivery/publication result and backup readability.
8. Record exact deployed commit, runtime versions/hashes, tests, task runs, deviations, incident lessons and rollback locations in this document.
9. Only then report completion.

---

## 13. 2026-08-15 upgrade execution log and lessons

### Verified target and staging

- Target locked to v2026.8.13 / `f80f453ae0679347e38abc917c7f94f717bf96c5`, not floating main.
- Production remained at `0c4c555d3ca25c5f9c0e5a79842cd760cefdc191` during staging.
- Initial broad local candidate was reduced after a second upstream-absorption review.
- Official-target LP-010/013/014/016 regressions: 164 passed.
- Prior candidate relevant regression suite and clean CLI checks passed, but those results must be rerun after the final reduced candidate and canonical dependency build.

### Browser staging error

- Browser Use 0.13.7 plus browser-harness 0.1.8 was initially placed in a separate temporary venv. Lightpanda 0.3.6 was placed as a temporary binary.
- This architecture was rejected because the final system must have one canonical Python environment; Browser Use will be merged into it and the temporary venv removed.
- A naked Lightpanda `--help` probe hung until Hermes idle recovery. The command had not been confirmed from official documentation and lacked the mandatory safe-probe wrapper. This was an execution-discipline failure, not a production Gateway crash. Seven Gateways remained active with no restart; no browser/runtime service was switched.

### Source-retirement corrections

- LP-007 update-banner cache patch retired.
- LP-008 local `pyproject.toml/uv.lock` production extra retired in favor of the external canonical environment lock.
- Qwen STT script removed from Hermes source and designated a shared formal service asset.
- Final intended runtime source surface is seven files; governance and local regression files are tracked separately.
- The first reduced-candidate retained-patch run exposed an incomplete LP-011 migration: DingTalk `_get_access_token` still depended exclusively on an already-connected Stream client, so proactive/independent `sampleAudio` could not acquire a token from the official `client_id/client_secret` configuration. The existing OAuth fallback was restored as the smallest semantic hunk. The next retained-patch run completed with 158 passed, 1 skipped and 0 failed; the skipped condition must be rechecked in the canonical environment.

### Open items before this document can be marked final

- complete package-conflict and consumer migration matrix for all non-exempt Python environments;
- establish and validate canonical combined hash lock;
- complete Node executable/toolchain inventory and consolidation;
- install/verify formal Lightpanda and Browser Use using official commands;
- complete Browser Use/Lightpanda decision matrix and random-port lease integration;
- adapt and shadow-test every browser Cron/Kanban path;
- rerun reduced-candidate tests;
- staged seven-Profile production cutover and real business validation;
- remove all redundant runtimes and temporary artifacts;
- append exact final commit, versions, hashes, run ids/results and closeout readback.

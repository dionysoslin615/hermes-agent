# LOCAL_UPGRADE_RUNBOOK.md — Hermes production upgrade and runtime-conservation contract

**Authority:** release-blocking and equal in importance to `LOCAL_PATCHES.md`.
**Scope:** Hermes core, seven formal Profiles, all formal Cron jobs, all formal Kanban workflows, Python/Node/browser runtimes, Gateway/platform delivery, TTS/STT, Browser Use and Lightpanda.
**Current target:** immutable upstream snapshot `18a76be124d7c16ed98b629a358b23fef76a7f46` (Hermes v0.21.0, 142 commits after formal tag v2026.8.31 / `29112bef099274229cadff79cdff7bf7b99c4b77`). It closes the full 4,629-commit gap from the previous fork main in one cycle.
**Production rollback identity at start of this upgrade:** `7329b3ad7b5f32653e5414d863ab587c2c472e4e` (v0.20.6 locally governed production).

This is an executable operating contract, not a narrative. An upgrade is not complete because code was copied, tests passed, a process started, or a browser opened. It is complete only after the exact upstream identity, minimal local delta, unique runtimes, all Profile routes, all Cron/Kanban business outcomes, delivery side effects, cleanup, rollback materials and this record have been independently read back.

### Current-cycle upstream and candidate evidence (2026-09-01)

- Upstream gap closed: 4,629 commits from the prior fork main to frozen upstream `18a76be124d7c16ed98b629a358b23fef76a7f46`; the post-v2026.8.31 unreleased slice is 142 commits across 351 files.
- Post-tag changes were reviewed by commit subject and file surface. The two overlaps with active local runtime files (`agent/agent_init.py`, `gateway/run.py`) retain distinct, still-unabsorbed production invariants after rebasing.
- Candidate identity: governed branch `upgrade/v0210-minimal-20260901`; five carried commits over the frozen upstream snapshot; 26 changed files, limited to the ledger allowlist.
- Regression evidence on the rebased snapshot: 72 of 73 changed/local test files passed on the host (1,810 passed, 37 skipped). The sole host-blocked file was the updater suite seeing real production Gateway PIDs; the same complete file passed in an isolated PID/network container (47 passed). Combined verified result: 1,857 passed, 37 skipped, zero code failures.
- Candidate runtime was rebuilt after testing from the hash-locked requirements contract: Python 3.11.15, Hermes 0.21.0, 262 compatible dependency packages plus the editable Hermes distribution; no lazy-test package is retained.

---

## 1. Non-negotiable invariants

### 1.1 Upstream-first source policy

1. Prefer the latest immutable formal tag. If the owner explicitly requests unreleased upstream fixes, fetch `origin/main` once, freeze its full commit SHA, record the post-tag delta and test that exact object; never build against a ref that moves during execution.
2. Start the candidate from untouched upstream.
3. Re-audit every entry in `LOCAL_PATCHES.md` against the new upstream implementation, sibling call paths, tests, official documentation and real production invariant.
4. Retire any patch absorbed upstream or replaceable by config, plugin, shared service asset, Cron/Kanban contract or deployment procedure.
5. Port only the smallest semantic hunk of patches proved indispensable. Copying an old whole file is forbidden.
6. No unlisted source difference may reach production.
7. Do not add a new local core feature to make an upgrade pass. If no authorized non-source solution exists, stop the upgrade and report the blocker.

### 1.2 One-environment policy

The closed production topology contains:

- **one canonical Python environment** for Hermes and Hermes-owned Python services;
- **one explicitly governed Browser Use tool environment** only when the upstream Browser Use CLI's exact dependency pins and stdin protocol cannot coexist with the canonical Hermes environment; this is a tool-isolation exception, not permission for Profile/service-local venvs;
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

- Interactive Profiles keep the Hermes official browser defaults: `browser.backend` unset, `browser.engine: auto`, and no persistent `browser.cdp_url`. When the governed Browser Use CLI is runnable, Hermes exposes the official `browser_exec` path; it falls back to the built-in browser stack only when that CLI is unavailable or the backend is explicitly disabled.
- Lightpanda is an installed optional engine of Hermes' built-in browser stack, not a transparent Browser Use backend. Built-in Lightpanda mode may fall back to Chrome for unsupported operations; Browser Use itself must not be described as automatically migrating a live Lightpanda session to Chrome.
- Every browser-using Cron or Kanban run receives a clean run-specific HOME/profile/user-data directory and an OS-assigned loopback CDP port (`--remote-debugging-port=0`) recorded in the task lease.
- Port reuse by convention, arithmetic, or pre-binding is forbidden. The Runner must read `DevToolsActivePort`, bind the endpoint to owner PID/PGID and profile identity, and reject reserved historical Profile ports 9222-9228.
- Chrome and Lightpanda are approved engines under one central runtime root. Browser Use is the official CLI/client in its governed tool environment and receives task-owned CDP routing through Hermes' supported `BROWSER_CDP_URL` → `BU_CDP_URL`/`BU_CDP_WS` bridge.
- Production PATH must resolve the fixed governed Browser Use launcher and must not fall through to Hermes' `uvx browser-use` convenience path.
- Cleanup must terminate the complete task process group, stop the matching Browser Harness daemon through its official reload entrypoint, release the lease, remove run-specific browser state, and prove no listener/PID remains.

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

Use one upgrade id, for example `hermes-v0210-YYYYMMDD-HHMMSS`.

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

LP-009, LP-010, LP-013, LP-014, LP-016, LP-020, LP-021 and CI-002 are upstream-absorbed on snapshot `18a76be124d7c16ed98b629a358b23fef76a7f46`. LP-007 and LP-008 remain retired through deployment alternatives. LP-017 and LP-018 remain only because untouched target behavior still fails the existing Browser Harness lifecycle and Kanban process-group invariants. LP-019 remains because the official CLI still overwrites an explicitly read-only Crawler `skills` root. LP-022 remains because untouched upstream records a normal lost race instead of a failed non-execution. The closed allowlist is nine runtime source files, three CI-001 files and eleven local regression files, all listed in `LOCAL_PATCHES.md`.

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
8. Run `pip check` equivalent, import checks and real smoke tests for Hermes, PDF/OCR/Office, OSS, RAG, MiniMax MCP, PPT Master, STT/TTS and every other canonical consumer.
9. Resolve Browser Use separately: first test every officially compatible CLI release in the canonical resolver and then run Hermes' real `browser_exec` stdin protocol. If dependencies resolve but the protocol does not execute, that version is incompatible. If the upstream-working version has irreconcilable exact pins, a separately hash-locked Browser Use tool environment is allowed only after explicit owner approval and must be the sole non-Coder exception.
10. At cutover, rename the old environment only into the bounded transaction rollback area, atomically place the new canonical environment, remap consumers and verify. After final acceptance delete the old environment and candidate residue completely; retain only text manifests, hashes and receipts.

### 5.4 Browser Use placement

The preferred state is canonical co-installation, but it is accepted only after both dependency resolution and Hermes' real stdin-CLI protocol pass. For v2026.8.13, Browser Use 0.11.13 resolved with Hermes but did not execute `browser_exec` code; Browser Use 0.13.7 plus Browser Harness 0.1.8 executed the official protocol but carried exact dependency pins incompatible with Hermes 0.20.1. The owner therefore approved one separately governed tool environment at `~/.hermes/services/browser-runtime/python/browser-use/0.13.7/venv`.

The exception must satisfy all of the following:

- exact input and hash lock beside the environment;
- fixed launcher `~/.hermes/services/browser-runtime/bin/browser-use`;
- systemd/automation preflight verifies the launcher, versions and hashes before work;
- production PATH resolves that launcher before `uvx`; missing/mismatched runtime fails closed;
- the tool environment contains no Profile/service business packages and is never cloned per Profile/task;
- interactive Profiles use Hermes' official default Browser Use resolution with Profile-scoped workspaces and no persistent CDP override; task Runners connect Browser Use only to the current run-owned random CDP endpoint; the tool environment itself stores no shared browser user-data profile;
- any future Browser Use release is retried in the canonical resolver and this exception is retired immediately if dependency and protocol tests both pass.

Before production use, verify from official source/documentation and real execution:

- installed Browser Use/Browser Harness distributions and console entry point;
- Hermes `browser_exec` can execute `page_info()` rather than returning help text;
- `BU_CDP_URL` / `BU_CDP_WS` routing reaches the intended Profile/task browser;
- seven Profile HERMES_HOME values yield seven distinct workspaces;
- no executable path reaches `uvx` fallback and no browser download occurs; and
- CLI/helper behavior required by upstream `tools/browser_use_cli.py` is present.

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
- `python/browser-use/<version>/` — the single approved Browser Use tool environment only when the governed exception is active;
- `manifests/` — source URL, release, size, SHA-256 and verification records;
- `leases/` — runtime ownership records;
- `runs/` — ephemeral per-run HOME/user-data/state, removed after use.

Browser Use belongs in this root only when the dependency-and-protocol proof activates the single governed tool-environment exception. It is never installed per Profile or per task.

### 7.2 Installation

- Read official release/install instructions before every download or command.
- Download each binary once into a `.part` file during the authorized maintenance phase.
- Verify expected size, cryptographic hash and executable format against the official release source.
- Atomically rename into the versioned formal location and update fixed launchers only after verification.
- Never run an installer that silently downloads Chromium.
- Search all relevant cache roots before and after installation; unexpected browser artifacts fail the phase and are removed before retry.

### 7.3 Engine decision

The Profile default is the official Browser Use driver with `browser.engine: auto`; official docs define `auto` as agent-browser's current Chrome default. Lightpanda is installed but is not the default engine: it is selected only by the explicit official setting `browser.engine: lightpanda` on the built-in agent-browser path. Only that built-in Lightpanda path provides transparent Chrome retry for eligible failures and unsupported actions; Browser Use is not a Lightpanda-to-Chrome migration layer.

### 7.4 Official default Profile browsers

Seven formal Profiles keep `browser.backend` unset, `browser.engine: auto`, and no persistent `browser.cdp_url`. The governed Browser Use CLI is resolved from the central runtime root, so Hermes follows its official default tool-selection path. Profile-fixed CDP services and 9222-9228 mappings are local drift and must remain disabled/absent after migration.

### 7.5 Random Cron/Kanban browsers

Every browser-using job/board launcher must:

1. run a preflight that validates fixed launcher, package version and binary hash without installation;
2. create a private run root and HOME;
3. request an OS-assigned loopback port with `--remote-debugging-port=0`, then read and validate `DevToolsActivePort` before marking the lease ready;
4. start a new process group using the selected central engine;
5. wait for a bounded CDP readiness check;
6. export only that run's `BROWSER_CDP_URL` to the Hermes worker and let the official Browser Use adapter translate it to `BU_CDP_URL` or `BU_CDP_WS`;
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

The shared source and canonical environment are switched once, while Gateway restart and acceptance are staged by Profile.

1. Confirm no active Cron/Kanban business run and preserve every enabled/paused state, especially paused Tender Intelligence.
2. Ask all seven existing Gateways to drain, then stop the seven user-owned systemd units from an external maintenance process; never stop the running control session from inside itself.
3. Switch the shared source and canonical environment atomically at their existing official paths; no new launcher or alternate production path is introduced.
4. Start the least business-critical/no-active-run Profile first.
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
- official-default Browser Use resolution, no persistent CDP override, and a real navigation smoke where the Profile exposes browser tools;
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

- Source rollback during the transaction: immutable previous commit plus backed-up dirty patch; after acceptance retain the Git identity and patch evidence, not a second checkout.
- Python rollback during the transaction: renamed old canonical environment plus exact manifest; restore atomically and never run both in production. Delete the old environment after acceptance.
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

- Browser Use 0.13.7 plus Browser Harness 0.1.8 was initially placed in a temporary tool venv; Lightpanda 0.3.6 was placed as a temporary binary.
- Canonical co-installation was then tested rather than assumed. Browser Use 0.11.13 resolved with Hermes but returned CLI help instead of executing Hermes stdin code. The upstream-working 0.13.7/0.1.8 pair had irreconcilable exact pins. After explicit owner approval, one hash-locked governed Browser Use tool environment was promoted under the central browser-runtime root; all Profile/task copies remain forbidden.
- A naked Lightpanda `--help` probe hung until Hermes idle recovery. The command had not been confirmed from official documentation and lacked the mandatory safe-probe wrapper. This was an execution-discipline failure, not a production Gateway crash. Seven Gateways remained active with no restart; no browser/runtime service was switched.

### Source-retirement corrections

- LP-007 update-banner cache patch retired.
- LP-008 local `pyproject.toml/uv.lock` production extra retired in favor of the external canonical environment lock.
- Qwen STT script removed from Hermes source and designated a shared formal service asset.
- Final intended runtime source surface is nine files; governance and ten local regression files are tracked separately.
- The first reduced-candidate retained-patch run exposed an incomplete LP-011 migration: DingTalk `_get_access_token` still depended exclusively on an already-connected Stream client, so proactive/independent `sampleAudio` could not acquire a token from the official `client_id/client_secret` configuration. The existing OAuth fallback was restored as the smallest semantic hunk. The next retained-patch run completed with 158 passed, 1 skipped and 0 failed; the skipped condition must be rechecked in the canonical environment.
- Final permission readback exposed that a one-time `chmod 0500` was not a durable Crawler Skill lock: every `hermes` CLI import called `ensure_hermes_home()` and forced `HERMES_HOME/skills` back to 0700. `LP-019` now preserves an already explicit all-write-bits-cleared Skill-root mode while retaining the upstream 0700 default for new or writable Skill roots and every other Hermes state directory. The exact failing `hermes kanban boards list --json` path was traced through `os.chmod`, then reproduced after the fix with the root remaining 0500 and all 184 Crawler Skill directories/`SKILL.md` objects non-writable; 83 full config/permission tests and the wider 150-test config/Cron/Kanban sandbox set passed.

### Environment, configuration and service conservation completed before cutover

- Whole-Hermes path census covered 102,409 directories and 551,581 files (about 85.2 GB). It found 17 `pyvenv.cfg` environments, 188 `node_modules` directories and 113 runtime-executable candidates. A second pass streamed 23.97 GB of large files; unreadable large files were limited to Coder-project MySQL binlogs under the explicit exception. No active Hermes config/script/Skill/service file was unreadable.
- Formal configuration registry covered 6,620 objects including all named-Profile Skills. Fifty legacy-path references were identified; immutable historical evidence was classified separately and all active references entered the cutover tree.
- Canonical Python 3.11.15 environment resolved and installed 245 compatible packages with a hash lock. `pip check` passed. Hermes local/upstream regression set passed 286 tests with one Windows-only skip. Real DOCX/XLSX/PPTX/PDF creation/readback passed; CUDA reported `torch 2.12.0+cu126` on NVIDIA L20.
- Canonical MCP protocol smokes passed for OSS (including real `oss_health`), RAG (17 tools and four green SQLite/Qdrant collections with no missing points), and MiniMax. Seven Profile configs contained 17 MCP bindings; all 17 initialized and listed tools using each Profile's actual config and interpolation syntax.
- Lightpanda 0.3.6 official release hash `e438c0ad44e0f6916c14cf13beb003512c60438d8fd200738d2e596e73f652d6` matched and the official `serve --host 127.0.0.1 --port <random>` command listened and cleaned its process group, port and temporary HOME. Chrome 151.0.7922.34 hash `0b20b130e7edd9dd51873be867761295fe0cfad490c2b9a64f95bd3cfc08fa71` was copied byte-for-byte into the central root.
- Browser Use 0.13.7 / Browser Harness 0.1.8 initially executed against seven fixed Profile CDP endpoints, but that was later rejected as a non-official deployment architecture. The seven persistent `browser.cdp_url` overrides were removed; all Profile browser settings now resolve to Hermes defaults (`backend` unset, `engine: auto`), and the seven fixed CDP services were disabled.
- All 16 Cron definitions were inventoried: 15 enabled at entry and `tender-intelligence` intentionally disabled. Before cutover, the 15 enabled jobs were paused through the official CLI. The active IPO DLOM runner received SIGTERM, exited cleanly and retained audit 632 at the resumable `round2_running` checkpoint with an expired lease and reviewer `-15` receipt; the database was not hand-edited.
- Formal Kanban boards contained no active workers at the cutover gate. Internal Journal had 86 done/archived cards; MA Detail had 295 cards with no running/claimed task.
- A shared Crawler browser contract governs the central Chrome entry, rejects historical fixed ports 9222-9228 and enforces the no-download environment. The obsolete shared-fixed-browser assertion was repaired to create its own unrelated sentinel, and the crawler browser suite passed 68/68. Five distinct Runner browser implementations started concurrently on OS-assigned ports, Tender's formal smoke passed, and every port/profile/process cleaned. Generic Kanban and competitor-info then exercised LP-017 through their formal worker/`call_agent` entries: the final Kanban card completed with `KANBAN_RUN_OWNED_OK`, central Browser Use 0.13.7, random port 37139, PAC, all four no-download guards, no uvx and zero cache delta; competitor-info returned `COMPETITOR_CRON_BROWSER_OK` and removed its isolated runtime. A deliberately short Kanban task also reproduced upstream timeout orphaning before LP-018; its residue was stopped and removed, Chrome was rebound to the worker PGID, and timeout group termination gained a dedicated regression.
- Final `policy-maintenance` recovery exposed a second LP-017 lifecycle branch that the initial run-owned-Chrome smokes did not cover. The Runner already owned a random-port Chrome and passed its CDP endpoint into an unattended Agent, so Hermes correctly avoided launching another Chrome; however, that same early return also skipped assignment of a task-private Browser Harness `BH_RUNTIME_DIR`/`BU_NAME`. Browser Use started a Harness daemon that called `setsid`, escaped the Agent PGID, held the Bubblewrap stdout/stderr pipes open after the Agent exited, and left the Runner blocked in `communicate(timeout=14400)` with its Chrome still alive. System-call tracing and pipe-inode ownership proved the chain. The first repair assigned a private runtime but incorrectly placed it below the deep Profile home; Browser Harness documents that callers must keep `BH_RUNTIME_DIR` short because AF_UNIX paths are limited to 104 bytes on macOS and 108 on Linux, and the production policy run returned `AF_UNIX path too long`. LP-017 now treats an unattended external/prestarted CDP as ownership of the Harness daemon even though Chrome remains Runner-owned, allocates `/tmp/hbu_<pid>` plus a private name, and stops the daemon through the official `--reload` cleanup at Agent exit. A real external-CDP smoke attached to Runner-owned Chrome on random port 45539, read the live page, removed the short runtime, and left no new daemon, socket, port or profile residue; 90 focused Browser Use tests, 460 browser wildcard tests with 7 deselected, and 60 Kanban core/tool tests passed. Final production policy completion is recorded separately only after the formal replay reaches closed state.

### Official browser architecture correction and Profile identity validation

- Official docs and locked source established the actual selection chain: Browser Use is the default when its CLI is runnable; the built-in stack is the fallback; Lightpanda belongs to the built-in stack and may fall back to Chrome for unsupported built-in operations. Browser Use is not a Lightpanda-to-Chrome migration layer.
- Interactive browser selection remains identical to locked upstream: Browser Use by default, built-in stack as fallback, `backend` unset, `engine: auto`, no persistent CDP. Only unattended Cron/Kanban execution differs through LP-017 because untouched upstream cannot launch a task-private headless Chrome, falls through to uvx when the scrubbed worker PATH lacks the CLI, and can hang on daemon-inherited pipes.
- All seven configs migrated to schema 34 and their effective browser values match locked upstream defaults. Six named Profile fresh-session smokes loaded their identities and the new official-document-first highest rule.
- Coder initially failed its identity smoke because it alone explicitly selected the optional `codex_app_server` runtime, whose locked implementation did not carry Hermes SOUL context into the Codex thread. Official docs define this runtime as opt-in and `auto` as default; the override was removed with `hermes -p coder config unset model.openai_runtime`, the coder Gateway was reloaded, and a fresh session correctly returned `金步摇` and the highest rule without any source change.
- A requested Lightpanda-default change was exercised before service reload and failed its first real navigation: current Hermes passes `AGENT_BROWSER_ARGS` to agent-browser for Chrome sandbox/PAC behavior, while agent-browser rejects any custom Chrome args with `--engine lightpanda`. The production PAC is a whitelist policy (listed financial/government domains use `106.15.11.192:8888`; all other traffic is direct), not a single global proxy URL, so converting it to `AGENT_BROWSER_PROXY` would change routing semantics. The attempted config was rolled back before any Gateway loaded it, the temporary run root was removed, and all seven Profiles returned to `backend` unset / `engine: auto` / no persistent CDP. The owner chose to retain official Browser Use/Chrome defaults, keep the verified Lightpanda binary installed but inactive, make no source patch, and retest only after upstream supports per-engine launch arguments plus PAC-equivalent routing.
- Final browser regressions passed 500/500 in Hermes and 68/68 in Crawler. Kanban core passed 25/25 and the new group-kill regression. Running every Kanban test module in one pytest process exposed 14 pre-existing order-dependent isolation failures; each exact node passed in a fresh pytest process, so no production delta was added to mask cross-module fixture leakage.

### Final closeout completed on 2026-08-15

- The locked deployment remains Hermes v0.20.1 at upstream baseline `f80f453ae0679347e38abc917c7f94f717bf96c5`; the last locally governed runtime-code commit before the subsequent documentation-only commits is `4f30d8cdafbdbf19dcbdbe4ef3c7c8b7c6ae8b17`. The earlier `0019ecaeafa41c416211089a054c5079f1435f68` commit established unattended browser isolation, and `4f30d8cdafbdbf19dcbdbe4ef3c7c8b7c6ae8b17` completed the remaining runtime-regression fixes. Floating `origin/main` was not followed.
- One canonical Python 3.11.15 environment, one approved Node v26.7.0 executable, one governed Chrome 151.0.7922.34 tree and one hash-locked Browser Use 0.13.7 / Browser Harness 0.1.8 environment remain. Lightpanda 0.3.6 is installed and verified but is not configured as the default browser.
- Seven Profile configurations are schema 34 with independent Profile homes, upstream-default browser selection and 17 MCP bindings. All seven Gateway units reached active/running after cutover; final service/process readback is repeated after the documentation commit.
- All 16 Cron definitions are conserved: 15 enabled and `tender-intelligence` intentionally paused. The final upgrade-impact matrix is `services/hermes-upgrade-history/v0.20.1-20260815/upgrade-impact-final-20260815.json`. `policy-maintenance` was replayed through its formal Runner after LP-017's AF_UNIX short-path correction, reached `closeout_v2` contract 2.4.10 at 19:49, then passed the shared Cron execution body with latest status `ok`; no task-private Chrome, Harness daemon, socket, profile or reserved port remained. `ma-info`'s pre-fix orphan Harness daemon was proven unused and removed.
- Post-upgrade Kanban diagnostics found no platform/runtime regression. A later 2026-08-15 Internal Journal business run completed T2 without spawning its contract-required T3 child; this is a workflow-chain defect, not evidence that the upgraded Kanban Worker is unavailable. MA Detail has four historical records whose underlying runs/blocked transitions predate this upgrade; no post-upgrade Worker startup, interpreter, permission, Browser Use or cleanup error exists. No business card was modified during this classification.
- Final regressions include Browser Use 90/90, browser wildcard 460 passed with 7 deselected, managed Browserbase/Modal 7/7, Kanban core/tool 60/60, config 76/76, policy Runner 30/30 and Crawler browser-contract 4/4. The restored pre-existing competitor formatting contract passes 64/64; the out-of-scope redline delta was removed and is not part of the upgrade.
- Upgrade cleanup removed the temporary scripts, v0.20/v0.20.1 rollback snapshots, desktop/Profile smoke homes, source/test caches and stale retired-browser Singleton links by exact allowlist. The compact formal history and cleanup receipt are under `services/hermes-upgrade-history/v0.20.1-20260815/`; no business data, Cron definition, Kanban card, active runtime environment or browser durable profile store was deleted.
- The source tree is committed only after final diff/test review. The resulting Git identity and clean-tree proof are recorded by the final closeout command output and the upgrade-impact artifact rather than self-referencing an unknowable commit inside its own commit.

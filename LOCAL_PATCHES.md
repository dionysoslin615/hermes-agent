# LOCAL_PATCHES.md — production semantic delta ledger

**Authority:** release-blocking, equal in force to `LOCAL_UPGRADE_RUNBOOK.md`.
**Upstream baseline:** Hermes Agent v2026.8.27 / `5fc308a70719a83cccdbba4c0e39c23f5a8239d5` (v0.20.6).
**Policy:** upstream-first. A local semantic delta survives only when current upstream lacks an equivalent, configuration/plugin/shared-service/Cron/Kanban alternatives cannot preserve the same production invariant, and a real regression test proves deletion would break an existing function. Every future upgrade must attempt retirement again before porting code.

## Allowed source-difference surface

Only these runtime files may differ from the upstream baseline:

1. `cron/scheduler.py`
2. `cron/executions.py`
3. `gateway/run.py`
4. `agent/agent_init.py`
5. `tools/kanban_tools.py`
6. `hermes_cli/kanban_db.py`
7. `tools/browser_use_cli.py`
8. `plugins/platforms/dingtalk/adapter.py`
9. `hermes_cli/config.py`
10. `agent/conversation_compression.py`
11. `agent/context_compressor.py`

Governance/CI-only files may also differ:

- `AGENTS.md`
- `LOCAL_PATCHES.md`
- `LOCAL_UPGRADE_RUNBOOK.md`
- `scripts/sandbox/proxy.py`, `scripts/sandbox/stage2-run.sh` and `scripts/dev-sandbox.sh` (CI-001; never imported by production runtime)
- `scripts/install.sh` (CI-002 installer-only; not imported by production runtime)

Local regression files may differ only when they directly exercise an ACTIVE-SOURCE invariant:

- `tests/cron/test_execution_ledger.py`
- `tests/cron/test_run_one_job.py`
- `tests/cron/test_cron_script.py`
- `tests/gateway/test_dingtalk.py`
- `tests/hermes_cli/test_kanban_core_functionality.py`
- `tests/hermes_cli/test_kanban_skill_readonly_sandbox.py`
- `tests/hermes_cli/test_kanban_worker_spawn_toolsets.py`
- `tests/hermes_cli/test_config.py`
- `tests/tools/test_browser_use_cli.py`
- `tests/tools/test_cloud_voice_integration.py` (DingTalk-only despite the historical filename)
- `tests/tools/test_kanban_tools.py`
- `tests/test_install_sh_node_deps_failure.py` (CI-002 installer regression)
- `tests/run_agent/test_in_place_compaction.py` (LP-020 marker-stamp contract)
- `tests/agent/test_lean_single_aux_call.py` (LP-021 single-aux-call contract)

Any other Git difference is a release blocker until either removed or entered here after the complete necessity procedure.

## Required status vocabulary

- **ACTIVE-SOURCE:** still requires a local source delta.
- **UPSTREAM-ABSORBED:** upstream now owns the invariant; local implementation must not be ported.
- **EXTERNALIZED:** invariant is preserved outside core source by configuration, a shared formal asset, or an automation contract.
- **DEPLOYMENT-CONTRACT:** no source delta; must be checked during every cutover.

---

## LP-001 — unlimited Cron pre-run script duration

- **Status:** ACTIVE-SOURCE.
- **File / symbols:** `cron/scheduler.py::_get_script_timeout`, `_run_job_script`.
- **Production invariant:** `cron.script_timeout_seconds: 0` means no script deadline. Long-running DLOM and similar stateful runners must not be killed at one hour.
- **Upstream v0.20.6:** accepts only values greater than zero and otherwise returns 3600 seconds; its execution loop also assumes every timeout is numeric.
- **Why alternatives fail:** selecting an arbitrary larger number changes unlimited semantics; splitting the runner changes checkpoint, lease, delivery, and idempotency behavior.
- **Minimal delta:** translate exact numeric zero from module override, environment bridge, or config into `None`; when it is `None`, skip deadline arithmetic while retaining cancellation polling and all positive-timeout behavior.
- **Regression evidence:** after the v0.20.6 cutover, `ipo-dlom` exposed the incomplete first port as `TypeError: unsupported operand type(s) for +: 'float' and 'NoneType'`; the corrected scheduler/script suite passed 68 tests with 1 skipped.
- **Retirement trigger:** upstream supports an explicit unlimited setting through both configuration parsing and script execution, or all formal long runners are redesigned and proven bounded without changing business semantics.

## LP-002 — Gateway remote image URL routing

- **Status:** ACTIVE-SOURCE.
- **File / symbol:** `gateway/run.py`, pending-native-image call to `build_native_content_parts`.
- **Production invariant:** HTTP(S) image references from messaging platforms reach a vision-capable model as native `image_url` parts.
- **Upstream v0.20.6:** the image builder supports `image_urls`, but this Gateway call site passes every reference as a local path; URL references therefore enter local filesystem checks and are skipped.
- **Minimal delta:** partition local paths and HTTP(S) URLs at the call site and pass them to the two official parameters.
- **Retirement trigger:** upstream Gateway performs the same partition or normalizes every platform image into a verified local cache before this call.

## LP-003 — authenticated DingTalk inbound media normalization

- **Status:** ACTIVE-SOURCE.
- **File / symbols:** `plugins/platforms/dingtalk/adapter.py`, inbound media extraction, `downloadCode` resolution, authenticated download/cache, recognition-text selection and STT fallback.
- **Production invariant:** DingTalk image, audio and document messages become readable local paths; voice messages use platform recognition text when non-empty and otherwise run configured Hermes STT.
- **Upstream v0.20.6:** extracts some references and resolves `downloadCode` to a temporary URL, but command STT rejects non-local paths before execution and document/image consumers require readable local bytes.
- **Minimal delta:** keep latest upstream adapter and add only authenticated byte acquisition, type-safe cache, dedupe and recognition/STT fallback.
- **Retirement trigger:** upstream DingTalk emits local cached media with equivalent auth, size/type limits and voice fallback.

## LP-004 — Profile-scoped Kanban worker fan-out

- **Status:** ACTIVE-SOURCE.
- **Files / symbols:** `agent/agent_init.py` worker guidance gate; `tools/kanban_tools.py::_worker_can_create_tasks`, create/link checks.
- **Production invariant:** dispatched workers always retain their own task lifecycle tools; only profiles configured with `kanban.worker_can_create_tasks: true` may create/link follow-up cards. Normal orchestrator chats must not receive worker-only prompt guidance.
- **Real consumers:** coordinator and auditor1 may fan out; crawler, coder, writer and supporter are restricted. The Internal Journal contract still uses worker-created continuation cards.
- **Why toolset removal fails:** removing the Kanban toolset also removes `show`, `heartbeat`, `comment`, `complete` and `block`, so the worker cannot satisfy its protocol.
- **Minimal delta:** default true for upstream compatibility; hide and reject only create/link for explicitly false worker profiles; require `HERMES_KANBAN_TASK` before injecting worker guidance.
- **Retirement trigger:** upstream has per-profile/per-worker allow and deny controls that preserve lifecycle tools.

## LP-005 — read-only Skill trees for Kanban workers

- **Status:** ACTIVE-SOURCE.
- **File / symbols:** `hermes_cli/kanban_db.py::_kanban_worker_skill_roots`, `_sandbox_kanban_worker_skills_read_only`, `_default_spawn`.
- **Production invariant:** every dispatched Kanban worker can read but cannot modify any default, Profile, external or symlink-target Skill tree.
- **Why chmod fails:** worker and skill owner are the same Linux user; a worker can reverse owner permission bits. Current formal Skill roots are owner-writable outside task-specific lock windows.
- **Minimal delta:** Linux bubblewrap around only the worker process; host filesystem otherwise unchanged; all visible Skill roots and symlink targets `--ro-bind`; missing boundary fails closed.
- **Retirement trigger:** upstream offers an equivalent mount/sandbox policy or workers run under a separately constrained identity proven unable to write every Skill target.

## LP-006 — Kanban worker routing-environment scrub

- **Status:** ACTIVE-SOURCE.
- **File / symbol:** `hermes_cli/kanban_db.py::_default_spawn`.
- **Production invariant:** detached workers never inherit interactive Gateway/session routing identity.
- **Upstream v0.20.6:** removes only keys currently present in `_VAR_MAP`.
- **Minimal delta:** additionally remove all `HERMES_SESSION_*`, all `HERMES_GATEWAY_*`, `HERMES_UI_SESSION_ID`, and `_HERMES_GATEWAY` before adding worker-owned variables.
- **Retirement trigger:** upstream owns a prefix-complete sanitizer applied to dispatcher children.

## LP-007 — update-banner cache invalidation

- **Status:** EXTERNALIZED / retired from source.
- **Former file:** `hermes_cli/banner.py`.
- **Replacement:** upgrade Runbook verifies exact Git identity and clears stale update-check state during controlled cutover; all Gateways start as new processes.
- **Reason for retirement:** cosmetic update indication does not carry business execution, and source modification is not necessary for functional parity.

## LP-008 — local production dependency extra

- **Status:** EXTERNALIZED / retired from source.
- **Former files:** `pyproject.toml`, `uv.lock`.
- **Replacement:** one external, hash-locked canonical-environment manifest plus before/after distribution conservation and real consumer smoke tests, documented in `LOCAL_UPGRADE_RUNBOOK.md`. Node-based production tools follow the same rule: WeStock is fixed at `~/.hermes/services/westock-data/1.0.4/package`, records npm source/SHA1/SHA512 integrity in `runtime-manifest.json`, and is invoked only through `~/.local/bin/westock-data-clawhub`; task-time `npx` installation is forbidden.
- **Consumer audit:** the deterministic `ipo-dlom-two-pass-runner.py` directly invokes the fixed launcher and its focused WeStock tests pass. Current `ipo-crawl` does **not** consume WeStock: its isolated `HERMES_HOME` contains only the `ipo-crawl` Skill, its Agent is launched with `--skills ipo-crawl`, and neither the live Runner nor IPO Crawl artifacts contain a WeStock command. Do not add or preserve a false IPO Crawl dependency during upgrades.
- **Validation:** fixed launcher output is byte-identical to direct execution of the pinned package entry for the same query; live search and `kline --fq hfq` pass after removal of the old `_npx` working copy.
- **Reason for retirement:** machine-specific PDF and production service packages must not modify upstream package metadata.

## LP-009 — terminal state for quiet one-shot sessions

- **Status:** UPSTREAM-ABSORBED.
- **Production invariant:** `hermes chat -Q` ends the final continuation tip in `state.db` before releasing the active lease. Cron and Kanban use this path heavily.
- **Upstream v0.20.6 evidence:** `_flush_one_shot_session_store` persists terminal state through `end_session` while preserving the remaining cleanup path.
- **Rule:** the old `cli.py` hunk and its local regression are not ported.

## LP-010 — MCP RPC serialization

- **Status:** UPSTREAM-ABSORBED.
- **Upstream evidence:** per-server `_rpc_lock`; tool calls, list tools/resources/prompts and reads serialize; active RPC suppresses recycle paths.
- **Validation:** official-target MCP regression included in the 164-test absorbed-patch suite.
- **Rule:** never port the old local implementation.

## LP-011 — DingTalk local file/audio delivery and final status

- **Status:** ACTIVE-SOURCE.
- **File / symbols:** `plugins/platforms/dingtalk/adapter.py`, OpenAPI token/media upload, staff recipient resolution, `sampleFile`, `sampleAudio`, `sendStatus`.
- **Production invariant:** a locally generated document/audio result is delivered to the actual DingTalk user and a final status is sent; API success is validated from response body, not HTTP status alone.
- **Upstream v0.20.6:** local document send explicitly returns unsupported; no complete sampleFile/sampleAudio/sendStatus path.
- **Minimal delta:** reuse upstream adapter/session identity; add only DingTalk OpenAPI calls, Stream-token reuse with official OAuth fallback for proactive/independent sends, cache and expiry bounds, real recipient validation and truthful `SendResult`.
- **Retirement trigger:** upstream provides equivalent local document/audio delivery, proactive OAuth token acquisition and status confirmation.

## LP-012 — Qwen STT and native voice delivery

- **Status:** mixed: DingTalk audio ACTIVE-SOURCE; Qwen command EXTERNALIZED; upstream-covered platform paths retired.
- **Source retained:** only DingTalk `sampleAudio` behavior already accounted under LP-011.
- **Formal external asset:** `~/.hermes/services/voice/aliyun_qwen_stt.py`, executed by the single canonical Python interpreter and referenced uniformly by all seven Profile configs.
- **Retired portions:** MiniMax TTS and Telegram routing now use upstream behavior; no legacy Telegram downgrade patch is ported.
- **Retirement trigger:** upstream DingTalk gains equivalent sampleAudio; Qwen STT may move to an upstream/provider plugin only after real parity tests.

## LP-013 — binary detection and UTF-8 clamp

- **Status:** UPSTREAM-ABSORBED.
- **Upstream evidence:** raw-byte sample detection and bounded UTF-8 line transport are present.
- **Validation:** official-target file-operation regressions included in the 164-test suite.
- **Rule:** never port the old local implementation.

## LP-014 — lifecycle-guard binary/NUL safety

- **Status:** UPSTREAM-ABSORBED.
- **Upstream evidence:** bounded regular-file reads, binary sniff, and `OSError`/`ValueError` handling for embedded NUL paths.
- **Validation:** official-target lifecycle regressions included in the 164-test suite. The old production guard was independently reproduced crashing on a test path before cutover.
- **Rule:** never port the old local implementation.

## LP-015 — Profile route conservation

- **Status:** DEPLOYMENT-CONTRACT.
- **Invariant:** every formal Profile retains its configured model, provider, fallback chain, reasoning, vision, Web, TTS/STT, toolsets, credentials visibility and platform delivery behavior.
- **Validation:** hash/redacted-key baseline before changes; independent clean-process smoke; real message/TTS/tool/browser checks after cutover; no secret value appears in reports.
- **Rule:** source tests or config-file equality alone are insufficient.

## LP-016 — sticky initial blocked state

- **Status:** UPSTREAM-ABSORBED.
- **Upstream v0.20.6 evidence:** `create_task` transactionally preserves an initial blocked state and its sticky reason.
- **Production-consumer audit:** no formal Cron, Kanban contract, Runner or reporting path requires a second synthetic `blocked` history event at creation time.
- **Rule:** the uncommitted local event hunk and its dedicated regression are not ported.

## LP-017 — unattended Browser Use run-owned Chrome lease

- **Status:** ACTIVE-SOURCE.
- **File / symbols:** `tools/browser_use_cli.py`, unattended-worker detection, governed CLI resolution, run-owned Chrome lease and daemon-safe CLI execution.
- **Production invariant:** every Cron/Kanban worker that calls `browser_exec` owns a task-private Browser Harness runtime and daemon. Without a pre-launched CDP it also receives one task-private central Chrome on an OS-assigned loopback port, with PAC routing, four no-download guards and complete daemon/process/profile cleanup. Interactive Browser Use keeps upstream defaults.
- **Upstream v0.20.6:** Browser Harness expects an already running Chrome; when the CLI is not on the worker's scrubbed PATH, `_find_cli` falls through to `uvx browser-use`; `subprocess.run(capture_output=True)` can wait forever when the persistent Harness daemon inherits its pipes. Even with an operator-owned CDP, Browser Use starts a detached Harness daemon in the shared default runtime unless the worker receives an explicit `BH_RUNTIME_DIR`/`BU_NAME` lifecycle.
- **Why alternatives fail:** persistent Profile CDP services violate task isolation; `BH_CHROME_PATH` launches a shared/default Chrome profile and cannot express the existing PAC/task lease; per-Runner duplication leaves generic Kanban and future Cron consumers uncovered; changing HOME breaks Profile credentials and provider state.
- **Minimal delta:** activate only for `HERMES_KANBAN_TASK` or explicit `HERMES_RUN_OWNED_BROWSER=1`; always prefer an existing CDP but still assign it a private `BH_RUNTIME_DIR`/`BU_NAME`; resolve the one shared governed Browser Use launcher and prohibit unattended uvx fallback; only when no CDP exists, start central Chrome with `--remote-debugging-port=0` and bridge to `BU_CDP_URL`; place the Harness AF_UNIX runtime at `/tmp/hbu_<pid>` so the complete `bu.sock` path stays below the documented 104-byte budget; use temp files instead of stdout/stderr pipes; clean by atexit and parent-death binding.
- **Validation:** Browser Use regressions 90/90 and the complete `test_browser*.py` set 460 passed with 7 deselected; a real Kanban card completed with title/text/url readback, managed CLI, no uvx, random port 37139, PAC, four guards and zero cache delta. A real policy Cron exposed the missing external-CDP case: its escaped daemon held sandbox stdio for over an hour, and the first repair still placed `BH_RUNTIME_DIR` below the deep Profile home, causing `AF_UNIX path too long`. The corrected external-CDP smoke attached to Runner-owned Chrome on random port 45539, read the live page, removed `/tmp/hbu_<pid>`, and left no new Harness daemon, socket, port or profile residue.
- **Retirement trigger:** upstream Browser Use natively launches a task/profile-private headless Chrome with random CDP, supports governed executable/PAC routing, fails closed instead of uvx in unattended sessions, and owns complete daemon/browser cleanup.

## LP-018 — Kanban timeout terminates the worker process group

- **Status:** ACTIVE-SOURCE.
- **File / symbol:** `hermes_cli/kanban_db.py::enforce_max_runtime`.
- **Production invariant:** max-runtime enforcement terminates the entire worker session, including Bubblewrap children, Browser Harness daemon and task-owned Chrome, before releasing the claim or recording timeout.
- **Upstream v0.20.6:** `_default_spawn` uses `start_new_session=True`, but timeout enforcement signals only the recorded leader PID and treats leader exit as complete; live descendants and browser listeners remain orphaned.
- **Minimal delta:** on POSIX, verify `os.getpgid(pid) == pid`, signal that PGID, poll group existence, then escalate the same group to SIGKILL; preserve the injected single-PID signal hook and Windows behavior.
- **Validation:** dedicated group-liveness regression plus Kanban core 25/25; real timeout reproduced the orphan before the patch, and a task-owned Chrome was then proven to share the worker PGID. Manual test residue was removed before proceeding.
- **Retirement trigger:** upstream timeout/reclaim owns process-tree or cgroup termination and proves no descendants/listeners survive.

## LP-019 — preserve an explicitly read-only Profile skills root

- **Status:** ACTIVE-SOURCE.
- **File / symbol:** `hermes_cli/config.py::_secure_skills_dir`, called by `ensure_hermes_home`.
- **Production invariant:** a Profile skills root whose write bits were deliberately removed remains read-only across every Gateway, Cron, Kanban and CLI startup; fresh and writable skill roots retain the official `0700` default.
- **Upstream v0.20.6:** every first `load_config()` in a process calls `ensure_hermes_home`, which unconditionally applies `_secure_dir(..., 0700)` to `HERMES_HOME/skills`. A direct syscall trace proved that even read-only `hermes kanban boards list --json` changed crawler's explicitly locked root from `0500` back to `0700`.
- **Why alternatives fail:** `HERMES_HOME_MODE=0500` also locks Cron, sessions, logs and all other state; `HERMES_SKIP_CHMOD` does not affect `_secure_dir`; same-user chmod/timers race every new process; the Kanban Bubblewrap boundary does not cover Profile Cron, Gateway or ordinary CLI sessions.
- **Minimal delta:** when the existing skills root has no owner/group/other write bit, preserve that stricter mode and only repair configured ownership; otherwise call the unchanged upstream `_secure_dir` path.
- **Validation:** focused regression 5/5; complete config and file-permission modules 83/83; real crawler reproduction remained `0500` after an official Kanban CLI startup, with 184 checked skill directories/`SKILL.md` files and zero writable entries.
- **Retirement trigger:** upstream supports a Profile-scoped read-only skills-root policy that survives `ensure_hermes_home`, or the crawler Profile is moved to a separately constrained identity/mount boundary proven to cover Gateway, Cron, Kanban and CLI execution.

## LP-020 — in-place compaction commit stamps the persistence marker

- **Status:** ACTIVE-SOURCE.
- **File / symbols:** `agent/conversation_compression.py` in-place commit branch, immediately after `archive_and_compact(...)` sets `split_status = "in_place_committed"`.
- **Production invariant:** after an in-place (`compression.in_place: true`) batch compaction commits, every compacted dict carries `_DB_PERSISTED_MARKER`, so the append-only flush (`_persist_session` → `_flush_messages_to_session_db_unlocked`) never re-INSERTs the post-compaction transcript. Live context size must monotonically shrink across a committed compaction.
- **Failure evidence (2026-08-30, coordinator session `20260830_121928_330881ba`, auditor1 session `20260829_205018_6a336f35`):** `compress()` returns marker-swept COPIES (`_strip_persistence_markers`); the in-place commit path — unlike `ContextCompressor._sync_micro_compact_to_db` — never re-stamped them. The same tool-result batch was durable-written twice with byte-identical timestamps at commit, again at turn finalize, and a fourth time mid-next-turn (state.db rows 529239/529304/529371/529692 sharing tool_call_id `call_NqMk...`; auditor1 held 41 duplicate groups, ~3.0 MB redundant). Live sets grew ~58K → ~512K tokens and every later preflight compression timed out at the 600 s ceiling against a session that no longer fit the model window, producing repeated "Context compression made no progress" failures on both profiles.
- **Why alternatives fail:** upstream v0.20.6 + 552 commits were checked (`git log HEAD..origin/main`): rotation-side dedupe (#94996 salvage) and compressor attempt-ownership races are fixed, but the in-place path still lacks the post-commit stamp; no config/plugin alternative can restore the marker (it is in-memory state on the returned dicts, required by the flush's skip contract).
- **Minimal delta:** 13 lines inside the `if in_place:` branch — import `_DB_PERSISTED_MARKER`, stamp every dict in `compressed`. No other file or behavior touched.
- **Validation:** `tests/run_agent/test_in_place_compaction.py` — `TestInPlaceCommitStampsPersistenceMarkers.test_committed_dicts_carry_marker` and `.test_no_duplicate_rows_after_post_commit_persist` (reproduces the production commit→persist sequence; asserts one active row per compacted message and zero duplicate contents). 13/13 pass with the fix; reverting ONLY the source hunk makes the new tests fail (verified via `git stash`), proving regression coverage.
- **Retirement trigger:** upstream stamps the persistence marker on the compacted set in the in-place commit path (or returns marker-preserving dicts with an equivalent flush-skip guarantee). Re-check on every upgrade against `agent/conversation_compression.py` and `agent/context_compressor.py::_sync_micro_compact_to_db`. origin/main already contains `1f2bd9e763` (#98450); retire this entry only on a freeze-tag upgrade that includes that commit, not when merely backporting LP-021.

## LP-021 — lean compaction makes exactly one auxiliary request

- **Status:** ACTIVE-SOURCE (temporary backport of upstream `4f22543509` / #96603 onto the v0.20.6 production tree).
- **File / symbols:** `agent/context_compressor.py` — remove `_build_chunk_digests` and sibling digest helpers; fold the session log into the single `_generate_summary` request; even-sample oversized lean input via `_sample_summary_input`.
- **Production invariant:** a lean-mode compaction attempt issues exactly one auxiliary `call_llm`. The digest loop (up to 28 sequential DeepSeek calls) is gone. Live context size after a committed compaction is unchanged by this patch (that remains LP-020).
- **Failure evidence (2026-08-31):** after LP-020, coordinator still issued four `Auxiliary compression: using deepseek` calls in ~7 minutes (10:51–10:58) and a 337 s micro-compaction. Local HEAD still contained `_build_chunk_digests`; default `compression.tail_mode: lean`.
- **Why not a full upgrade:** origin/main is ~603 commits ahead; cherry-picking `4f22543509` onto this tree conflicts. Runbook forbids copying whole files. This is the smallest semantic hunk.
- **Minimal delta:** digest-loop removal, session-log section in the summary template, even-sampling for lean input, drop `_lean_pristine_tools` snapshot. LP-020 is untouched. Docs/evals from the upstream commit are not ported.
- **Validation:** `tests/agent/test_lean_single_aux_call.py` 8/8 and LP-020 marker tests 2/2 pass (`10 passed in 2.80s`).
- **Retirement trigger:** freeze-tag upgrade that already contains `4f22543509`. Do not keep this hunk when merging that tag.

## LP-022 — Cron overlap suppression is not a failed execution

- **Status:** ACTIVE-SOURCE.
- **Files / symbols:** `cron/executions.py::discard_unstarted_execution`; `cron/scheduler.py::tick._process_job`.
- **Production invariant:** when a built-in tick loses the durable `fire_claim` to an already-running, manual, or external fire, the job has not started and must not be recorded as `failed`, increment failure streaks, create incidents, or pollute business completion reporting.
- **Failure evidence (2026-09-01):** `ipo-dlom` runs every minute and correctly serializes long projects, but 44 overlap attempts from 04:55 through 05:38 were recorded as `failed` with `Fire claim lost; execution was not started.`; all 44 had `started_at IS NULL` and represented zero failed projects.
- **Why alternatives fail:** marking overlap as completed corrupts success counts; adding a new terminal status widens the public schema and every consumer; filtering only reports leaves `cron doctor`, incidents, and failure streaks wrong; slowing the DLOM schedule creates avoidable queue idle time.
- **Minimal delta:** retain the pre-dispatch claimed placeholder for crash recovery, then transactionally delete only the current process's exact `claimed`, never-started row after confirmed claim loss. Any ownership/state mismatch remains an immutable diagnostic failure.
- **Validation:** focused execution-ledger and tick regressions prove normal overlap leaves no history row, while running/completed/foreign or otherwise unsafe rows cannot be deleted; complete relevant Cron suites must remain green.
- **Retirement trigger:** upstream records only successfully fire-claimed built-in attempts, or introduces a first-class neutral skipped/overlap terminal state excluded from failures, incidents, streaks, and business completion counts.

## DEPLOYMENT-CONTRACT DC-007 — compression total ceiling 1800 s on every profile

- **Class:** deployment contract; no source delta (config-only).
- **Files:** every profile `config.yaml` (`compression.context_total_ceiling_seconds: 1800`); coordinator, auditor1, coder, crawler, writer, supporter and default set 2026-08-30, read back verified.
- **Invariant:** a legitimately slow large-context compression is allowed to finish instead of being amputated at the default 600 s ceiling. Production: a 232,847-token summary completed server-side at 823.9 s but was abandoned at 600 s; 470K/525K-token real-payload probes completed in 45.3 s/12.8 s while in-session attempts died at 600 s. 1800 s covers the observed worst case with margin while keeping runaway attempts bounded.
- **Upgrade check:** confirm the key survives the merge in every profile config; if upstream changes the default or the semantics of `compression.context_total_ceiling_seconds` / `hygiene_total_ceiling_seconds`, re-derive this contract.

---

## Upgrade-time mandatory retirement procedure

For every LP on every upgrade:

1. Resolve and verify the exact upstream tag and commit; never compare only version strings.
2. Read the upstream symbol, all sibling call paths, related tests, changelog and official documentation.
3. Reproduce the production invariant against untouched upstream in an isolated `HERMES_HOME` with network/runtime downloads disabled.
4. Test alternatives in order: upstream behavior; config; plugin; shared formal asset; Cron/Kanban contract; only then source.
5. If an alternative preserves the real end-to-end result, retire the source patch.
6. If source remains necessary, port the smallest semantic hunk onto untouched upstream; never copy whole old files.
7. Run syntax, focused regression, full relevant suite, clean-process import/CLI checks, then real Profile/Cron/Kanban validation.
8. Record evidence, new retirement trigger and exact allowed file list here.

The authoritative operational sequence, rollback rules and environment/browser conservation checks are in `LOCAL_UPGRADE_RUNBOOK.md`.

## CI-001 — trusted transparent non-fixture HTTPS in Install & Update E2E

- **Class:** CI-only; not production runtime source.
- **Files:** `scripts/sandbox/proxy.py`, `scripts/sandbox/stage2-run.sh`, `scripts/dev-sandbox.sh`.
- **Invariant:** the real installer/update matrix must not fail because the fixture proxy performs a redundant second TLS handshake or replaces the public CA set with only the fixture CA.
- **Upstream/fork evidence:** both upstream and the fork failed first with CONNECT relay `SSLEOFError`; after transparent tunnelling, uv correctly exposed `UnknownIssuer` because `SSL_CERT_FILE` contained only the fixture root.
- **Minimal delta:** keep MITM only for fixture hosts, use bidirectional transparent CONNECT tunnelling for non-fixture hosts, build one CA bundle containing both the fixture CA and the runner's public roots, and point curl/OpenSSL/Git/Node at that same bundle inside stage 2.
- **Validation:** local bidirectional CONNECT integration smoke, Python/shell validation, fork run `33237541031`, and production-commit fork run `33245992470`: update and installer routes both passed from release `v2026.5.16` to the synchronized branch.
- **Retirement trigger:** upstream adopts an equivalent tunnel or replaces the sandbox proxy.

## CI-002 — scope curl-installer npm dependencies away from Desktop

- **Class:** installer/CI-only; not production runtime source.
- **Files:** `scripts/install.sh`, `tests/test_install_sh_node_deps_failure.py`.
- **Invariant:** the CLI installer installs the root toolchain plus `ui-tui` and `web`, but does not traverse `apps/desktop`, download Electron, or build desktop-native modules.
- **Upstream evidence:** root `package.json` is now a workspace monorepo and already declares the intended scoped scripts; `hermes update` likewise names only `ui-tui`, `web`, and `--include-workspace-root`, while `install.sh` still ran an unscoped root `npm install`. The installer E2E therefore failed after the code update reached the workspace-era manifest.
- **Minimal delta:** make the installer use the same explicit workspace scope and standard npm flags as the updater; preserve the existing TUI stage and failure handling.
- **Validation:** focused installer/updater regressions `6 passed`; fork run `33237541031` passed both update and installer routes at commit `0fc5b11ce3a05daf03a447c17a82b1caecfc1b91`.
- **Retirement trigger:** upstream scopes the root installer identically or removes the root Node dependency stage.

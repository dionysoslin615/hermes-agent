# LOCAL_PATCHES.md — production semantic delta ledger

**Authority:** release-blocking, equal in force to `LOCAL_UPGRADE_RUNBOOK.md`.
**Upstream baseline:** fixed authorized Hermes target `6ec05205a943cf813bd56c3c79d64bcf922dac67`. Newer remote observations do not change this baseline without new owner authorization.
**Policy:** upstream-first. A local semantic delta survives only when current upstream lacks an equivalent, configuration/plugin/shared-service/Cron/Kanban alternatives cannot preserve the same production invariant, and a real regression test proves deletion would break an existing function. Every future upgrade must attempt retirement again before porting code.

## Allowed source-difference surface

Only these runtime files may differ from the upstream baseline:

1. `cron/executions.py`
2. `cron/scheduler.py`
3. `cron/scheduler_script.py`
4. `gateway/run_turn_runner.py`
5. `hermes_cli/config_home.py`
6. `hermes_cli/kanban_db_dispatch.py`
7. `tools/browser_use_cli.py`
8. `tools/kanban_tools.py`

Governance/CI-only files may also differ:

- `LOCAL_PATCHES.md`
- `LOCAL_UPGRADE_RUNBOOK.md`

Local regression files may differ only when they directly exercise an ACTIVE-SOURCE invariant:

- `tests/cron/test_execution_ledger.py`
- `tests/cron/test_run_one_job.py`
- `tests/cron/test_cron_script.py`
- `tests/gateway/test_remote_native_image_url.py`
- `tests/hermes_cli/test_kanban_core_functionality.py`
- `tests/hermes_cli/test_kanban_skill_readonly_sandbox.py`
- `tests/hermes_cli/test_config.py`
- `tests/tools/test_browser_use_cli.py`
- `tests/tools/test_kanban_tools.py`

Any other Git difference is a release blocker until either removed or entered here after the complete necessity procedure.

## Required status vocabulary

- **ACTIVE-SOURCE:** still requires a local source delta.
- **UPSTREAM-ABSORBED:** upstream now owns the invariant; local implementation must not be ported.
- **EXTERNALIZED:** invariant is preserved outside core source by configuration, a shared formal asset, or an automation contract.
- **DEPLOYMENT-CONTRACT:** no source delta; must be checked during every cutover.

---

## LP-001 — unlimited Cron pre-run script duration

- **Status:** ACTIVE-SOURCE.
- **File / symbol:** `cron/scheduler_script.py::_get_script_timeout`, with scheduler wiring in `cron/scheduler.py`.
- **Production invariant:** `cron.script_timeout_seconds: 0` means no `subprocess.run` timeout. Long-running DLOM and similar stateful runners must not be killed at one hour.
- **Untouched v0.21.1 target:** accepts only values greater than zero and otherwise returns 3600 seconds.
- **Why alternatives fail:** selecting an arbitrary larger number changes unlimited semantics; splitting the runner changes checkpoint, lease, delivery, and idempotency behavior.
- **Minimal delta:** translate exact numeric zero from module override, environment bridge, or config into `None`; preserve all positive and invalid-value upstream behavior.
- **Retirement trigger:** upstream supports an explicit unlimited setting or all formal long runners are redesigned and proven bounded without changing business semantics.

## LP-002 — Gateway remote image URL routing

- **Status:** ACTIVE-SOURCE.
- **File / symbol:** `gateway/run_turn_runner.py`, pending-native-image call to `build_native_content_parts`.
- **Production invariant:** HTTP(S) image references from messaging platforms reach a vision-capable model as native `image_url` parts.
- **Untouched v0.21.1 target:** the image builder supports `image_urls`, but this Gateway call site passes every reference as a local path; URL references therefore enter local filesystem checks and are skipped.
- **Minimal delta:** partition local paths and HTTP(S) URLs at the call site and pass them to the two official parameters.
- **Retirement trigger:** upstream Gateway performs the same partition or normalizes every platform image into a verified local cache before this call.

## LP-003 — authenticated DingTalk inbound media normalization

- **Status:** EXTERNALIZED / retired from source.
- **Former files:** `plugins/platforms/dingtalk/adapter.py`, `plugins/platforms/dingtalk/inbound.py`, and the local DingTalk regression additions.
- **Replacement:** this deployment has no live DingTalk Profile, credential, Home Channel, Cron sender, Kanban notifier, or connected adapter. The upstream DingTalk plugin remains intact and available but is not activated.
- **Rule:** do not resurrect the former local media-normalization delta automatically. A future DingTalk consumer must qualify the then-current upstream plugin and obtain fresh authorization for any new local semantic delta.

## LP-004 — Profile-scoped Kanban worker fan-out

- **Status:** ACTIVE-SOURCE.
- **Files / symbols:** `tools/kanban_tools.py::_worker_can_create_tasks`, create/link visibility and handler checks. The fixed target already limits worker guidance through `owned_kanban_task()` in `agent/agent_init.py` / `agent/system_prompt.py`; no local delta remains in those files.
- **Production invariant:** dispatched workers always retain their own task lifecycle tools; only profiles configured with `kanban.worker_can_create_tasks: true` may create/link follow-up cards. Normal orchestrator chats must not receive worker-only prompt guidance.
- **Real consumers:** coordinator and auditor1 may fan out; crawler, coder, writer and supporter are restricted. The Internal Journal contract still uses worker-created continuation cards.
- **Why toolset removal fails:** removing the Kanban toolset also removes `show`, `heartbeat`, `comment`, `complete` and `block`, so the worker cannot satisfy its protocol.
- **Minimal delta:** default true for upstream compatibility; hide and reject only create/link for explicitly false worker profiles; require `HERMES_KANBAN_TASK` before injecting worker guidance.
- **Retirement trigger:** upstream has per-profile/per-worker allow and deny controls that preserve lifecycle tools.

## LP-005 — read-only Skill trees for Kanban workers

- **Status:** ACTIVE-SOURCE.
- **File / symbols:** `hermes_cli/kanban_db_dispatch.py::_kanban_worker_skill_roots`, `_sandbox_kanban_worker_skills_read_only`, `_default_spawn`; `hermes_cli/kanban_db.py` retains only the compatibility-facing exports required by current callers.
- **Production invariant:** every dispatched Kanban worker can read but cannot modify any default, Profile, external or symlink-target Skill tree.
- **Why chmod fails:** worker and skill owner are the same Linux user; a worker can reverse owner permission bits. Current formal Skill roots are owner-writable outside task-specific lock windows.
- **Minimal delta:** Linux bubblewrap around only the worker process; host filesystem otherwise unchanged; all visible Skill roots and symlink targets `--ro-bind`; missing boundary fails closed.
- **Retirement trigger:** upstream offers an equivalent mount/sandbox policy or workers run under a separately constrained identity proven unable to write every Skill target.

## LP-006 — Kanban worker routing-environment scrub

- **Status:** ACTIVE-SOURCE.
- **File / symbol:** `hermes_cli/kanban_db_dispatch.py::_default_spawn`.
- **Production invariant:** detached workers never inherit interactive Gateway/session routing identity.
- **Untouched v0.21.1 target:** removes only keys currently present in `_VAR_MAP`.
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
- **Replacement:** Hermes PM owns one canonical `+all` environment. Machine-specific production dependencies live in the external plugin manifest `~/.hermes/plugins/local-runtime-extras/pyproject.toml` and are installed through `hermes pm install --extra all`, never by changing upstream metadata or mutating the venv. Production scripts call `~/.hermes/services/python-runtime/python`, which resolves the current PM environment from the selected install's `facts.json`; they never embed an environment ID. The JZ RAG service keeps its own declaration/lock under `~/.hermes/services/rag/` and pins `FlagEmbedding==1.4.2`, the first upstream release carrying the Transformers 5 tokenizer compatibility required by the deployed reranker. A Hermes upgrade must conserve that compatible pin (or adopt a later officially fixed release only after the same real `rerank=true` consumer smokes) and must not regress to 1.4.0. Node-based production tools follow the same rule: WeStock is fixed at `~/.hermes/services/westock-data/1.0.4/package`, records npm source/SHA1/SHA512 integrity in `runtime-manifest.json`, and is invoked only through `~/.local/bin/westock-data-clawhub`; task-time `npx` installation is forbidden.
- **Consumer audit:** the deterministic `ipo-dlom-two-pass-runner.py` directly invokes the fixed launcher and its focused WeStock tests pass. Current `ipo-crawl` does **not** consume WeStock: its isolated `HERMES_HOME` contains only the `ipo-crawl` Skill, its Agent is launched with `--skills ipo-crawl`, and neither the live Runner nor IPO Crawl artifacts contain a WeStock command. Do not add or preserve a false IPO Crawl dependency during upgrades.
- **Validation:** the JZ RAG service must pass dependency integrity, tokenizer compatibility, unchanged model/cache identity, and real `rerank=true` searches for every enabled RAG collection; the DLOM consumer must additionally prove the real company-bound IPO tool call and receipt path. The fixed WeStock launcher output is byte-identical to direct execution of the pinned package entry for the same query; live search and `kline --fq hfq` pass after removal of the old `_npx` working copy.
- **Reason for retirement:** machine-specific PDF and production service packages must not modify upstream package metadata.

## LP-009 — terminal state for quiet one-shot sessions

- **Status:** UPSTREAM-ABSORBED.
- **Production invariant:** `hermes chat -Q` ends the final continuation tip in `state.db` before releasing the active lease. Cron and Kanban use this path heavily.
- **Upstream v0.20.6 evidence:** `_flush_one_shot_session_store` persists terminal state through `end_session` while preserving the remaining cleanup path.
- **Rule:** the old `cli.py` hunk and its local regression are not ported.

## LP-010 — MCP RPC serialization

- **Status:** UPSTREAM-ABSORBED.
- **Upstream evidence:** per-server `_rpc_lock`; tool calls, list tools/resources/prompts and reads serialize; active RPC suppresses recycle paths.
- **Validation:** current-target MCP regressions passed in the affected suite.
- **Rule:** never port the old local implementation.

## LP-011 — DingTalk local file/audio delivery and final status

- **Status:** EXTERNALIZED / retired from source.
- **Former file:** `plugins/platforms/dingtalk/adapter.py` and its local delivery regressions.
- **Replacement:** all production Profiles use Telegram or another non-DingTalk route; no active workflow consumes DingTalk `sampleFile`, `sampleAudio`, proactive OAuth delivery, or `sendStatus` behavior. The exact upstream DingTalk implementation is retained without local augmentation.
- **Rule:** future DingTalk activation starts from current upstream behavior and requires fresh end-to-end qualification; the retired source hunk is not replayed by default.

## LP-012 — Qwen STT and native voice delivery

- **Status:** EXTERNALIZED.
- **Formal external asset:** `~/.hermes/services/voice/aliyun_qwen_stt.py`, executed by the single canonical Python interpreter and referenced uniformly by all seven Profile configs.
- **Source retirement:** the former DingTalk `sampleAudio` portion retired with LP-011; MiniMax TTS and Telegram voice routing use upstream behavior; no legacy Telegram downgrade or DingTalk audio patch is retained.
- **Retirement trigger:** Qwen STT may move to an upstream/provider plugin only after real parity tests.

## LP-013 — binary detection and UTF-8 clamp

- **Status:** UPSTREAM-ABSORBED.
- **Upstream evidence:** raw-byte sample detection and bounded UTF-8 line transport are present.
- **Validation:** current-target file-operation regressions passed in the affected suite.
- **Rule:** never port the old local implementation.

## LP-014 — lifecycle-guard binary/NUL safety

- **Status:** UPSTREAM-ABSORBED.
- **Upstream evidence:** bounded regular-file reads, binary sniff, and `OSError`/`ValueError` handling for embedded NUL paths.
- **Validation:** current-target lifecycle regressions passed in the affected suite. The old production guard was independently reproduced crashing on a test path before cutover.
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
- **Untouched v0.21.1 target:** Browser Harness expects an already running Chrome; when the CLI is not on the worker's scrubbed PATH, `_find_cli` falls through to `uvx browser-use`; `subprocess.run(capture_output=True)` can wait forever when the persistent Harness daemon inherits its pipes. Even with an operator-owned CDP, Browser Use starts a detached Harness daemon in the shared default runtime unless the worker receives an explicit `BH_RUNTIME_DIR`/`BU_NAME` lifecycle.
- **Why alternatives fail:** persistent Profile CDP services violate task isolation; `BH_CHROME_PATH` launches a shared/default Chrome profile and cannot express the existing PAC/task lease; per-Runner duplication leaves generic Kanban and future Cron consumers uncovered; changing HOME breaks Profile credentials and provider state.
- **Minimal delta:** activate only for `HERMES_KANBAN_TASK` or explicit `HERMES_RUN_OWNED_BROWSER=1`; always prefer an existing CDP but still assign it a private `BH_RUNTIME_DIR`/`BU_NAME`; resolve the one shared governed Browser Use launcher and prohibit unattended uvx fallback; only when no CDP exists, start central Chrome with `--remote-debugging-port=0` and bridge to `BU_CDP_URL`; place the Harness AF_UNIX runtime at `/tmp/hbu_<pid>` so the complete `bu.sock` path stays below the documented 104-byte budget; use temp files instead of stdout/stderr pipes; clean by atexit and parent-death binding.
- **Validation:** Browser Use regressions 90/90 and the complete `test_browser*.py` set 460 passed with 7 deselected; a real Kanban card completed with title/text/url readback, managed CLI, no uvx, random port 37139, PAC, four guards and zero cache delta. A real policy Cron exposed the missing external-CDP case: its escaped daemon held sandbox stdio for over an hour, and the first repair still placed `BH_RUNTIME_DIR` below the deep Profile home, causing `AF_UNIX path too long`. The corrected external-CDP smoke attached to Runner-owned Chrome on random port 45539, read the live page, removed `/tmp/hbu_<pid>`, and left no new Harness daemon, socket, port or profile residue.
- **Retirement trigger:** upstream Browser Use natively launches a task/profile-private headless Chrome with random CDP, supports governed executable/PAC routing, fails closed instead of uvx in unattended sessions, and owns complete daemon/browser cleanup.

## LP-018 — Kanban timeout terminates the worker process group

- **Status:** ACTIVE-SOURCE.
- **File / symbol:** `hermes_cli/kanban_db_dispatch.py::enforce_max_runtime`.
- **Production invariant:** max-runtime enforcement terminates the entire worker session, including Bubblewrap children, Browser Harness daemon and task-owned Chrome, before releasing the claim or recording timeout.
- **Untouched v0.21.1 target:** `_default_spawn` uses `start_new_session=True`, but timeout enforcement signals only the recorded leader PID and treats leader exit as complete; live descendants and browser listeners remain orphaned.
- **Minimal delta:** on POSIX, verify `os.getpgid(pid) == pid`, signal that PGID, poll group existence, then escalate the same group to SIGKILL; preserve the injected single-PID signal hook and Windows behavior.
- **Validation:** dedicated group-liveness regression plus Kanban core 25/25; real timeout reproduced the orphan before the patch, and a task-owned Chrome was then proven to share the worker PGID. Manual test residue was removed before proceeding.
- **Retirement trigger:** upstream timeout/reclaim owns process-tree or cgroup termination and proves no descendants/listeners survive.

## LP-019 — preserve an explicitly read-only Profile skills root

- **Status:** ACTIVE-SOURCE.
- **File / symbol:** `hermes_cli/config_home.py::_secure_skills_dir`, exposed through `hermes_cli/config.py` and called by `ensure_hermes_home`.
- **Production invariant:** a Profile skills root whose write bits were deliberately removed remains read-only across every Gateway, Cron, Kanban and CLI startup; fresh and writable skill roots retain the official `0700` default.
- **Untouched v0.21.1 target:** every first `load_config()` in a process calls `ensure_hermes_home`, which unconditionally applies `_secure_dir(..., 0700)` to `HERMES_HOME/skills`. A direct syscall trace proved that even read-only `hermes kanban boards list --json` changed crawler's explicitly locked root from `0500` back to `0700`.
- **Why alternatives fail:** `HERMES_HOME_MODE=0500` also locks Cron, sessions, logs and all other state; `HERMES_SKIP_CHMOD` does not affect `_secure_dir`; same-user chmod/timers race every new process; the Kanban Bubblewrap boundary does not cover Profile Cron, Gateway or ordinary CLI sessions.
- **Minimal delta:** when the existing skills root has no owner/group/other write bit, preserve that stricter mode and only repair configured ownership; otherwise call the unchanged upstream `_secure_dir` path.
- **Validation:** focused regression 5/5; complete config and file-permission modules 83/83; real crawler reproduction remained `0500` after an official Kanban CLI startup, with 184 checked skill directories/`SKILL.md` files and zero writable entries.
- **Retirement trigger:** upstream supports a Profile-scoped read-only skills-root policy that survives `ensure_hermes_home`, or the crawler Profile is moved to a separately constrained identity/mount boundary proven to cover Gateway, Cron, Kanban and CLI execution.

## LP-020 — in-place compaction commit stamps the persistence marker

- **Status:** UPSTREAM-ABSORBED.
- **Upstream file / symbols:** `agent/conversation_compression.py` in-place commit branch, immediately after `archive_and_compact(...)` sets `split_status = "in_place_committed"`.
- **Production invariant:** after an in-place (`compression.in_place: true`) batch compaction commits, every compacted dict carries `_DB_PERSISTED_MARKER`, so the append-only flush (`_persist_session` → `_flush_messages_to_session_db_unlocked`) never re-INSERTs the post-compaction transcript. Live context size must monotonically shrink across a committed compaction.
- **Failure evidence (2026-08-30, coordinator session `20260830_121928_330881ba`, auditor1 session `20260829_205018_6a336f35`):** `compress()` returns marker-swept COPIES (`_strip_persistence_markers`); the in-place commit path — unlike `ContextCompressor._sync_micro_compact_to_db` — never re-stamped them. The same tool-result batch was durable-written twice with byte-identical timestamps at commit, again at turn finalize, and a fourth time mid-next-turn (state.db rows 529239/529304/529371/529692 sharing tool_call_id `call_NqMk...`; auditor1 held 41 duplicate groups, ~3.0 MB redundant). Live sets grew ~58K → ~512K tokens and every later preflight compression timed out at the 600 s ceiling against a session that no longer fit the model window, producing repeated "Context compression made no progress" failures on both profiles.
- **Upstream evidence:** deployed target contains `1f2bd9e763d304be136ffb3194d598c16a1a9eee` (#98450), which stamps `_DB_PERSISTED_MARKER` in the in-place commit path.
- **Validation:** the target's affected compression tests passed; the deployed diff carries neither compaction source nor the former local regression file.
- **Rule:** never port the old local implementation.

## LP-021 — lean compaction makes exactly one auxiliary request

- **Status:** UPSTREAM-ABSORBED.
- **Upstream file / symbols:** `agent/context_compressor.py` — digest-loop removal, single `_generate_summary` request, and `_sample_summary_input`.
- **Production invariant:** a lean-mode compaction attempt issues exactly one auxiliary `call_llm`. The digest loop (up to 28 sequential DeepSeek calls) is gone. Live context size after a committed compaction is unchanged by this patch (that remains LP-020).
- **Failure evidence (2026-08-31):** after LP-020, coordinator still issued four `Auxiliary compression: using deepseek` calls in ~7 minutes (10:51–10:58) and a 337 s micro-compaction. Local HEAD still contained `_build_chunk_digests`; default `compression.tail_mode: lean`.
- **Upstream evidence:** deployed target contains `4f22543509d1b91dc45bcb369447126c5eb14fb7` (#96603).
- **Validation:** the target's affected compression tests passed; the deployed diff carries neither compaction source nor the former local regression file.
- **Rule:** never port the old local implementation.

## LP-022 — Cron overlap suppression is not a failed execution

- **Status:** ACTIVE-SOURCE.
- **Files / symbols:** `cron/executions.py::discard_unstarted_execution`; `cron/scheduler.py::tick._process_job`.
- **Production invariant:** when a built-in tick loses the durable `fire_claim` to an already-running, manual, or external fire, the job has not started and must not be recorded as `failed`, increment failure streaks, create incidents, or pollute business completion reporting.
- **Failure evidence (2026-09-01):** `ipo-dlom` runs every minute and correctly serializes long projects, but 44 overlap attempts from 04:55 through 05:38 were recorded as `failed` with `Fire claim lost; execution was not started.`; all 44 had `started_at IS NULL` and represented zero failed projects.
- **Why alternatives fail:** marking overlap as completed corrupts success counts; adding a new terminal status widens the public schema and every consumer; filtering only reports leaves `cron doctor`, incidents, and failure streaks wrong; slowing the DLOM schedule creates avoidable queue idle time.
- **Minimal delta:** retain the pre-dispatch claimed placeholder for crash recovery, then transactionally delete only the current process's exact `claimed`, never-started row after confirmed claim loss. Any ownership/state mismatch remains an immutable diagnostic failure.
- **Validation:** focused execution-ledger and tick regressions prove normal overlap leaves no history row, while running/completed/foreign or otherwise unsafe rows cannot be deleted; complete relevant Cron suites must remain green.
- **Retirement trigger:** upstream records only successfully fire-claimed built-in attempts, or introduces a first-class neutral skipped/overlap terminal state excluded from failures, incidents, streaks, and business completion counts.

## LP-023 — npm advisory and Desktop compatibility closure for the frozen Hermes target

- **Status:** ACTIVE-SOURCE security maintenance on the deliberately frozen target; do not replace it by updating or rebasing Hermes upstream.
- **Files:** root/workspace `package.json` files and `package-lock.json`; `apps/desktop/src/plugins/hermes-bots/relay.test.ts`; `apps/desktop/scripts/bundle-electron-main.test.mjs`; `locales/_keys.desktop.json`.
- **Invariant:** the complete installed npm tree must report zero known vulnerabilities with the selected npm 12 audit path, without `npm audit fix --force`, duplicate runtimes, or unrelated source changes. Direct pins/overrides are `brace-expansion 5.0.12`, `dompurify 3.4.16`, `ip-address 10.7.2`, `js-yaml 4.3.2`, `undici 6.28.1/7.29.1`, `yaml 2.9.1`, `vitest 4.1.11`, and Electron `41.10.6`.
- **Electron 41 boundary:** Electron 40 cannot close the active advisory; 41.10.6 is the first selected audited line. Review the official Electron 41 breaking-change section before every later bump, then require typecheck, affected tests and a real package build. The relay test must distinguish the required empty roster sync sent to the remote primary from forbidden polling or retention of the non-primary local source; asserting zero total RPCs contradicts production behavior.
- **Desktop host-isolation delta:** the bundled-main Linux test must not inherit the audit host's `/proc/driver/nvidia/version`; its preload masks only that probe and synchronizes the mocked built-in ESM export. The generated Desktop locale-key manifest must include the three already-consumed read-only terminal strings (`terminalOpenInteractive`, `terminalReadOnly`, `terminalReadOnlyHelp`). Neither change alters production runtime behavior.
- **Validation:** `npm install` and `npm ls --all --depth=0` succeed; root `npm audit --json` returns zero vulnerabilities and exit zero; Desktop typecheck/lint exits zero; UI tests pass `1124` files / `9930` tests; Electron-platform tests pass `336` files / `3181` tests with six files and sixteen tests intentionally skipped; the focused relay test passes; and the Electron 41 Linux x64 production build and package test complete. Existing non-error lint warnings and the optional HUD X11 native-build degradation are reported, not converted into false failures or hidden by dependency changes.
- **Retirement trigger:** a later authorized Hermes target already contains an equal-or-stronger audited dependency graph and preserves the relay contract; re-prove from that target rather than blindly carrying these exact pins.

## DEPLOYMENT-CONTRACT DC-007 — compression total ceiling 1800 s on every profile

- **Class:** deployment contract; no source delta (config-only).
- **Files:** every profile `config.yaml` (`compression.context_total_ceiling_seconds: 1800`); coordinator, auditor1, coder, crawler, writer, supporter and default set 2026-08-30, read back verified.
- **Invariant:** a legitimately slow large-context compression is allowed to finish instead of being amputated at the default 600 s ceiling. Production: a 232,847-token summary completed server-side at 823.9 s but was abandoned at 600 s; 470K/525K-token real-payload probes completed in 45.3 s/12.8 s while in-session attempts died at 600 s. 1800 s covers the observed worst case with margin while keeping runaway attempts bounded.
- **Upgrade check:** confirm the key survives the merge in every profile config; if upstream changes the default or the semantics of `compression.context_total_ceiling_seconds` / `hygiene_total_ceiling_seconds`, re-derive this contract.

## DEPLOYMENT-CONTRACT DC-008 — fail-closed one-shot cutover and recovery controller

- **Class:** deployment contract; no Hermes upstream source delta.
- **Invariant:** a controller capable of stopping or restarting any Gateway is launched only as `Type=exec`, `Restart=no`, with no Timer/Path/dependency retry. Recovery failure is durably terminal; re-entry performs zero additional stop/start/publication actions until the failed prerequisite is repaired and a new attempt is explicitly authorized.
- **Failure evidence:** the 2026-10-01 recovery controller used `Restart=on-failure`, `RestartSec=1s`, and `StartLimitIntervalSec=0`; a restored-generation health failure therefore re-entered recovery and repeatedly stopped/started the default Gateway.
- **Validation:** the transaction's fail-closed recovery regression must first reproduce the old non-zero/replay behavior, then prove `RECOVERY_FAILED` plus side-effect-free re-entry. The private vertical health-failure, controller-crash and profile-contract-failure lanes must restore the known-good generation and leave no proof unit or fixture residue. Before any production cutover, read back the live transient unit and reject every automatic restart or activation path.
- **Rule:** systemd restart policy is never the cutover recovery mechanism. A separately authorized, state-aware invocation is the only retry path.

## DEPLOYMENT-CONTRACT DC-009 — stable Hermes and Python entries for external consumers

- **Class:** deployment contract; no Hermes upstream source delta.
- **Invariant:** every repository-external production runner and unit invokes Hermes through `/home/dionysos/.local/bin/hermes` and Python through `/home/dionysos/.hermes/services/python-runtime/python`. Neither a selected PM environment ID, an internal repository venv, `shutil.which("hermes")`, nor an inherited interactive PATH is a production contract.
- **Failure evidence:** after the 2026-09-30 environment switch, mixed launch resolution selected old/internal or bare-tool runtimes. Affected tasks reported missing provider packages or model connection failures even though the selected PM environment was healthy.
- **Repair:** external runners and units were moved to the stable launchers; the Python wrapper resolves the selected install/environment from PM facts at invocation time. The current environment has zero missing or mismatched declared runtime distributions.
- **Upgrade gate:** enumerate every Profile, Cron script, Kanban launcher, systemd unit and wrapper; reject any executable reference to a retired environment, internal venv or unstable PATH lookup. Historical logs are evidence, not executable consumers.

## DEPLOYMENT-CONTRACT DC-010 — isolated Agent PM, browser and credential boundary

- **Class:** external runner/sandbox contract; no Hermes upstream source delta.
- **Invariant:** an isolated Agent home can read the formal PM install registry but can write only the PM install lock and selected environment lease surface. Browser Harness runtime/temp/Chrome state is run-owned. A business-model subprocess receives only task-required tools and environment variables; Profile/crawler credential files are masked.
- **Failure evidence:** isolated homes without the PM registry fell back to a bare runtime; read-only Bubblewrap omitted lock/lease writes; Browser Harness inherited shared runtime defaults; Competitor/IPO subprocesses had broader terminal/filesystem/environment access than their tasks required.
- **Repair:** the formal install registry is linked read-only; only `.install.lock` and the selected environment `.leases` are writable; IPO assigns task-private Browser Harness paths and stable run names; Competitor removes general terminal access and masks the crawler environment file.
- **Validation:** a real Bubblewrap probe showed the masked crawler environment empty, Qixin credentials absent and only the required search credential present. A real Chrome/CDP probe used an OS-assigned loopback port and left no browser process, listener or run directory. The affected crawler cohort passed 244 tests.
- **Upgrade gate:** rerun both real probes after every PM, sandbox, Browser Use or runner change. Config equality and mocks are insufficient.

## DEPLOYMENT-CONTRACT DC-011 — WeKnora full-build carrier, readiness and resume

- **Class:** external RAG controller/systemd contract; no Hermes upstream source delta.
- **Invariant:** the one-shot full build and the intentionally disabled incremental watcher are separate lifecycle objects. The full build runs only in its persistent user unit under the dynamic Python launcher, with explicit PATH, `KillMode=control-group`, restart-on-failure and an intact resumable journal. Every write-capable controller mode fails before lock creation or remote writes unless readiness binds current controller commit/script hash, clean pinned official runtime commit, deployed image, embedding model and regression evidence.
- **Failure evidence:** earlier full-build processes were attached to disposable Hermes worker scopes; a transient unit later shadowed the persistent name. The build was stopped twice during recovery. Exact systemd windows show both exits followed explicit stop operations and reached `InterruptedError: stop requested`; no kernel OOM evidence exists. Live Graph tasks later returned malformed JSON for two source-input classes: ASCII backslashes (`invalid character ... in string escape code`) and raw line breaks copied into a JSON string (`invalid character '\\n' in string literal`). A later Graph task returned the provider's deterministic `Content Exists Risk` rejection for a seven-digit software-registration identifier. Re-running archived tasks without changing deterministic input repeated all three failures.
- **Repair:** the transient collision was removed; a persistent unit was restored with stable runtime and cgroup semantics. The full-build unit now runs a durable parent supervisor (`--retry-apply --poll-seconds 15`): a nonzero apply child or transient spawn error is audited and retried from the V2 journal without terminating the systemd service, while a requested stop exits cleanly without a false retry event. Readiness enforcement is called by the parent, `--apply`, `--watch` and every other write-capable mode before the lock path. Graph repair is failure-class driven rather than document-specific: an explicit invalid-string-escape failure encodes every ASCII backslash as `&#92;`; an explicit raw-newline-in-string failure encodes CR/LF as `&#13;`/`&#10;`; an explicit `Content Exists Risk` rejection groups standalone long registration identifiers of seven or more digits while conserving every digit and leaving shorter dates/version fields unchanged. Every official Chunk API write requires revision `+1`, `index_status=ready` and exact-or-trailing-whitespace-only readback, then uses native stage-local Graph recovery. A demonstrably unbalanced Chinese book-title quote remains a separate reversible class. Unsupported deterministic failures are not guessed or rewritten; they are recorded and passed to the official archived-task `run_now` path without terminating the durable parent. This follows DeepSeek's official JSON-mode warning and WeKnora's native asynchronous Graph lifecycle; production WeKnora upstream source and image remain unchanged. Incremental remains disabled and inactive.
- **Resume evidence:** at the authorized 2026-10-01 19:38 CST resume, the open V2 journal held 3,434 planned uploads, 10 intents and 6 verified uploads. The service recovered the 4 completed lost acknowledgements by metadata, reached 10/10, committed the manifest from 520 to 530 paths and continued the next scan. The invalid-string-escape object `28bc595e-c261-4ca8-900b-351e433ca2ab` / Chunk `cf62ef98-e160-4623-95cb-1e051c1f1f2a` changed from one current Graph failure to zero. On 2026-10-02 the raw-newline object `c4386c0f-561e-4e63-a4a5-a0cdabcc6a42` / Chunk `42b3b401-3ad6-4290-86b2-1c365fc3c4db` advanced from `graph_completed=2863/2864` with one repeated failure to `2864/2864`, zero failures and a complete Graph/Wiki receipt after the reversible Chunk revision `0→1`. Later the Content Exists Risk object `71550304-c8aa-4f3c-8c16-3ccaafd71983` / Chunk `1ba4ec36-39be-4512-a08a-c92306c66e17` advanced from `graph_completed=5302/5303` with one repeated failure to `5303/5303`, zero failures and a complete Graph/Wiki receipt after digit-preserving Chunk revision `0→1`; the official API canonicalized one trailing line break, which is accepted by the shared readback-equivalence rule. The current transaction then continued from its durable journal. The original 60-second progress one-liner was retired; its service/journal readback semantics were retained and extended in the sole current 15-second focused monitor.
- **Validation:** current controller script SHA `baf5ce4b6d2878dc07a352353e59a5eea040965fffdf3bad8899b704fd9fcd83`, controller HEAD, pinned upstream HEAD, deployed image and embedding model match the attestation; the current controller suite passes 85 tests plus 7 subtests and the complete WeKnora directory passes 144 tests plus 7 subtests. The focused 15-second monitor SHA is `4aadd0fad4deee925fea42b3f0b7d47fa6e2ca37c41cc395b3b865308994ff37` and its 3 tests cover service-state loss, restart growth, apply-child failure and journal corruption while suppressing requested-stop noise. The Tender/DLOM runtime cohort passes 144 tests plus 7 subtests.
- **Upgrade gate:** keep the incremental unit disabled/inactive. Admit the persistent full-build unit only after fleet, security and controller gates pass; enable it during the multi-day build so host/session recovery can resume it. Run the focused monitor at 15-second cadence with persistent process ownership and alert only on service loss, restart growth, apply-cycle failure or journal corruption; ordinary progress remains health telemetry. Disable the one-shot unit after final source/manifest/Knowledge/vector/Graph/Wiki/MCP conservation closes.

## DEPLOYMENT-CONTRACT DC-012 — Browser Use is the formal route; PM agent-browser is intentionally absent

- **Class:** deployment contract and explicit optional-component decision; no Hermes upstream source delta.
- **Formal route:** the model-facing surface is `browser_exec`; Browser Use / Browser Harness is the driver; the single shared stable Chrome entry is `~/.hermes/services/browser-runtime/bin/chrome`; task-private profiles, Harness runtimes and OS-assigned `--remote-debugging-port=0` listeners provide unattended isolation. The `chromium_headless_shell-*` compatibility entry is only a symlink to that same Chrome binary, not a second browser copy. Lightpanda is a distinct optional engine, not a duplicate Chromium.
- **Decision:** do **not** install PM `agent-browser` or PM `chromium` merely because `hermes doctor` prints an optional-component warning or `hermes pm doctor` prints `? ... not installed`. `pm doctor` exit zero and a green real Browser Use navigation establish that this absence is not a defect. The generic `browser` and `browser-use` availability rows must be interpreted separately from the optional local `agent-browser` backend.
- **Why installation is currently rejected:** the installed PM package graph declares `agent-browser -> chromium`. Installing `agent-browser --tools-only` would therefore add a second PM-managed Chromium beside the verified external Chrome runtime; it would not repair npm advisories, and it would not by itself make `hermes doctor` exit zero. Optional-component silence is not worth duplicate runtime ownership or a browser downgrade.
- **Upgrade gate:** every upgrade must preserve the Browser Use/Browser Harness import and launcher, the stable Chrome entry, PAC behavior, task-private profile/runtime ownership, random CDP allocation and complete teardown. Run one harmless real `browser_exec` navigation and verify zero test residue. Classify `agent-browser`/PM Chromium absence as intentional optional state, not an issue, cleanup target or installation recommendation.
- **Change boundary:** only a new explicit owner requirement for the built-in local `agent-browser` backend may reopen this decision. Before any such migration, inventory every hard-coded Chrome consumer and active independently supervised browser workload, prove the PM Chromium version is not a regression, migrate the stable entry, validate every affected Profile/Cron/Kanban/Runner, and remove the old runtime only after zero consumers. Never install first and decide ownership afterward.

## DEPLOYMENT-CONTRACT DC-013 — Session storage maintenance preserves real history

- **Class:** deployment/data-retention contract; no source delta.
- **Invariant:** a Doctor size warning is not corruption and does not authorize message deletion. Read the installed `sessions optimize-storage`, prune and VACUUM implementations; measure integrity, page/freelist use, FTS storage version, table/index contribution and safe prune candidates before scheduling downtime. Never delete rows merely because content repeats: lifecycle, compaction, display, platform or disposition differences can make byte-similar messages distinct durable records.
- **2026-10-02 evidence:** official optimize-storage completed for the default and crawler stores; five principal Profiles had zero 90-day or never-active prune candidates. A live-consistent copy of the approximately 1.9 GiB default store passed `quick_check` before and after VACUUM but reclaimed only about `1.057%`. The apparent 60,917-row semantic excess was concentrated in one historical session and included lifecycle/identity differences. Therefore no message rows were deleted, the Gateway was not stopped, and the one authorized maintenance window was not consumed.
- **Upgrade gate:** preserve every Profile `state.db`; use only official maintenance surfaces or a read-only/consistent-copy probe first. Enter a stop/start window only when the exact offline operation has proved material safe benefit or a real integrity defect. A retained-history capacity advisory may remain nonzero and must be reported honestly instead of forced green.

## DEPLOYMENT-CONTRACT DC-014 — MCP Authorization stays in Profile-scoped secret files

- **Class:** deployment/configuration contract; no source delta.
- **Invariant:** every MCP `Authorization` header in `config.yaml` is an environment substitution; its value exists only in that Profile's mode-`0600` `.env`. Never print, copy into Git, or preserve the value in rollback material after live verification.
- **Validation:** all eight formal Profiles pass independent `config check` and `mcp test jz_rag`; every inspected Authorization header is `${...}` substitution and all eight environment files are mode `0600`. A standalone MCP probe proves fresh-process resolution; a Gateway reload or new session is still required before claiming an already-running conversation's frozen tool schema changed.
- **Upgrade gate:** conserve variable names and per-Profile values without exposing them, scan configs for literal headers, check modes, then run config and MCP probes separately for every Profile. Delete credential-bearing temporary backups immediately after verification.

## DEPLOYMENT-CONTRACT DC-015 — Profile-local subscription adapters remain isolated

- **Class:** Profile-local plugin contract outside upstream source.
- **Crawler MiniMax web route:** `~/.hermes/profiles/crawler/plugins/web/minimax_token_plan_mcp/provider.py` lazily discovers only the configured `minimax_tp` MCP when its cached tool handle is absent. This closes cold-start sessions without broad MCP discovery; the focused test and a real fresh Crawler session must pass.
- **Auditor2 Alibaba CN route:** only auditor2 owns the `alibaba-token-plan-cn` web-search, web-extract and image-generation adapters and the `ALIBABA_TOKEN_PLAN_CN_API_KEY` reference. Other Profiles must have neither the plugin nor that selected provider. Validate each capability through auditor2's real runtime; generated paid-test media must be byte-checked and then removed.
- **Firecrawl boundary:** Crawler Firecrawl remains a distinct configured extraction route. A quota failure may be retried after recharge, but must not be silently replaced by a browser or another backend. The 2026-10-02 fresh session `20261002_131841_ab8c9b` returned `FIRECRAWL_EXTRACT_OK`, and its Crawler `state.db` tool chain contains the real extraction result.
- **Upgrade gate:** hash the Profile-local adapters/tests, prove only the intended Profile can select them, run fresh sessions through each selected backend, read the tool-call chain from the owning Profile store, and remove temporary media/backups. Do not modify official provider or Skill source to preserve these routes.

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

No CI-only source delta is active on this target. Historical installer/sandbox experiments are not part of the production difference surface and must not be replayed automatically.

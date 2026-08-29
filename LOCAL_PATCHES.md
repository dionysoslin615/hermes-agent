# LOCAL_PATCHES.md — production semantic delta ledger

**Authority:** release-blocking, equal in force to `LOCAL_UPGRADE_RUNBOOK.md`.
**Upstream baseline:** Hermes Agent v2026.8.27 / `5fc308a70719a83cccdbba4c0e39c23f5a8239d5` (v0.20.6).
**Policy:** upstream-first. A local semantic delta survives only when current upstream lacks an equivalent, configuration/plugin/shared-service/Cron/Kanban alternatives cannot preserve the same production invariant, and a real regression test proves deletion would break an existing function. Every future upgrade must attempt retirement again before porting code.

## Allowed source-difference surface

Only these runtime files may differ from the upstream baseline:

1. `cron/scheduler.py`
2. `gateway/run.py`
3. `agent/agent_init.py`
4. `tools/kanban_tools.py`
5. `hermes_cli/kanban_db.py`
6. `tools/browser_use_cli.py`
7. `plugins/platforms/dingtalk/adapter.py`
8. `hermes_cli/config.py`

Governance/CI-only files may also differ:

- `AGENTS.md`
- `LOCAL_PATCHES.md`
- `LOCAL_UPGRADE_RUNBOOK.md`
- `scripts/sandbox/proxy.py` (CI-001; never imported by production runtime)

Local regression files may differ only when they directly exercise an ACTIVE-SOURCE invariant:

- `tests/cron/test_cron_script.py`
- `tests/gateway/test_dingtalk.py`
- `tests/hermes_cli/test_kanban_core_functionality.py`
- `tests/hermes_cli/test_kanban_skill_readonly_sandbox.py`
- `tests/hermes_cli/test_kanban_worker_spawn_toolsets.py`
- `tests/hermes_cli/test_config.py`
- `tests/tools/test_browser_use_cli.py`
- `tests/tools/test_cloud_voice_integration.py` (DingTalk-only despite the historical filename)
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
- **Replacement:** one external, hash-locked canonical-environment manifest plus before/after distribution conservation and real consumer smoke tests, documented in `LOCAL_UPGRADE_RUNBOOK.md`.
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

## CI-001 — transparent non-fixture HTTPS in Install & Update E2E

- **Class:** CI-only; not production runtime source.
- **File:** `scripts/sandbox/proxy.py`.
- **Invariant:** the real installer/update matrix must not fail because the test proxy performs a redundant second TLS handshake for npm/PyPI traffic.
- **Upstream/fork evidence:** both upstream and the fork repeatedly failed with `SSLEOFError` inside the Python MITM proxy; update legs otherwise progressed.
- **Minimal delta:** keep MITM only for fixture hosts and use standard transparent CONNECT tunnelling for every non-fixture host.
- **Validation:** local bidirectional CONNECT integration smoke and Python compilation pass; the synchronized fork workflow is the final remote acceptance test.
- **Retirement trigger:** upstream adopts an equivalent tunnel or replaces the sandbox proxy.

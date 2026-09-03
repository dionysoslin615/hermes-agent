# LOCAL_PATCHES.md — production semantic delta ledger

**Authority:** release-blocking, equal in force to `LOCAL_UPGRADE_RUNBOOK.md`.
**Upstream baseline:** owner-frozen immutable `origin/main` snapshot `73f68362b3f639b97352a5dedc9e74b10520a84f` (Hermes v0.21.0; 478 upstream commits after the prior `f709bd88b6cc62b23f40e878c1d5960604302ee2` production baseline). The owner explicitly froze this SHA after the candidate had already passed, rather than continuing to chase a moving `main`; later upstream movement belongs to a later maintenance cycle.
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

Package-contract files may differ only for the explicitly approved DingTalk SDK pin in LP-023 and the lock-only `sanitize-html` security update recorded below:

- `pyproject.toml`
- `uv.lock`
- `tools/lazy_deps.py`
- `package-lock.json`

Governance/CI-only files may also differ:

- `AGENTS.md`
- `LOCAL_PATCHES.md`
- `LOCAL_UPGRADE_RUNBOOK.md`
- `scripts/sandbox/proxy.py`, `scripts/sandbox/stage2-run.sh` and `scripts/dev-sandbox.sh` (CI-001; never imported by production runtime)
- `.github/workflows/install-e2e.yml` and `scripts/sandbox/pick-release-tags.sh` (CI-003; never imported by production runtime)
- `.github/workflows/ci.yaml` (CI-only correction; never imported by production runtime)

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
- `tests/tools/test_browser_real_profile.py`
- `tests/tools/test_browser_snapshot_threshold.py`
- `tests/tools/test_browser_supervisor.py`
- `tests/tools/test_cloud_voice_integration.py` (DingTalk-only despite the historical filename)
- `tests/tools/test_kanban_tools.py`

Any other Git difference is a release blocker until either removed or entered here after the complete necessity procedure.

### 2026-09-02 absorption readback

- `git cherry -v origin/main HEAD` reports all ten local non-merge commits as `+`: exact patch-id absorption is zero.
- Semantic review found related upstream work around compression, browser lifecycle, routed-profile Cron and multiplexed secrets, but none fully preserves the production invariants carried by the allowed runtime files above. No active local source delta is retired in this cutover.
- The failed `agent-browser` 0.36 experiment and all proposed Hermes packaging workarounds were discarded before production. Production remains on Hermes' original npm-native `agent-browser` 0.26.0 entry. The upgrade-created `services/browser-runtime/bin/agent-browser` wrapper and Lightpanda 0.3.7 downgrade were both erroneous experiment residue and were fully retired after owner correction. The pre-upgrade governed state is restored: Chrome remains the active/default browser path, while official Lightpanda 0.4.0 is installed only as the explicitly deferred optional engine recorded in `runtime-manifest.json`. No new `hermes-agent` runtime-source patch or deployment-layer launcher remains from this experiment.

### 2026-09-03 post-upgrade hygiene readback

- No additional Hermes repository runtime-source delta was introduced. Profile-local `PLAYWRIGHT_BROWSERS_PATH` and `AGENT_BROWSER_EXECUTABLE_PATH` duplicates were removed; the central `environment.d` declarations remain authoritative for the governed engine root and Chrome executable. Every formal Profile retains `AGENT_BROWSER_ARGS=--no-sandbox,--disable-dev-shm-usage,--proxy-pac-url=http://127.0.0.1:7788/proxy.pac`: the shared PAC sends only whitelist matches through the proxy and returns `DIRECT` for all other destinations. Tender's Firecrawl/direct-browser/PAC escalation order is task-specific and does not remove this fleet-wide PAC capability.
- The official Playwright live-doctor path requires revision `chromium_headless_shell-1234`; a compatibility symlink under the central browser-runtime engine root resolves that path to the existing governed Chrome 152 binary. It does not duplicate, download or wrap a browser executable. Seven `doctor --live` runs launched and closed the browser successfully, and seven fresh primary-model calls returned `PROFILE_OK`.
- The crawler DLOM runner is an external business runner, not Hermes core source. Its transaction backup now survives database commit, integrity/readback checks, durable completion receipt and the queue transition to `completed`, then is hash-verified and deleted while its path/hash/deletion time remain in the receipt. The focused runner suite passes 86 tests. This prevents successful projects from accumulating full database snapshots without weakening rollback safety.
- Deep cleanup removed all non-Tender children of `~/.hermes/backups`, Profile backup residue, 478,703,616 allocated bytes of superseded deep service/project/MA-detail backups, 787 stale DLOM backup-directory shells plus 5,226,496 allocated bytes of completed-project repair copies, stale `/tmp` content including 67,219,456 allocated bytes of upgrade browser/pytest/audit residue, superseded MinerU jobs with hash-identical formal KB copies, obsolete MinerU temporary jobs and an unreferenced service wrapper. Git-tracked source assets are retained even when their historical names contain `backup` or `before`; Tender material, live curator recovery blobs, receipt-bound DLOM artifacts, unresolved MinerU source/intermediates and production services also remain intentionally preserved.
- A final two-pass residue sweep removed the new non-Tender recovery/probe backup, all unreferenced maintenance worktrees, package staging/rollback material, browser/pytest/build/audit temporaries and stale sockets; npm cache verification garbage-collected invalid content. The root backup directory now contains only the five owner-retained Tender groups.
- `sanitize-html` is lock-pinned from vulnerable 2.17.6 to fixed 2.17.7 without changing any parent package or dependency range. The live tree resolves only 2.17.7; root and Web production audits report zero vulnerabilities. A clean isolated `npm ci --ignore-scripts` followed by Web typecheck, tests, lint and production build passed, and the candidate/rollback material was removed.
- GitHub CLI API access was healthy while unauthenticated Git HTTPS fetches returned HTTP 429 because no credential helper was configured. `gh auth setup-git` installed the authenticated helper and `git fetch --all --prune --no-tags` then completed normally. The fork is synchronized only by a fast-forward of this governed branch; floating official `origin/main` remains next-cycle input and is not merged into the owner-frozen production target.
- GitHub's `ci.yaml` also failed before creating any job because the `detect-changes` composite action accepts only `github-token`, while the caller passed two checkout-only inputs (`sparse-checkout` and `sparse-checkout-cone-mode`). Removing those undefined inputs preserves the composite action's own checkout/classification implementation and allows GitHub to dispatch the workflow normally.
- Once dispatch was restored, the blocking Windows-footgun lane correctly exposed three POSIX-only local-patch references. The two `os.killpg` calls now carry the checker's explicit same-line POSIX suppression beside their existing runtime guards, and Linux `prctl` resolves `SIGKILL` with a portable `SIGTERM` fallback. The complete checker scans 1,085 files with zero findings; focused Kanban and Browser Use suites pass 47 and 125 tests.
- The remaining fork CI jobs were not failing code: their requested `ubuntu-latest-32-core`, `ubuntu-latest-96-core`, and `windows-latest-32-core` labels are private larger-runner labels available to the upstream repository but unavailable to the personal fork, so GitHub left them queued without assigning a runner. Reusable test workflows now select those labels only in `NousResearch/hermes-agent` and otherwise fall back to standard GitHub-hosted labels; upstream capacity and behavior are unchanged.
- On the lower-capacity standard fork runner, the SessionsPage routing regression exceeded Vitest's 5-second default once while the same lane was running all workspaces concurrently. Its explicit timeout is now 15 seconds; assertions and production code are unchanged.

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
- **Untouched upstream snapshot:** accepts only values greater than zero and otherwise returns 3600 seconds; its execution loop also assumes every timeout is numeric.
- **Why alternatives fail:** selecting an arbitrary larger number changes unlimited semantics; splitting the runner changes checkpoint, lease, delivery, and idempotency behavior.
- **Minimal delta:** translate exact numeric zero from module override, environment bridge, or config into `None`; when it is `None`, skip deadline arithmetic while retaining cancellation polling and all positive-timeout behavior.
- **Regression evidence:** after the v0.20.6 cutover, `ipo-dlom` exposed the incomplete first port as `TypeError: unsupported operand type(s) for +: 'float' and 'NoneType'`; the corrected scheduler/script suite passed 68 tests with 1 skipped.
- **Upstream tracking:** [#100943](https://github.com/NousResearch/hermes-agent/issues/100943).
- **Retirement trigger:** upstream supports an explicit unlimited setting through both configuration parsing and script execution, or all formal long runners are redesigned and proven bounded without changing business semantics.

## LP-002 — Gateway remote image URL routing

- **Status:** ACTIVE-SOURCE.
- **File / symbol:** `gateway/run.py`, pending-native-image call to `build_native_content_parts`.
- **Production invariant:** HTTP(S) image references from messaging platforms reach a vision-capable model as native `image_url` parts.
- **Untouched upstream snapshot:** the image builder supports `image_urls`, but this Gateway call site passes every reference as a local path; URL references therefore enter local filesystem checks and are skipped.
- **Minimal delta:** partition local paths and HTTP(S) URLs at the call site and pass them to the two official parameters.
- **Upstream tracking:** existing issue [#31857](https://github.com/NousResearch/hermes-agent/issues/31857) was rechecked and supplemented with the cross-platform Gateway call-site evidence; no duplicate issue was opened.
- **Retirement trigger:** upstream Gateway performs the same partition or normalizes every platform image into a verified local cache before this call.

## LP-003 — authenticated DingTalk inbound media normalization

- **Status:** ACTIVE-SOURCE.
- **File / symbols:** `plugins/platforms/dingtalk/adapter.py`, inbound media extraction, `downloadCode` resolution, authenticated download/cache, recognition-text selection and STT fallback.
- **Production invariant:** DingTalk image, audio and document messages become readable local paths; voice messages use platform recognition text when non-empty and otherwise run configured Hermes STT.
- **Current consumers:** coordinator, writer and auditor1. Crawler, coder and supporter have no DingTalk platform/toolset binding, credentials, Cron origin, channel-directory entry or Gateway telemetry; default remains Telegram-only.
- **Untouched upstream snapshot:** extracts some references and resolves `downloadCode` to a temporary URL, but command STT rejects non-local paths before execution and document/image consumers require readable local bytes.
- **Minimal delta:** keep latest upstream adapter and add only authenticated byte acquisition, type-safe cache, dedupe and recognition/STT fallback.
- **Upstream tracking:** inbound media chain [#31857](https://github.com/NousResearch/hermes-agent/issues/31857) and document callback gap [#16964](https://github.com/NousResearch/hermes-agent/issues/16964).
- **Retirement trigger:** upstream DingTalk emits local cached media with equivalent auth, size/type limits and voice fallback.

## LP-004 — Profile-scoped Kanban worker fan-out

- **Status:** ACTIVE-SOURCE.
- **Files / symbols:** `agent/agent_init.py` worker guidance gate; `tools/kanban_tools.py::_worker_can_create_tasks`, create/link checks.
- **Production invariant:** dispatched workers always retain their own task lifecycle tools; only profiles configured with `kanban.worker_can_create_tasks: true` may create/link follow-up cards. Normal orchestrator chats must not receive worker-only prompt guidance.
- **Real consumers:** coordinator and auditor1 may fan out; crawler, coder, writer and supporter are restricted. The Internal Journal contract still uses worker-created continuation cards.
- **Why toolset removal fails:** removing the Kanban toolset also removes `show`, `heartbeat`, `comment`, `complete` and `block`, so the worker cannot satisfy its protocol.
- **Minimal delta:** default true for upstream compatibility; hide and reject only create/link for explicitly false worker profiles; require `HERMES_KANBAN_TASK` before injecting worker guidance.
- **Upstream tracking:** [#100944](https://github.com/NousResearch/hermes-agent/issues/100944).
- **Retirement trigger:** upstream has per-profile/per-worker allow and deny controls that preserve lifecycle tools.

## LP-005 — read-only Skill trees for Kanban workers

- **Status:** ACTIVE-SOURCE.
- **File / symbols:** `hermes_cli/kanban_db.py::_kanban_worker_skill_roots`, `_sandbox_kanban_worker_skills_read_only`, `_default_spawn`.
- **Production invariant:** every dispatched Kanban worker can read but cannot modify any default, Profile, external or symlink-target Skill tree.
- **Why chmod fails:** worker and skill owner are the same Linux user; a worker can reverse owner permission bits. Current formal Skill roots are owner-writable outside task-specific lock windows.
- **Minimal delta:** Linux bubblewrap around only the worker process; host filesystem otherwise unchanged; all visible Skill roots and symlink targets `--ro-bind`; missing boundary fails closed.
- **Upstream tracking:** existing task-scoped read-only overlay proposal [#33245](https://github.com/NousResearch/hermes-agent/issues/33245).
- **Retirement trigger:** upstream offers an equivalent mount/sandbox policy or workers run under a separately constrained identity proven unable to write every Skill target.

## LP-006 — Kanban worker routing-environment scrub

- **Status:** ACTIVE-SOURCE.
- **File / symbol:** `hermes_cli/kanban_db.py::_default_spawn`.
- **Production invariant:** detached workers never inherit interactive Gateway/session routing identity.
- **Untouched upstream snapshot:** removes only keys currently present in `_VAR_MAP`.
- **Minimal delta:** additionally remove all `HERMES_SESSION_*`, all `HERMES_GATEWAY_*`, `HERMES_UI_SESSION_ID`, and `_HERMES_GATEWAY` before adding worker-owned variables.
- **Upstream tracking:** child authority/environment inheritance is tracked by [#83565](https://github.com/NousResearch/hermes-agent/issues/83565), including the related Kanban subprocess reports it indexes.
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
- **v0.21.0 evidence:** `_flush_one_shot_session_store` persists terminal state through `end_session` while preserving the remaining cleanup path.
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
- **Untouched upstream snapshot:** local document send explicitly returns unsupported; no complete sampleFile/sampleAudio/sendStatus path.
- **Minimal delta:** reuse upstream adapter/session identity; add only DingTalk OpenAPI calls, Stream-token reuse with official OAuth fallback for proactive/independent sends, cache and expiry bounds, real recipient validation and truthful `SendResult`.
- **Upstream tracking:** authenticated local-document delivery [#76096](https://github.com/NousResearch/hermes-agent/issues/76096); broader platform media-send gap [#22487](https://github.com/NousResearch/hermes-agent/issues/22487).
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
- **v0.21.0 evidence:** `create_task` transactionally preserves an initial blocked state and its sticky reason.
- **Production-consumer audit:** no formal Cron, Kanban contract, Runner or reporting path requires a second synthetic `blocked` history event at creation time.
- **Rule:** the uncommitted local event hunk and its dedicated regression are not ported.

## LP-017 — unattended Browser Use run-owned Chrome lease

- **Status:** ACTIVE-SOURCE.
- **File / symbols:** `tools/browser_use_cli.py`, unattended-worker detection, governed CLI resolution, run-owned Chrome lease and daemon-safe CLI execution.
- **Production invariant:** every Cron/Kanban worker that calls `browser_exec` owns a task-private Browser Harness runtime and daemon. Without a pre-launched CDP it also receives one task-private central Chrome on an OS-assigned loopback port, with PAC routing, four no-download guards and complete daemon/process/profile cleanup. Interactive Browser Use keeps upstream defaults.
- **Untouched v0.21.0:** Browser Harness expects an already running Chrome; when the CLI is not on the worker's scrubbed PATH, `_find_cli` falls through to `uvx browser-use`; `subprocess.run(capture_output=True)` can wait forever when the persistent Harness daemon inherits its pipes. Even with an operator-owned CDP, Browser Use starts a detached Harness daemon in the shared default runtime unless the worker receives an explicit `BH_RUNTIME_DIR`/`BU_NAME` lifecycle.
- **Why alternatives fail:** persistent Profile CDP services violate task isolation; `BH_CHROME_PATH` launches a shared/default Chrome profile and cannot express the existing PAC/task lease; per-Runner duplication leaves generic Kanban and future Cron consumers uncovered; changing HOME breaks Profile credentials and provider state.
- **Minimal delta:** activate only for `HERMES_KANBAN_TASK` or explicit `HERMES_RUN_OWNED_BROWSER=1`; always prefer an existing CDP but still assign it a private `BH_RUNTIME_DIR`/`BU_NAME`; resolve the one shared governed Browser Use launcher and prohibit unattended uvx fallback; only when no CDP exists, start central Chrome with `--remote-debugging-port=0` and bridge to `BU_CDP_URL`; place the Harness AF_UNIX runtime at `/tmp/hbu_<pid>` so the complete `bu.sock` path stays below the documented 104-byte budget; use temp files instead of stdout/stderr pipes; clean by atexit and parent-death binding.
- **Upstream tracking:** [#100945](https://github.com/NousResearch/hermes-agent/issues/100945).
- **Validation:** Browser Use regressions 90/90 and the complete `test_browser*.py` set 460 passed with 7 deselected; a real Kanban card completed with title/text/url readback, managed CLI, no uvx, random port 37139, PAC, four guards and zero cache delta. A real policy Cron exposed the missing external-CDP case: its escaped daemon held sandbox stdio for over an hour, and the first repair still placed `BH_RUNTIME_DIR` below the deep Profile home, causing `AF_UNIX path too long`. The corrected external-CDP smoke attached to Runner-owned Chrome on random port 45539, read the live page, removed `/tmp/hbu_<pid>`, and left no new Harness daemon, socket, port or profile residue.
- **Retirement trigger:** upstream Browser Use natively launches a task/profile-private headless Chrome with random CDP, supports governed executable/PAC routing, fails closed instead of uvx in unattended sessions, and owns complete daemon/browser cleanup.

## LP-018 — Kanban timeout terminates the worker process group

- **Status:** ACTIVE-SOURCE.
- **File / symbol:** `hermes_cli/kanban_db.py::enforce_max_runtime`.
- **Production invariant:** max-runtime enforcement terminates the entire worker session, including Bubblewrap children, Browser Harness daemon and task-owned Chrome, before releasing the claim or recording timeout.
- **Untouched v0.21.0:** `_default_spawn` uses `start_new_session=True`, but timeout enforcement signals only the recorded leader PID and treats leader exit as complete; live descendants and browser listeners remain orphaned.
- **Minimal delta:** on POSIX, verify `os.getpgid(pid) == pid`, signal that PGID, poll group existence, then escalate the same group to SIGKILL; preserve the injected single-PID signal hook and Windows behavior.
- **Upstream tracking:** existing exact-class report [#80280](https://github.com/NousResearch/hermes-agent/issues/80280).
- **Validation:** dedicated group-liveness regression plus Kanban core 25/25; real timeout reproduced the orphan before the patch, and a task-owned Chrome was then proven to share the worker PGID. Manual test residue was removed before proceeding.
- **Retirement trigger:** upstream timeout/reclaim owns process-tree or cgroup termination and proves no descendants/listeners survive.

## LP-019 — preserve an explicitly read-only Profile skills root

- **Status:** ACTIVE-SOURCE.
- **File / symbol:** `hermes_cli/config.py::_secure_skills_dir`, called by `ensure_hermes_home`.
- **Production invariant:** a Profile skills root whose write bits were deliberately removed remains read-only across every Gateway, Cron, Kanban and CLI startup; fresh and writable skill roots retain the official `0700` default.
- **Untouched v0.21.0:** every first `load_config()` in a process calls `ensure_hermes_home`, which unconditionally applies `_secure_dir(..., 0700)` to `HERMES_HOME/skills`. A direct syscall trace proved that even read-only `hermes kanban boards list --json` changed crawler's explicitly locked root from `0500` back to `0700`.
- **Why alternatives fail:** `HERMES_HOME_MODE=0500` also locks Cron, sessions, logs and all other state; `HERMES_SKIP_CHMOD` does not affect `_secure_dir`; same-user chmod/timers race every new process; the Kanban Bubblewrap boundary does not cover Profile Cron, Gateway or ordinary CLI sessions.
- **Minimal delta:** when the existing skills root has no owner/group/other write bit, preserve that stricter mode and only repair configured ownership; otherwise call the unchanged upstream `_secure_dir` path.
- **Upstream tracking:** existing `_secure_dir` permission-clobber report [#68055](https://github.com/NousResearch/hermes-agent/issues/68055) was used rather than opening a narrower duplicate.
- **Validation:** focused regression 5/5; complete config and file-permission modules 83/83; real crawler reproduction remained `0500` after an official Kanban CLI startup, with 184 checked skill directories/`SKILL.md` files and zero writable entries.
- **Retirement trigger:** upstream supports a Profile-scoped read-only skills-root policy that survives `ensure_hermes_home`, or the crawler Profile is moved to a separately constrained identity/mount boundary proven to cover Gateway, Cron, Kanban and CLI execution.

## LP-020 — in-place compaction persistence marker

- **Status:** UPSTREAM-ABSORBED in v0.21.0.
- **Upstream evidence:** the frozen target contains `stamp_db_persisted_markers(compressed)` in the committed in-place compaction path, preserving the append-only flush skip invariant.
- **Rule:** the former `agent/conversation_compression.py` hunk and local-only regression are not ported.
- **Validation:** untouched v0.21.0 marker reproducer passes; no local diff remains in `agent/conversation_compression.py`.

## LP-021 — lean compaction single auxiliary request

- **Status:** UPSTREAM-ABSORBED in v0.21.0.
- **Upstream evidence:** the frozen target contains `_sample_summary_input`, folds lean input into the single summary request, and has no `_build_chunk_digests` loop.
- **Rule:** the former `agent/context_compressor.py` backport and local-only regression are not ported.
- **Validation:** untouched v0.21.0 single-call reproducer passes; no local diff remains in `agent/context_compressor.py`.

## LP-022 — Cron overlap suppression is not a failed execution

- **Status:** ACTIVE-SOURCE.
- **Files / symbols:** `cron/executions.py::discard_unstarted_execution`; `cron/scheduler.py::tick._process_job`.
- **Production invariant:** when a built-in tick loses the durable `fire_claim` to an already-running, manual, or external fire, the job has not started and must not be recorded as `failed`, increment failure streaks, create incidents, or pollute business completion reporting.
- **Failure evidence (2026-09-01):** `ipo-dlom` runs every minute and correctly serializes long projects, but 44 overlap attempts from 04:55 through 05:38 were recorded as `failed` with `Fire claim lost; execution was not started.`; all 44 had `started_at IS NULL` and represented zero failed projects.
- **Why alternatives fail:** marking overlap as completed corrupts success counts; adding a new terminal status widens the public schema and every consumer; filtering only reports leaves `cron doctor`, incidents, and failure streaks wrong; slowing the DLOM schedule creates avoidable queue idle time.
- **Minimal delta:** retain the pre-dispatch claimed placeholder for crash recovery, then transactionally delete only the current process's exact `claimed`, never-started row after confirmed claim loss. Any ownership/state mismatch remains an immutable diagnostic failure.
- **Upstream tracking:** [#100946](https://github.com/NousResearch/hermes-agent/issues/100946).
- **Validation:** focused execution-ledger and tick regressions prove normal overlap leaves no history row, while running/completed/foreign or otherwise unsafe rows cannot be deleted; complete relevant Cron suites must remain green.
- **Retirement trigger:** upstream records only successfully fire-claimed built-in attempts, or introduces a first-class neutral skipped/overlap terminal state excluded from failures, incidents, streaks, and business completion counts.

## LP-023 — DingTalk OpenAPI SDK 2.2.57 pin

- **Status:** ACTIVE-SOURCE package contract; no Hermes runtime logic change.
- **Files:** `pyproject.toml`, `uv.lock`, `tools/lazy_deps.py`.
- **Production invariant:** the canonical Hermes environment and future rebuilds use `alibabacloud-dingtalk==2.2.57`; every unrelated Python distribution remains frozen. The resolver metadata change to `alibabacloud-gateway-spi==0.0.4` is required by 2.2.57 and matches the version already present in production before this maintenance.
- **Current consumers:** the package remains required by coordinator, writer and auditor1. Its presence in the one shared canonical venv does not enable DingTalk for crawler, coder, supporter or default; platform activation remains strictly Profile-configured.
- **Minimal delta:** change only the DingTalk extra/lazy-dependency pins and the two corresponding lock records. The external hash lock at `~/.hermes/services/python-runtime/` remains the production installation authority; task-time lazy installation stays forbidden in production.
- **Validation:** a relocatable Python 3.11.15 candidate built from the full external hash lock conserved 262/262 distributions with only `alibabacloud-dingtalk` changing; `uv pip check`, Robot/Card/new-model imports, 51 focused DingTalk tests and five Profile configuration checks passed before cutover. Production cutover then installed exactly 2.2.57, retained the already-present gateway SPI 0.0.4, restarted only the five DingTalk Profiles, preserved the default/crawler Gateway PIDs, and read back all five platform states as connected with live TLS sockets. The final 18-file local regression matrix passed 596 tests with 8 intentional skips and zero failures.
- **Retirement trigger:** the next immutable upstream target pins 2.2.57 or newer and passes the same conservation and DingTalk regression matrix.

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

- **Class:** UPSTREAM-ABSORBED in v0.21.0.
- **Upstream evidence:** `scripts/install.sh::node_deps_workspace_args` now scopes installation to `ui-tui`, `web`, and the workspace root, with a root-only fallback that excludes `apps/*`.
- **Rule:** the former `scripts/install.sh` hunk and installer-only regression are not ported.
- **Validation:** frozen-target installer scope tests and Exact-HEAD fork E2E must pass.

## CI-003 — select only reachable release tags with a complete checkout graph

- **Class:** CI-only; not production runtime source.
- **Files:** `.github/workflows/install-e2e.yml`, `scripts/sandbox/pick-release-tags.sh`.
- **Invariant:** Install & Update E2E may select only release refs accepted by the target main branch, and its reachability test must run against a complete commit graph.
- **Failure evidence:** fork run `33449769412` selected a release tag left unreachable by an upstream history rewrite; after adding reachability filtering, run `33515746755` used `fetch-tags: true` with the default shallow depth and falsely reported zero reachable tags because tagged ancestors were behind the shallow boundary.
- **Minimal delta:** filter release tags with `merge-base --is-ancestor "${tag}^{}" HEAD`; set the picker checkout to `fetch-depth: 0` while retaining `fetch-tags: true`.
- **Validation:** local full-graph and synthetic unreachable-tag picker tests, followed by Exact-HEAD fork E2E run `33524153684` at runtime commit `aae3b91bff7a99972efb5110913c826dec623d3e`; the picker plus all ten installer/update matrix jobs passed.
- **Upstream tracking:** [#100947](https://github.com/NousResearch/hermes-agent/issues/100947).
- **Retirement trigger:** upstream adopts equivalent reachability filtering plus a complete picker checkout graph.

## CI-004 — deterministic browser regression harnesses

- **Class:** test-only; never imported by production runtime.
- **Files:** `tests/tools/test_browser_real_profile.py`, `tests/tools/test_browser_snapshot_threshold.py`, `tests/tools/test_browser_supervisor.py`.
- **Invariant:** Browser lifecycle tests isolate the unit under test instead of accidentally launching a real Chrome, depending on same-size file rewrites changing `mtime_ns`, or omitting the same AppArmor sandbox bypass selected by production.
- **Validation:** after upgrading the governed browser stack, the complete 60-file Browser/CDP set passed as independent processes: 877 passed and one intentional OOPIF skip. Real Chrome and Lightpanda CDP validation is recorded in `LOCAL_UPGRADE_RUNBOOK.md`.
- **Upstream tracking:** [#100983](https://github.com/NousResearch/hermes-agent/issues/100983), [#100988](https://github.com/NousResearch/hermes-agent/issues/100988), and the integration-fixture note on [#15765](https://github.com/NousResearch/hermes-agent/issues/15765).
- **Retirement trigger:** upstream tests contain equivalent deterministic isolation and environment-sensitive sandbox setup.

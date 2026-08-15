# LOCAL_PATCHES.md — production semantic delta ledger

**Authority:** release-blocking, equal in force to `LOCAL_UPGRADE_RUNBOOK.md`.
**Upstream baseline:** Hermes Agent v2026.8.13 / `f80f453ae0679347e38abc917c7f94f717bf96c5`.
**Policy:** upstream-first. A local semantic delta survives only when current upstream lacks an equivalent, configuration/plugin/shared-service/Cron/Kanban alternatives cannot preserve the same production invariant, and a real regression test proves deletion would break an existing function. Every future upgrade must attempt retirement again before porting code.

## Allowed source-difference surface

Only these runtime files may differ from the upstream baseline:

1. `cron/scheduler.py`
2. `gateway/run.py`
3. `agent/agent_init.py`
4. `tools/kanban_tools.py`
5. `hermes_cli/kanban_db.py`
6. `cli.py`
7. `plugins/platforms/dingtalk/adapter.py`

Governance-only files may also differ:

- `AGENTS.md`
- `LOCAL_PATCHES.md`
- `LOCAL_UPGRADE_RUNBOOK.md`

Local regression files may differ only when they directly exercise an ACTIVE-SOURCE invariant:

- `tests/cli/test_single_query_session_finalize.py`
- `tests/cron/test_cron_script.py`
- `tests/gateway/test_dingtalk.py`
- `tests/hermes_cli/test_kanban_skill_readonly_sandbox.py`
- `tests/hermes_cli/test_kanban_worker_spawn_toolsets.py`
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
- **File / symbol:** `cron/scheduler.py::_get_script_timeout`.
- **Production invariant:** `cron.script_timeout_seconds: 0` means no `subprocess.run` timeout. Long-running DLOM and similar stateful runners must not be killed at one hour.
- **Upstream 0.20.1:** accepts only values greater than zero and otherwise returns 3600 seconds.
- **Why alternatives fail:** selecting an arbitrary larger number changes unlimited semantics; splitting the runner changes checkpoint, lease, delivery, and idempotency behavior.
- **Minimal delta:** translate exact numeric zero from module override, environment bridge, or config into `None`; preserve all positive and invalid-value upstream behavior.
- **Retirement trigger:** upstream supports an explicit unlimited setting or all formal long runners are redesigned and proven bounded without changing business semantics.

## LP-002 — Gateway remote image URL routing

- **Status:** ACTIVE-SOURCE.
- **File / symbol:** `gateway/run.py`, pending-native-image call to `build_native_content_parts`.
- **Production invariant:** HTTP(S) image references from messaging platforms reach a vision-capable model as native `image_url` parts.
- **Upstream 0.20.1:** the image builder supports `image_urls`, but this Gateway call site passes every reference as a local path; URL references therefore enter local filesystem checks and are skipped.
- **Minimal delta:** partition local paths and HTTP(S) URLs at the call site and pass them to the two official parameters.
- **Retirement trigger:** upstream Gateway performs the same partition or normalizes every platform image into a verified local cache before this call.

## LP-003 — authenticated DingTalk inbound media normalization

- **Status:** ACTIVE-SOURCE.
- **File / symbols:** `plugins/platforms/dingtalk/adapter.py`, inbound media extraction, `downloadCode` resolution, authenticated download/cache, recognition-text selection and STT fallback.
- **Production invariant:** DingTalk image, audio and document messages become readable local paths; voice messages use platform recognition text when non-empty and otherwise run configured Hermes STT.
- **Upstream 0.20.1:** extracts some references and resolves `downloadCode` to a temporary URL, but command STT rejects non-local paths before execution and document/image consumers require readable local bytes.
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
- **Upstream 0.20.1:** removes only keys currently present in `_VAR_MAP`.
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

- **Status:** ACTIVE-SOURCE.
- **File / symbols:** `cli.py::_end_single_query_session`, `_finalize_single_query`.
- **Production invariant:** `hermes chat -Q` ends the final continuation tip in `state.db` before releasing the active lease. Cron and Kanban use this path heavily.
- **Upstream 0.20.1:** emits finalize notification and cleanup but does not persist `end_session(..., cli_close)`.
- **Minimal delta:** one helper and one guarded call; failures log but do not bypass remaining cleanup.
- **Retirement trigger:** upstream persists equivalent final-tip terminal state on every one-shot exit path.

## LP-010 — MCP RPC serialization

- **Status:** UPSTREAM-ABSORBED.
- **Upstream evidence:** per-server `_rpc_lock`; tool calls, list tools/resources/prompts and reads serialize; active RPC suppresses recycle paths.
- **Validation:** official-target MCP regression included in the 164-test absorbed-patch suite.
- **Rule:** never port the old local implementation.

## LP-011 — DingTalk local file/audio delivery and final status

- **Status:** ACTIVE-SOURCE.
- **File / symbols:** `plugins/platforms/dingtalk/adapter.py`, OpenAPI token/media upload, staff recipient resolution, `sampleFile`, `sampleAudio`, `sendStatus`.
- **Production invariant:** a locally generated document/audio result is delivered to the actual DingTalk user and a final status is sent; API success is validated from response body, not HTTP status alone.
- **Upstream 0.20.1:** local document send explicitly returns unsupported; no complete sampleFile/sampleAudio/sendStatus path.
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
- **Upstream evidence:** `create_task` records both `created` and `blocked(reason=initial_status)` transactionally.
- **Validation:** official-target sticky-block regression included in the 164-test suite.
- **Rule:** never port the old local implementation.

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

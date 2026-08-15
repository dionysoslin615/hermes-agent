"""Use the Browser Use CLI 3.0 (https://browser-use.com) for browser automation

When browser.backend is "browser-use", the model gets ``browser_exec`` tool
instead of default browser tools
"""

import atexit
import json
import logging
import os
import re
import signal
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from utils import is_truthy_value

logger = logging.getLogger(__name__)

_BACKEND_KEY = "browser-use"
BACKEND_DISABLED = "off"

# Cloud daemon names become the BU_NAME env var
_SESSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")

_DEFAULT_TIMEOUT_S = 300
_MIN_TIMEOUT_S = 5
_MAX_TIMEOUT_S = 1800
_STDERR_CAP_CHARS = 4000

# Browser Use's official local mode attaches to an already-running desktop
# Chrome.  Unattended Kanban/Cron workers have no desktop browser to attach to,
# and must not share a fixed CDP port.  These globals hold one lazy, run-owned
# Chrome lease per worker process.  Interactive sessions keep the official
# attach-to-local-Chrome behaviour unchanged.
_RUN_OWNED_BROWSER_LOCK = threading.RLock()
_RUN_OWNED_BROWSER_PROC: Optional[subprocess.Popen] = None
_RUN_OWNED_BROWSER_ROOT: Optional[Path] = None
_RUN_OWNED_BROWSER_RUNTIME: Optional[Path] = None
_RUN_OWNED_BROWSER_WORKSPACE: Optional[Path] = None
_RUN_OWNED_BROWSER_URL = ""
_RUN_OWNED_BROWSER_NAME = ""
_RUN_OWNED_BROWSER_GUARDS = {
    "PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD": "1",
    "UV_PYTHON_DOWNLOADS": "never",
    "HERMES_SKIP_NODE_BOOTSTRAP": "1",
    "HERMES_DISABLE_LAZY_INSTALLS": "1",
}

# Filesystem-safe task ids for per-task workspace dirs.
_TASK_ID_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")

# Screenshot paths printed by capture_screenshot() in the exec output.
# Two alternatives: POSIX absolute (/tmp/shot.png) and Windows drive-letter
# absolute (C:\Users\...\shot.png or C:/Users/.../shot.png). Browser Use on
# Windows prints native paths — the POSIX-only pattern silently dropped them
# and screenshot_path / the multimodal attach never fired (#83884).
_IMAGE_PATH_RE = re.compile(
    r"((?:[A-Za-z]:[\\/]|/)[^\s\"']+?\.(?:png|jpe?g|webp))", re.IGNORECASE
)

# http(s) URL literals in exec code checked against browser_navigate's policy
_URL_RE = re.compile(r"https?://[^\s'\"\\)]+", re.IGNORECASE)


def _blocked_url_in_code(code: str) -> Optional[str]:
    """Return an error if a URL literal fails the built-in navigation checks."""
    from tools.browser_tool import evaluate_url_safety

    for url in _URL_RE.findall(code or ""):
        err = evaluate_url_safety(url)
        if err:
            return err.get("error", "Blocked: unsafe URL")
    return None


def _base_subprocess_env() -> dict:
    from tools.browser_tool import _build_browser_env

    env = _build_browser_env()
    env.setdefault("ANONYMIZED_TELEMETRY", "false")
    return env


def _run_owned_browser_requested(env: dict) -> bool:
    """Whether this unattended worker needs a private local Chrome lease."""
    if env.get("BU_CDP_WS") or env.get("BU_CDP_URL"):
        return False
    if os.environ.get("BU_CDP_WS") or os.environ.get("BU_CDP_URL"):
        return False
    return _is_unattended_browser_worker()


def _is_unattended_browser_worker() -> bool:
    return bool(os.environ.get("HERMES_KANBAN_TASK")) or is_truthy_value(
        os.environ.get("HERMES_RUN_OWNED_BROWSER"), default=False
    )


def _apply_run_owned_browser_guards(env: dict) -> None:
    """Disable every supported lazy/browser dependency installer."""
    env.update(_RUN_OWNED_BROWSER_GUARDS)


def _run_owned_child_setup() -> None:
    """Bind Chrome to the worker lifetime without leaving its process group.

    Kanban timeout handling terminates the worker process group. Chrome must
    inherit that group so a timed-out task cannot strand a detached browser.
    """
    if sys.platform.startswith("linux"):
        try:
            import ctypes

            libc = ctypes.CDLL(None)
            libc.prctl(1, signal.SIGKILL, os.getppid(), 0, 0)
        except Exception:
            pass


def _run_owned_chrome_args(env: dict) -> list[str]:
    """Return operator Chrome args without lease-conflicting switches."""
    raw = str(env.get("AGENT_BROWSER_ARGS") or os.environ.get("AGENT_BROWSER_ARGS") or "")
    blocked = ("--remote-debugging-port", "--remote-debugging-address", "--user-data-dir")
    args = [part.strip() for part in raw.split(",") if part.strip()]
    args = [arg for arg in args if not arg.startswith(blocked)]
    if not any(arg == "--no-sandbox" for arg in args):
        try:
            from tools.browser_tool import _needs_chromium_sandbox_bypass

            if _needs_chromium_sandbox_bypass():
                args.append("--no-sandbox")
        except Exception:
            pass
    if not any(arg == "--disable-dev-shm-usage" for arg in args):
        args.append("--disable-dev-shm-usage")
    return args


def _run_owned_endpoint_live(url: str) -> bool:
    try:
        port = int(url.rsplit(":", 1)[-1])
        socket.create_connection(("127.0.0.1", port), timeout=0.4).close()
        with urllib.request.urlopen(f"{url}/json/version", timeout=1.0) as response:
            return response.status == 200
    except Exception:
        return False


def _cleanup_run_owned_browser() -> None:
    """Stop the task's Browser Use daemon, Chrome process group and profile."""
    global _RUN_OWNED_BROWSER_PROC, _RUN_OWNED_BROWSER_ROOT, _RUN_OWNED_BROWSER_RUNTIME
    global _RUN_OWNED_BROWSER_WORKSPACE
    global _RUN_OWNED_BROWSER_URL, _RUN_OWNED_BROWSER_NAME

    with _RUN_OWNED_BROWSER_LOCK:
        proc = _RUN_OWNED_BROWSER_PROC
        root = _RUN_OWNED_BROWSER_ROOT
        runtime = _RUN_OWNED_BROWSER_RUNTIME
        workspace = _RUN_OWNED_BROWSER_WORKSPACE
        name = _RUN_OWNED_BROWSER_NAME
        _RUN_OWNED_BROWSER_PROC = None
        _RUN_OWNED_BROWSER_ROOT = None
        _RUN_OWNED_BROWSER_RUNTIME = None
        _RUN_OWNED_BROWSER_WORKSPACE = None
        _RUN_OWNED_BROWSER_URL = ""
        _RUN_OWNED_BROWSER_NAME = ""

    if name:
        try:
            cmd = _find_cli()
            if cmd:
                stop_env = _base_subprocess_env()
                stop_env["BU_NAME"] = name
                if runtime is not None:
                    stop_env["BH_RUNTIME_DIR"] = str(runtime)
                subprocess.run(
                    [*cmd, "--reload"], stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, timeout=10, env=stop_env,
                )
        except Exception:
            pass
    if proc is not None and proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    if root is not None:
        shutil.rmtree(root, ignore_errors=True)
    if runtime is not None:
        shutil.rmtree(runtime, ignore_errors=True)
    if workspace is not None:
        shutil.rmtree(workspace, ignore_errors=True)


def _set_run_owned_browser_workspace(workspace: str) -> None:
    """Bind Browser Use's task workspace to the unattended lease cleanup."""
    global _RUN_OWNED_BROWSER_WORKSPACE
    with _RUN_OWNED_BROWSER_LOCK:
        if _RUN_OWNED_BROWSER_PROC is not None:
            _RUN_OWNED_BROWSER_WORKSPACE = Path(workspace)


def _ensure_run_owned_browser(env: dict, task_id: Optional[str]) -> Optional[str]:
    """Attach an unattended worker to a private Browser Use runtime.

    A worker that already has an operator-owned CDP endpoint still needs a
    private ``BH_RUNTIME_DIR``/``BU_NAME``.  Browser Use otherwise starts a
    detached shared harness daemon which can outlive the worker, keep sandbox
    stdio pipes open, and prevent the owning runner from reaping its process.

    Workers without an endpoint additionally receive one lazy, random-port
    Chrome lease. Returns an actionable error string on failure, otherwise
    None.
    """
    global _RUN_OWNED_BROWSER_PROC, _RUN_OWNED_BROWSER_ROOT, _RUN_OWNED_BROWSER_RUNTIME
    global _RUN_OWNED_BROWSER_URL, _RUN_OWNED_BROWSER_NAME

    if not _is_unattended_browser_worker():
        return None
    _apply_run_owned_browser_guards(env)

    external_endpoint = str(env.get("BU_CDP_URL") or env.get("BU_CDP_WS") or "")
    if external_endpoint:
        with _RUN_OWNED_BROWSER_LOCK:
            if (
                _RUN_OWNED_BROWSER_RUNTIME is not None
                and _RUN_OWNED_BROWSER_NAME
                and _RUN_OWNED_BROWSER_URL == external_endpoint
            ):
                env["BU_NAME"] = _RUN_OWNED_BROWSER_NAME
                env["BH_RUNTIME_DIR"] = str(_RUN_OWNED_BROWSER_RUNTIME)
                return None

            _cleanup_run_owned_browser()
            # Browser Harness binds ``bu.sock`` below BH_RUNTIME_DIR.  Keep the
            # complete AF_UNIX path short (Linux sun_path=108; macOS=104), just
            # like the branch below that also launches Chrome.  A deep
            # profile-local HERMES_HOME path is not safe here.
            name = f"hbu_{os.getpid()}"
            runtime = Path(tempfile.gettempdir()) / name
            shutil.rmtree(runtime, ignore_errors=True)
            runtime.mkdir(mode=0o700)

            _RUN_OWNED_BROWSER_PROC = None
            _RUN_OWNED_BROWSER_ROOT = None
            _RUN_OWNED_BROWSER_RUNTIME = runtime
            _RUN_OWNED_BROWSER_WORKSPACE = None
            _RUN_OWNED_BROWSER_URL = external_endpoint
            _RUN_OWNED_BROWSER_NAME = name
            env["BU_NAME"] = name
            env["BH_RUNTIME_DIR"] = str(runtime)
            return None

    if not _run_owned_browser_requested(env):
        return None
    with _RUN_OWNED_BROWSER_LOCK:
        if (
            _RUN_OWNED_BROWSER_PROC is not None
            and _RUN_OWNED_BROWSER_PROC.poll() is None
            and _run_owned_endpoint_live(_RUN_OWNED_BROWSER_URL)
        ):
            env["BU_CDP_URL"] = _RUN_OWNED_BROWSER_URL
            env["BU_NAME"] = _RUN_OWNED_BROWSER_NAME
            if _RUN_OWNED_BROWSER_RUNTIME is not None:
                env["BH_RUNTIME_DIR"] = str(_RUN_OWNED_BROWSER_RUNTIME)
            return None

        _cleanup_run_owned_browser()
        from hermes_constants import get_default_hermes_root, get_hermes_home

        chrome = Path(
            os.environ.get("AGENT_BROWSER_EXECUTABLE_PATH")
            or get_default_hermes_root() / "services/browser-runtime/bin/chrome"
        )
        if not chrome.is_file() or not os.access(chrome, os.X_OK):
            return f"Managed Chrome is not executable at {chrome}"

        raw_id = task_id or os.environ.get("HERMES_KANBAN_TASK") or f"worker-{os.getpid()}"
        safe_id = _TASK_ID_SAFE_RE.sub("_", str(raw_id)).strip("._-") or "worker"
        safe_id = safe_id[-32:]
        root = get_hermes_home() / "tmp/run-owned-browser" / f"{safe_id}-{os.getpid()}"
        profile = root / "profile"
        profile.mkdir(parents=True, exist_ok=False)
        stderr_path = root / "chrome.stderr.log"
        args = [
            str(chrome),
            "--headless=new",
            "--remote-debugging-address=127.0.0.1",
            "--remote-debugging-port=0",
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--disable-component-update",
            "--disable-features=Translate,MediaRouter",
            "--window-size=1280,900",
            *_run_owned_chrome_args(env),
            "about:blank",
        ]
        launch_env = dict(env)
        launch_env.update(_RUN_OWNED_BROWSER_GUARDS)
        try:
            with stderr_path.open("wb") as stderr_file:
                proc = subprocess.Popen(
                    args, stdout=subprocess.DEVNULL, stderr=stderr_file,
                    env=launch_env, preexec_fn=_run_owned_child_setup,
                )
        except Exception as e:
            shutil.rmtree(root, ignore_errors=True)
            return f"Failed to launch managed Chrome: {e}"

        port_file = profile / "DevToolsActivePort"
        deadline = time.monotonic() + 15
        url = ""
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                break
            try:
                port = int(port_file.read_text(encoding="utf-8").splitlines()[0])
                if port in range(9222, 9229):
                    raise RuntimeError(f"Chrome selected reserved fixed CDP port {port}")
                candidate = f"http://127.0.0.1:{port}"
                if _run_owned_endpoint_live(candidate):
                    url = candidate
                    break
            except (OSError, ValueError, IndexError):
                pass
            time.sleep(0.1)
        if not url:
            try:
                proc.kill()
            except Exception:
                pass
            detail = ""
            try:
                detail = stderr_path.read_text(encoding="utf-8", errors="replace")[-1000:]
            except OSError:
                pass
            shutil.rmtree(root, ignore_errors=True)
            return f"Managed Chrome did not expose a random CDP endpoint: {detail}"

        # Browser Harness uses BU_NAME in AF_UNIX socket filenames. Keep both
        # the name and runtime root deliberately short (Linux sun_path=108).
        name = f"hbu_{os.getpid()}"
        runtime = Path(tempfile.gettempdir()) / name
        shutil.rmtree(runtime, ignore_errors=True)
        runtime.mkdir(mode=0o700)
        _RUN_OWNED_BROWSER_PROC = proc
        _RUN_OWNED_BROWSER_ROOT = root
        _RUN_OWNED_BROWSER_RUNTIME = runtime
        _RUN_OWNED_BROWSER_URL = url
        _RUN_OWNED_BROWSER_NAME = name
        env["BU_CDP_URL"] = url
        env["BU_NAME"] = name
        env["BH_RUNTIME_DIR"] = str(runtime)
        return None


atexit.register(_cleanup_run_owned_browser)


def _read_browser_cfg() -> dict:
    """Return the ``browser:`` config section, or {} on any failure."""
    try:
        from hermes_cli.config import cfg_get, read_raw_config

        cfg = cfg_get(read_raw_config(), "browser", default={})
        return cfg if isinstance(cfg, dict) else {}
    except Exception as e:
        logger.debug("Could not read browser config section: %s", e)
        return {}


def get_browser_backend() -> str:
    """Return the configured browser backend key ("" = unset → default).

    YAML 1.1 parses an unquoted ``off`` as boolean False — a hand-edited
    ``backend: off`` must mean BACKEND_DISABLED, not "unset". (True has no
    sensible backend meaning; normalize it to unset.)
    """
    raw = _read_browser_cfg().get("backend")
    if raw is False:
        return BACKEND_DISABLED
    if raw is True:
        return ""
    return str(raw or "").strip().lower()


def is_legacy_browser_use_cloud_config(browser_cfg: dict) -> bool:
    """True for pre-CLI direct-API Browser Use cloud configs"""
    if not isinstance(browser_cfg, dict):
        return False
    if browser_cfg.get("backend"):
        return False  # an explicit backend choice wins
    provider = str(browser_cfg.get("cloud_provider") or "").strip().lower()
    if provider not in {"browser-use", ""}:
        return False  # explicit local/Browserbase/… choices win
    if is_truthy_value(browser_cfg.get("use_gateway"), default=False):
        return False
    # Camofox is selected via env var, not cloud_provider — a Camofox user
    # with a stray BROWSER_USE_API_KEY must keep their explicit choice.
    try:
        from tools.browser_camofox import is_camofox_mode

        if is_camofox_mode():
            return False
    except Exception as e:
        logger.debug("Camofox activity check failed during migration: %s", e)
    return bool(os.getenv("BROWSER_USE_API_KEY"))


def is_browser_use_cli_mode() -> bool:
    """True when the Browser Use CLI replaces the built-in browser stack.

    Browser Use mode is the DEFAULT: an unset ``browser.backend`` ("") enables
    it whenever the browser-use CLI is runnable (installed binary or uvx).
    Set ``browser.backend: off`` (or ``/browser use off``) for the built-in
    browser_* tools.

    Camofox always falls back to the built-in tools regardless of
    ``browser.backend`` — it is Firefox-based with a custom HTTP API and no
    CDP surface, so the CDP-only browser-use harness cannot drive it.
    """
    try:
        from tools.browser_camofox import is_camofox_mode

        if is_camofox_mode():
            return False
    except Exception as e:
        logger.debug("Camofox activity check failed: %s", e)
    backend = get_browser_backend()
    if backend:
        return backend == _BACKEND_KEY
    if is_legacy_browser_use_cloud_config(_read_browser_cfg()):
        return True
    # Default (backend unset): Browser Use mode when the CLI can run at all;
    # otherwise keep the built-in tools so browsing never silently breaks.
    return _find_cli() is not None


_NOTICE_STAMP_NAME = ".browser_use_default_notice"
_NOTICE_INTERVAL_S = 24 * 3600


def default_downgrade_notice() -> Optional[str]:
    """One-line notice when the default Browser Use backend silently downgraded.

    Returns the notice string when ``browser.backend`` is unset (Browser Use
    would be the default) but the CLI is not runnable, so the session fell
    back to the built-in browser tools. Rate-limited to once per 24h via a
    stamp file so it nudges without nagging. Returns ``None`` otherwise.
    """
    try:
        if get_browser_backend():
            return None  # explicit choice — nothing downgraded
        try:
            from tools.browser_camofox import is_camofox_mode

            if is_camofox_mode():
                return None
        except Exception:
            pass
        if _find_cli() is not None:
            return None

        from hermes_constants import get_hermes_home

        stamp = Path(get_hermes_home()) / "cache" / _NOTICE_STAMP_NAME
        try:
            if 0 <= time.time() - stamp.stat().st_mtime < _NOTICE_INTERVAL_S:
                return None
        except OSError:
            pass
        try:
            stamp.parent.mkdir(parents=True, exist_ok=True)
            stamp.touch()
        except OSError:
            pass
        return (
            "Browser Use CLI not found — using the built-in browser tools. "
            "Run `hermes tools` (Browser Automation → Browser Use) to install it, "
            "or `browser.backend: off` in config.yaml to silence this."
        )
    except Exception as e:  # pragma: no cover — a notice must never break startup
        logger.debug("browser-use downgrade notice failed: %s", e)
        return None


def _managed_bin_dir() -> Optional[str]:
    """Hermes' own bin dir ($HERMES_HOME/bin) — where install.sh puts uv/uvx
    and where install_cli() links the browser-use binary."""
    try:
        from hermes_constants import get_hermes_home

        return str(Path(get_hermes_home()) / "bin")
    except Exception as e:  # pragma: no cover — defensive
        logger.debug("Could not resolve managed bin dir: %s", e)
        return None


def _shared_browser_runtime_bin() -> Optional[str]:
    """Deployment-wide managed browser CLI directory shared by all profiles."""
    try:
        from hermes_constants import get_default_hermes_root

        return str(get_default_hermes_root() / "services/browser-runtime/bin")
    except Exception as e:  # pragma: no cover — defensive
        logger.debug("Could not resolve shared browser runtime bin dir: %s", e)
        return None


def _find_cli() -> Optional[List[str]]:
    """Locate the browser-use CLI, or None when it can't be run.

    Prefers an installed browser-use binary (PATH, deployment-wide managed
    browser runtime, then $HERMES_HOME/bin). Interactive sessions retain the
    upstream uvx fallback. Unattended Cron/Kanban workers fail closed instead:
    uvx may lazily download code and violates their frozen-runtime contract.
    """
    bin_dir = _managed_bin_dir()
    shared_bin = _shared_browser_runtime_bin()
    for probe_path in (None, shared_bin, bin_dir):
        if probe_path is None or probe_path:
            direct = shutil.which("browser-use", path=probe_path)
            if direct:
                return [direct]
    if _is_unattended_browser_worker():
        return None
    for probe_path in (None, bin_dir):
        if probe_path is None or probe_path:
            uvx = shutil.which("uvx", path=probe_path)
            if uvx:
                return [uvx, "browser-use"]
    return None


def install_cli(timeout_s: int = 600) -> Tuple[bool, str]:
    """Install the browser-use CLI persistently via ``uv tool install``.

    Resolution order for uv: Hermes' managed uv (bootstrapped on demand via
    ``hermes_cli.managed_uv.ensure_uv``) → uv on PATH. The binary is linked
    into ``$HERMES_HOME/bin`` (``UV_TOOL_BIN_DIR``) so ``_find_cli()``
    resolves it for every profile without touching the user's PATH.

    Returns ``(ok, message)`` — never raises.
    """
    direct = shutil.which("browser-use")
    if direct:
        return True, f"browser-use CLI already installed ({direct})"
    shared_bin = _shared_browser_runtime_bin()
    if shared_bin:
        shared = shutil.which("browser-use", path=shared_bin)
        if shared:
            return True, f"browser-use CLI already installed ({shared})"
    bin_dir = _managed_bin_dir()
    if bin_dir:
        managed = shutil.which("browser-use", path=bin_dir)
        if managed:
            return True, f"browser-use CLI already installed ({managed})"

    uv_bin: Optional[str] = None
    try:
        from hermes_cli.managed_uv import ensure_uv

        uv_bin = str(ensure_uv() or "") or None
    except Exception as e:
        logger.debug("Managed uv bootstrap unavailable: %s", e)
    if not uv_bin:
        uv_bin = shutil.which("uv")
    if not uv_bin:
        return False, (
            "uv is not available and could not be bootstrapped. Install uv "
            "(https://docs.astral.sh/uv/) and run `uv tool install browser-use`."
        )

    env = dict(os.environ)
    env["UV_NO_CONFIG"] = "1"
    if bin_dir:
        try:
            Path(bin_dir).mkdir(parents=True, exist_ok=True)
            env["UV_TOOL_BIN_DIR"] = bin_dir
        except OSError as e:
            logger.debug("Could not prepare %s: %s", bin_dir, e)

    try:
        result = subprocess.run(
            [uv_bin, "tool", "install", "browser-use"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return False, f"`uv tool install browser-use` timed out after {timeout_s}s"
    except Exception as e:
        return False, f"Failed to run `uv tool install browser-use`: {e}"

    if result.returncode != 0:
        tail = "\n".join(
            (result.stderr or result.stdout or "").strip().splitlines()[-3:]
        )
        return False, f"`uv tool install browser-use` failed:\n{tail}"

    found = _find_cli()
    if not found or len(found) != 1:
        return False, (
            "install reported success but the browser-use binary is still "
            "not resolvable — run `uv tool install browser-use` manually"
        )
    return True, f"browser-use CLI installed ({found[0]})"


def _workspace_dir(task_id: Optional[str]) -> Optional[str]:
    """Stable per-task scratch dir that persists across browser_exec calls"""
    existing = os.environ.get("BH_AGENT_WORKSPACE")
    if existing:
        return existing
    try:
        from pathlib import Path

        from hermes_constants import get_hermes_home

        safe = _TASK_ID_SAFE_RE.sub("_", str(task_id or "default"))[:80] or "default"
        path = Path(get_hermes_home()) / "cache" / "browser-use" / "workspace" / safe
        path.mkdir(parents=True, exist_ok=True)
        return str(path)
    except Exception as e:
        logger.debug("browser_exec workspace unavailable: %s", e)
        return None


def _find_screenshot(stdout: str, since: float) -> Optional[str]:
    """Return the last screenshot path printed during this exec, or None.

    Only accepts files that exist and were written after the exec started
    """
    for path in reversed(_IMAGE_PATH_RE.findall(stdout or "")):
        try:
            if os.path.isfile(path) and os.path.getmtime(path) >= since - 1:
                return path
        except OSError:
            continue
    return None


def _native_screenshot_result(result: Dict[str, Any], path: str) -> Optional[Dict[str, Any]]:
    """Build a multimodal tool result attaching path for vision models"""
    try:
        from pathlib import Path

        from tools.vision_tools import (
            _resize_image_for_vision,
            _should_use_native_vision_fast_path,
        )

        if not _should_use_native_vision_fast_path():
            return None
        data_url = _resize_image_for_vision(Path(path))
        text = json.dumps(result, ensure_ascii=False)
        return {
            "_multimodal": True,
            "content": [
                {
                    "type": "text",
                    "text": (
                        text
                        + "\n\nThe screenshot from this call is attached — "
                        "inspect it with your native vision."
                    ),
                },
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
            "text_summary": text,
            "meta": {"screenshot_path": path, "native_vision": True},
        }
    except Exception as e:
        logger.debug("Native screenshot attach failed (falling back to text): %s", e)
        return None


def _resolve_backend_cdp(env: dict, task_id: Optional[str]) -> Optional[str]:
    """Point the harness at the configured browser backend's CDP endpoint.

    Resolution order (first hit wins):

    1. ``BU_CDP_WS`` / ``BU_CDP_URL`` already in the environment — explicit
       user/operator override, passed through untouched.
    2. ``BROWSER_CDP_URL`` env / ``browser.cdp_url`` config override — the
       ``/browser connect`` path, same precedence the built-in tools honor.
    3. A configured cloud browser provider (Browserbase, Firecrawl, Nous
       gateway/Browser Use cloud, …): reuse the legacy stack's
       ``_get_session_info()`` so browser_exec shares the SAME provider
       session machinery — per-task session cache, expiry replacement,
       inactivity reaper, and atexit cleanup — instead of duplicating it.
    4. Nothing configured: return None; the harness attaches to local
       Chrome (or Browser Use cloud via BU_AUTOSPAWN for legacy configs).

    Returns an error string on provider failure, None on success.
    """
    if env.get("BU_CDP_WS") or env.get("BU_CDP_URL"):
        return None

    try:
        from tools.browser_tool import (
            _get_cdp_override,
            _get_cloud_provider,
            _get_session_info,
        )
    except Exception as e:  # pragma: no cover — stubbed browser_tool in tests
        logger.debug("browser_tool backend resolution unavailable: %s", e)
        return None

    try:
        override = _get_cdp_override()
    except Exception:
        override = ""
    if override:
        env["BU_CDP_URL" if override.startswith(("http://", "https://")) else "BU_CDP_WS"] = override
        return None

    try:
        provider = _get_cloud_provider()
    except Exception as e:
        logger.debug("Cloud provider lookup failed: %s", e)
        provider = None
    if provider is None:
        return None

    # Browser Use direct-API configs: the CLI talks to Browser Use cloud
    # natively (BU_AUTOSPAWN / auth login) — routing through the legacy
    # provider here would just create a second, redundant session. The
    # Nous-gateway variant (use_gateway: true) DOES resolve through the
    # provider: the gateway provisions the cloud browser server-side and
    # returns its CDP URL, giving subscribers CLI mode with no raw key.
    provider_key = str(getattr(provider, "name", "") or "").strip().lower()
    if provider_key == _BACKEND_KEY and not is_truthy_value(
        _read_browser_cfg().get("use_gateway"), default=False
    ):
        return None

    try:
        session_info = _get_session_info(task_id or "browser-exec-default")
    except Exception as e:
        return (
            f"Cloud browser provider {type(provider).__name__} failed to "
            f"provide a session: {e}. Fix the provider configuration or "
            "switch backends via `hermes tools` → Browser Automation."
        )
    cdp = str((session_info or {}).get("cdp_url") or "")
    if not cdp:
        return (
            f"Cloud browser provider {type(provider).__name__} returned no "
            "CDP endpoint, so Browser Use mode cannot drive it. Switch to "
            "the built-in browser tools for this provider."
        )
    env["BU_CDP_URL" if cdp.startswith(("http://", "https://")) else "BU_CDP_WS"] = cdp
    return None


def browser_exec(
    code: str,
    session: str = "",
    timeout_s: int = _DEFAULT_TIMEOUT_S,
    task_id: Optional[str] = None,
):
    """Run Python code through the browser-use CLI, and return its output"""
    from tools.registry import tool_error, tool_result

    if not code or not code.strip():
        return tool_error("No code provided. Pass Python that uses the pre-imported helpers, e.g. new_tab(\"https://example.com\") then print(page_info()).")

    blocked = _blocked_url_in_code(code)
    if blocked:
        return tool_error(blocked)

    cmd = _find_cli()
    if not cmd:
        return tool_error(
            "browser-use CLI not found on PATH, and uvx is unavailable for a "
            "zero-install run. Install it with `uv tool install browser-use` "
            "(or `pipx install browser-use`), then run `browser-use --doctor` "
            "to verify the setup."
        )

    env = _base_subprocess_env()
    if session:
        if not _SESSION_RE.match(session):
            return tool_error(
                f"Invalid session name {session!r}: use 1-64 letters, digits, "
                "dashes, or underscores (e.g. 'r7k2')."
            )
        env["BU_NAME"] = session
    else:
        # Route through the configured browser backend (Browserbase,
        # Firecrawl, Nous gateway, CDP override, …). Explicit BU_NAME cloud
        # sessions manage their own browser and skip backend resolution.
        backend_err = _resolve_backend_cdp(env, task_id)
        if backend_err:
            return tool_error(backend_err)
        run_owned_err = _ensure_run_owned_browser(env, task_id)
        if run_owned_err:
            return tool_error(run_owned_err)

    workspace = _workspace_dir(task_id)
    if workspace:
        env["BH_AGENT_WORKSPACE"] = workspace
        _set_run_owned_browser_workspace(workspace)

    # BU_AUTOSPAWN makes the CLI start a Browser Use cloud browser when no
    # local Chrome/CDP endpoint is reachable (their API key authenticates it)
    if "BU_AUTOSPAWN" not in env and is_legacy_browser_use_cloud_config(_read_browser_cfg()):
        env["BU_AUTOSPAWN"] = "1"

    try:
        timeout = max(_MIN_TIMEOUT_S, min(int(timeout_s), _MAX_TIMEOUT_S))
    except (TypeError, ValueError):
        timeout = _DEFAULT_TIMEOUT_S

    # Windows: hide the console the .cmd shim would flash (as browser_tool does)
    popen_extra: dict = {}
    if os.name == "nt":
        try:
            from hermes_cli._subprocess_compat import windows_hide_flags

            popen_extra["creationflags"] = windows_hide_flags()
            _si = subprocess.STARTUPINFO()
            _si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            popen_extra["startupinfo"] = _si
        except Exception as e:
            logger.debug("Windows hide-flags unavailable: %s", e)

    started = time.time()
    stdout_text = ""
    stderr_text = ""
    try:
        # Browser Harness starts a persistent daemon. That daemon can inherit
        # stdout/stderr, so PIPE + communicate() would wait for EOF long after
        # the one-shot CLI process exited. Private temp files preserve complete
        # output without tying tool completion to daemon descriptor lifetime.
        with tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace") as stdout_file, tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace") as stderr_file:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=stdout_file,
                stderr=stderr_file,
                text=True,
                env=env,
                **popen_extra,
            )
            try:
                proc.communicate(input=code, timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
                return tool_error(
                    f"browser-use exec timed out after {timeout}s. The daemon may "
                    "still be working; retry with a larger timeout_s (max "
                    f"{_MAX_TIMEOUT_S}), or split the work into several calls that "
                    "append to workspace files — anything already written to the "
                    "workspace is preserved."
                )
            stdout_file.flush()
            stderr_file.flush()
            stdout_file.seek(0)
            stderr_file.seek(0)
            stdout_text = stdout_file.read()
            stderr_text = stderr_file.read()
    except OSError as e:
        return tool_error(f"Failed to launch browser-use CLI: {e}")

    result = {
        "success": proc.returncode == 0,
        "exit_code": proc.returncode,
        "output": stdout_text,
    }
    if workspace:
        result["workspace"] = workspace
    if session:
        result["session"] = session
    stderr = stderr_text.strip()
    if stderr:
        if len(stderr) > _STDERR_CAP_CHARS:
            stderr = stderr[:_STDERR_CAP_CHARS] + "\n… (stderr truncated)"
        result["stderr"] = stderr

    screenshot = _find_screenshot(stdout_text, started)
    if screenshot:
        result["screenshot_path"] = screenshot
        native = _native_screenshot_result(result, screenshot)
        if native is not None:
            return native
    return tool_result(result)


# The tool description is the CLI's skill, fetched from browser-use skill
_HEADER_BASE = (
    "Drive a real web browser via the Browser Use CLI. The `code` argument "
    "is piped verbatim to the `browser-use` CLI on stdin and executed as "
    "full Python (standard library available) with the CLI's pre-imported "
    "browser helpers; stdout comes back in the result. Start `code` with a "
    "one-line comment describing the step for the user in plain, "
    "non-technical language, max 60 chars (e.g. `# Searching Amazon for "
    "paper towels`) — the UI displays it as the step label.\n\n"
    "STATE: the browser session and the workspace persist across calls; "
    "Python variables do NOT (each call is a fresh interpreter). The "
    "workspace is a stable directory — path in $BH_AGENT_WORKSPACE and "
    "returned as `workspace` in every result. For multi-item tasks "
    "('collect all N products / every entry / the full table'), append each "
    "batch to a JSON/CSV file in the workspace as you go, then read it back "
    "to assemble the final answer; define reusable functions in "
    "agent_helpers.py there — the harness auto-imports it into every call. "
    "Do aggregation in code, not in your head: dedupe, count, sort, and "
    "format with Python inside the exec. Before giving a final answer on a "
    "multi-item task, verify the collected count against what was asked "
    "and go back for anything missing.\n\n"
    "Batch each sub-procedure (navigate, wait, extract, act) into one call "
    "— do not spend a call per action — but for long extractions prefer "
    "several medium calls that append to workspace files over one giant "
    "call, so progress survives timeouts. For a named cloud browser, pass "
    "session=<name> (never BU_NAME env syntax)."
)

_HEADER_VISION = (
    " Screenshots are attached to your context automatically: when the exec "
    "output contains a capture_screenshot() path, the image arrives with "
    "this tool's result and you inspect it directly with your own vision — "
    "never send browser screenshots to a separate vision tool."
)

_HEADER_TEXT_ONLY = (
    " Your model cannot view images, so work text-first: page_info() for "
    "state, js() for reading/extracting DOM text, fill_input(selector, "
    "text) for inputs, and js(\"document.querySelector('…').click()\") for "
    "clicks — skip the screenshot-driven workflow described below."
)

_DESCRIPTION_HEADER = _HEADER_BASE  # back-compat alias for external imports

# NOTE: browser_exec is additionally gated at tool-definition time — sessions
# whose resolved toolsets do not include ``terminal`` never see it (see
# model_tools._compute_tool_definitions). The check_fn registered below only
# answers "is Browser Use mode configured"; surface policy lives with the
# session, not in the process-wide TTL-cached check_fn.


def _description_header() -> str:
    """Header tailored to whether the active model can see images natively"""
    try:
        from tools.vision_tools import _should_use_native_vision_fast_path

        if _should_use_native_vision_fast_path():
            return _HEADER_BASE + _HEADER_VISION
    except Exception:
        pass
    return _HEADER_BASE + _HEADER_TEXT_ONLY

_skill_text_cache: Optional[str] = None
_skill_text_fetched = False

# Pinned quick-reference for the CLI's pre-imported helpers. Replaces the
# live ``browser-use skill`` fetch: embedding whatever text the installed CLI
# version prints would ship uncontrolled third-party content into every
# session's system-side schema (version drift across machines, supply-chain
# exposure, and a byte-unstable prompt). A/B benchmarked Aug 2026 (108 runs,
# opus-4.8 + kimi-k3, 6 multi-step tasks x 3 reps): header-only schema went
# 36/36 vs 36/36 for the full skill dump at ~equal tokens (-60% vs the
# legacy browser_* toolset either way). The pinned digest below keeps the
# first-call reliability of the helper names without the 7.7KB dump.
_HELPERS_DIGEST = (
    "\n\nHELPERS (pre-imported): new_tab(url) opens/navigates (use for the "
    "FIRST navigation), goto_url(url) navigates the current tab, "
    "wait_for_load() after navigation, page_info() summarizes the current "
    "page state, js(expr) evaluates a JS expression and returns its value "
    "(js('document.title'); wrap function bodies as js('(() => {...})()') — "
    "a bare '() => {...}' returns the function itself, uncalled), "
    "fill_input(selector, text) types into inputs, click_at_xy(x, y) clicks "
    "viewport coordinates, capture_screenshot() saves and prints a "
    "screenshot path, cdp('Domain.method', **kwargs) is raw CDP — "
    "cdp('Accessibility.getFullAXTree')['nodes'] lists every element's "
    "role/name/backendDOMNodeId (filter in Python before printing; it is "
    "thousands of nodes), then cdp('DOM.getBoxModel', backendNodeId=n) gives "
    "click coordinates. ensure_real_tab() recovers from a stale/internal "
    "tab. Login walls: stop and ask the user; never guess credentials."
)


def _cli_skill_text() -> str:
    """Deprecated: always returns "" — the schema uses the pinned header.

    Kept so tests and any external callers keep importing a stable symbol;
    see _HELPERS_DIGEST for the rationale (benchmark-backed removal of the
    live ``browser-use skill`` fetch).
    """
    return _skill_text_cache or ""


def _dynamic_schema_overrides() -> dict:
    return {"description": _description_header() + _HELPERS_DIGEST}


BROWSER_EXEC_SCHEMA = {
    "name": "browser_exec",
    # Static fallback, used only when the CLI (and uvx) is unavailable
    "description": (
        _HEADER_BASE
        + _HELPERS_DIGEST
        + "\n\n(The browser-use CLI is not installed yet. Install it with "
        "`uv tool install browser-use`.)"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute using the pre-imported browser helpers. Use print(...) for any data you need back.",
            },
            "session": {
                "type": "string",
                "description": "Named cloud browser session (sets BU_NAME). Omit for the local default daemon. Use the same name you passed to start_remote_daemon().",
            },
            "timeout_s": {
                "type": "integer",
                "description": f"Max seconds to wait for the code to finish (default {_DEFAULT_TIMEOUT_S}, max {_MAX_TIMEOUT_S}).",
                "default": _DEFAULT_TIMEOUT_S,
            },
        },
        "required": ["code"],
    },
}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
from tools.registry import registry

registry.register(
    name="browser_exec",
    toolset="browser-use",
    schema=BROWSER_EXEC_SCHEMA,
    handler=lambda args, **kw: browser_exec(
        code=args.get("code", ""),
        session=args.get("session", "") or "",
        timeout_s=args.get("timeout_s", _DEFAULT_TIMEOUT_S),
        task_id=kw.get("task_id"),
    ),
    check_fn=is_browser_use_cli_mode,
    dynamic_schema_overrides=_dynamic_schema_overrides,
    emoji="🌐",
)

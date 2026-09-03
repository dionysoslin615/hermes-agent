"""Use the Browser Use CLI 3.0 (https://browser-use.com) for browser automation

When browser.backend is "browser-use", the model gets ``browser_exec`` tool
instead of default browser tools
"""

import atexit
import contextlib
import importlib
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
from typing import Any, Callable, Dict, List, Optional, Tuple

from hermes_constants import get_hermes_home
from utils import is_truthy_value

logger = logging.getLogger(__name__)

_BACKEND_KEY = "browser-use"
BACKEND_DISABLED = "off"

# Cloud daemon names become the BU_NAME env var
_SESSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")

# Set on the env dict by the CDP resolvers when the resolved browser is EXCLUSIVE to this named session
# (per-name provider / named BU cloud / Lightpanda). Popped before the subprocess launches — never exported.
_PRIVATE_BROWSER_SENTINEL = "_HERMES_BU_PRIVATE_BROWSER"

# Prepended to the model's code for named sessions on SHARED browsers (a /browser connect CDP override): the
# harness daemon attaches to the first existing page at startup, so two fresh named daemons can land on the
# SAME tab. Steering each onto a tab it created prevents clobbering. Runs once per daemon (marker keyed by
# BU_NAME + daemon pid).
_OWN_TAB_PREAMBLE = """\
# hermes: pin this named session to its own tab (once per daemon process)
def _hermes_ensure_own_tab():
    import os as _os, tempfile as _tf
    _name = _os.environ.get("BU_NAME", "default")
    try:
        # Key the marker by the daemon's pid so a daemon restart (which
        # re-attaches to the first shared page) re-pins automatically,
        # while agent-driven tab switches mid-session are left alone.
        from browser_harness import _ipc as _bipc
        _dpid = _bipc.pid_path(_name).read_text().strip() or "0"
    except Exception:
        _dpid = "0"
    _uid = _os.getuid() if hasattr(_os, "getuid") else 0
    _marker = _os.path.join(
        _tf.gettempdir(), "hermes-bu-owntab-%s-%s-%s" % (_uid, _name, _dpid)
    )
    if _os.path.exists(_marker):
        return
    try:
        # Force a fresh target: new_tab() would REUSE a blank current tab,
        # which is exactly the tab a sibling daemon may also hold.
        _tid = cdp("Target.createTarget", url="about:blank").get("targetId")
        if _tid:
            switch_tab(_tid)
    except Exception:
        pass  # best-effort: worst case is pre-fix behavior
    try:
        open(_marker, "w").close()
    except OSError:
        pass
_hermes_ensure_own_tab()
del _hermes_ensure_own_tab
"""

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

_TASK_ID_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")  # filesystem-safe task ids
# Screenshot paths printed by capture_screenshot(): POSIX or Windows drive-letter absolute.
_IMAGE_PATH_RE = re.compile(r"((?:[A-Za-z]:[\\/]|/)[^\s\"']+?\.(?:png|jpe?g|webp))", re.IGNORECASE)
# http(s) URL literals in exec code checked against browser_navigate's policy
_URL_RE = re.compile(r"https?://[^\s'\"\\)]+", re.IGNORECASE)
_FHS_BIN_DIRS = ("/usr/local/sbin", "/usr/local/bin", "/usr/sbin", "/usr/bin", "/sbin", "/bin")


def _quiet(fn: Callable[[], Any], default: Any, log_prefix: str = "") -> Any:
    """``fn()``, or ``default`` on any exception (debug-logged when ``log_prefix`` is set)."""
    try:
        return fn()
    except Exception as e:
        if log_prefix:
            logger.debug("%s: %s", log_prefix, e)
    return default


def _lazy_call(module: str, name: str, default: Any, log_prefix: str) -> Any:
    """Call ``module.name()`` resolved at call time (tests stub the module / patch the
    attribute); on any failure log ``log_prefix`` and return ``default``."""
    return _quiet(lambda: getattr(importlib.import_module(module), name)(), default, log_prefix)


def _camofox_active(context: str = "") -> bool:
    return _lazy_call("tools.browser_camofox", "is_camofox_mode", False, f"Camofox activity check failed{context}")


def _real_profile_consented() -> bool:
    return _lazy_call("tools.browser_tool_cloud", "_use_real_profile", False, "real-profile consent lookup failed")


def _set_cdp_env(env: dict, cdp: str) -> None:
    """Export a CDP endpoint under the BU_CDP_* contract (http(s) → URL, else WS)."""
    env["BU_CDP_URL" if cdp.startswith(("http://", "https://")) else "BU_CDP_WS"] = cdp


def _has_cdp_env(env: dict) -> bool:
    return bool(env.get("BU_CDP_WS") or env.get("BU_CDP_URL"))


def _export_session_cdp(env: dict, get_session_info: Callable[[str], Any], cache_key: str,
                        fail_msg: Callable[[Exception], str], no_cdp_msg: str) -> Optional[str]:
    """Export the CDP endpoint from ``get_session_info(cache_key)``; error string on failure / no CDP."""
    try:
        cdp = str((get_session_info(cache_key) or {}).get("cdp_url") or "")
    except Exception as e:
        return fail_msg(e)
    if not cdp:
        return no_cdp_msg
    _set_cdp_env(env, cdp)
    return None


def _blocked_url_in_code(code: str) -> Optional[str]:
    """Return an error if a URL literal fails the built-in navigation checks."""
    from tools.browser_tool import evaluate_url_safety
    return next((err.get("error", "Blocked: unsafe URL") for err in map(evaluate_url_safety, _URL_RE.findall(code or "")) if err), None)


def _base_subprocess_env() -> dict:
    from tools.browser_tool import _build_browser_env
    env = _build_browser_env()
    # The CLI runs under its own Python (uv tool / uvx); an inherited PYTHONPATH/PYTHONHOME
    # (Hermes's venv) wins over its site-packages → wrong-ABI C-extensions and a crash.
    # PYTHONPATH/PYTHONHOME inherited from the agent process point at Hermes's venv site-packages, and a
    # child interpreter honors them ahead of its own site-packages — so the CLI imports compiled
    # C-extensions (e.g. pydantic_core) built for the wrong interpreter and crashes on ABI mismatch (#83427,
    # #84841, #86006, #86104). Strip both — the CLI manages its own environment and never needs Hermes's
    # import path.
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env["PATH"] = _floor_subprocess_path(env.get("PATH", ""))
    env.setdefault("ANONYMIZED_TELEMETRY", "false")
    return env


def _floor_subprocess_path(path: str) -> str:
    """Guarantee core system dirs on the CLI subprocess PATH: profile workers (kanban bots, cron) can inherit
    a PATH of only version-manager dirs, and the uv binary's POSIX sh trampoline resolves ``dirname``/``realpath``
    via PATH (exit 127 without /usr/bin). Reuses browser_tool's ``_merge_browser_path`` floor, else appends
    FHS bin dirs. Windows .cmd shims don't trampoline: no-op there."""
    if os.name == "nt":
        return path
    with contextlib.suppress(Exception):
        from tools.browser_tool_install import _merge_browser_path
        return _merge_browser_path(path or "")
    parts = [p for p in (path or "").split(os.pathsep) if p]
    return os.pathsep.join(parts + [d for d in _FHS_BIN_DIRS if d not in set(parts) and os.path.isdir(d)])


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
            sigkill = getattr(signal, "SIGKILL", signal.SIGTERM)
            libc.prctl(1, sigkill, os.getppid(), 0, 0)
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
    global _RUN_OWNED_BROWSER_WORKSPACE
    global _RUN_OWNED_BROWSER_URL, _RUN_OWNED_BROWSER_NAME

    if not _is_unattended_browser_worker():
        return None
    _apply_run_owned_browser_guards(env)
    requested_name = str(env.get("BU_NAME") or f"hbu_{os.getpid()}")

    external_endpoint = str(env.get("BU_CDP_URL") or env.get("BU_CDP_WS") or "")
    if external_endpoint:
        with _RUN_OWNED_BROWSER_LOCK:
            if (
                _RUN_OWNED_BROWSER_RUNTIME is not None
                and _RUN_OWNED_BROWSER_NAME == requested_name
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
            name = requested_name
            runtime = Path(tempfile.gettempdir()) / f"hbu_{os.getpid()}"
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
            and _RUN_OWNED_BROWSER_NAME == requested_name
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
        name = requested_name
        runtime = Path(tempfile.gettempdir()) / f"hbu_{os.getpid()}"
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


def _use_gateway(browser_cfg: dict) -> bool:
    return is_truthy_value(browser_cfg.get("use_gateway"), default=False)


def get_browser_backend() -> str:
    """Configured browser backend key ("" = unset → default). YAML 1.1 parses an
    unquoted ``off`` as False — that must mean BACKEND_DISABLED, not "unset"."""
    raw = _read_browser_cfg().get("backend")
    return (BACKEND_DISABLED if raw is False else "") if isinstance(raw, bool) else str(raw or "").strip().lower()


def is_legacy_browser_use_cloud_config(browser_cfg: dict) -> bool:
    """True for pre-CLI direct-API Browser Use cloud configs. An explicit backend or
    a non-Browser-Use cloud_provider wins; Camofox is selected via env var, not
    cloud_provider, so a Camofox user with a stray BROWSER_USE_API_KEY keeps it."""
    if not isinstance(browser_cfg, dict) or browser_cfg.get("backend"):
        return False
    provider = str(browser_cfg.get("cloud_provider") or "").strip().lower()
    if provider not in {"browser-use", ""} or _use_gateway(browser_cfg) or _camofox_active(" during migration"):
        return False
    return bool(os.getenv("BROWSER_USE_API_KEY"))


def is_browser_use_cli_mode() -> bool:
    """True when the Browser Use CLI replaces the built-in browser stack. Browser Use mode is the DEFAULT:
    unset ``browser.backend`` ("") enables it whenever the CLI is runnable (installed binary or uvx);
    ``browser.backend: off`` keeps the built-in browser_* tools. Camofox always falls back to the built-in
    tools (Firefox, custom HTTP API, no CDP surface for the harness)."""
    if _camofox_active():
        return False
    backend = get_browser_backend()
    return backend == _BACKEND_KEY if backend else (is_legacy_browser_use_cloud_config(_read_browser_cfg()) or _find_cli() is not None)


def default_downgrade_notice() -> Optional[str]:
    """One-line notice when ``browser.backend`` is unset but the CLI is not runnable, so
    the session fell back to the built-in tools. Rate-limited to once per 24h via a stamp file."""
    try:
        if get_browser_backend() or _camofox_active() or _find_cli() is not None:
            return None  # explicit choice / Camofox / CLI present — nothing downgraded
        stamp = Path(get_hermes_home()) / "cache" / ".browser_use_default_notice"
        with contextlib.suppress(OSError):
            if 0 <= time.time() - stamp.stat().st_mtime < 24 * 3600:
                return None
        with contextlib.suppress(OSError):
            stamp.parent.mkdir(parents=True, exist_ok=True)
            stamp.touch()
        return ("Browser Use CLI not found — using the built-in browser tools. Run `hermes tools` "
                "(Browser Automation → Browser Use) to install it, or `browser.backend: off` in config.yaml to silence this.")
    except Exception as e:  # pragma: no cover — a notice must never break startup
        logger.debug("browser-use downgrade notice failed: %s", e)
        return None


def _managed_bin_dir() -> str:
    """$HERMES_HOME/bin — where install.sh puts uv/uvx and install_cli() links browser-use."""
    return str(Path(get_hermes_home()) / "bin")


def _user_local_bin_dir() -> Optional[str]:
    """Standard user-level tool directory, which service PATH may omit."""
    try:
        if os.name == "nt":
            base = os.environ.get("APPDATA")
            return str(Path(base) / "uv" / "bin") if base else None
        return str(Path(os.path.expanduser("~")) / ".local" / "bin")
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("Could not resolve user-local bin dir: %s", exc)
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
    """Locate the governed Browser Use CLI.

    Interactive sessions retain upstream fallbacks. Unattended Cron/Kanban
    workers must use the deployment-wide or Hermes-managed binary and never
    trigger a lazy uvx download.
    """
    probe_paths = (_shared_browser_runtime_bin(), _managed_bin_dir(), None, _user_local_bin_dir())
    for probe_path in probe_paths:
        if probe_path is None or probe_path:
            direct = shutil.which("browser-use", path=probe_path)
            if direct:
                return [direct]
    if _is_unattended_browser_worker():
        return None
    for probe_path in (_managed_bin_dir(), None, _user_local_bin_dir()):
        if probe_path is None or probe_path:
            uvx = shutil.which("uvx", path=probe_path)
            if uvx:
                return [uvx, "browser-use"]
    return None


def install_cli(timeout_s: int = 600) -> Tuple[bool, str]:
    """Install the browser-use CLI via ``uv tool install`` (managed uv via ``ensure_uv`` → uv on PATH), linking
    the binary into ``$HERMES_HOME/bin`` (``UV_TOOL_BIN_DIR``) so ``_find_cli()`` resolves it for every profile.
    Returns ``(ok, message)``; never raises. MANAGED-FIRST: only the managed copy short-circuits — a browser-use
    on PATH is a user-level side install and must not block provisioning the canonical copy (version drift)."""
    shared_bin = _shared_browser_runtime_bin()
    if shared_bin:
        shared = shutil.which("browser-use", path=shared_bin)
        if shared:
            return True, f"browser-use CLI already installed ({shared})"
    bin_dir = _managed_bin_dir()
    managed = shutil.which("browser-use", path=bin_dir)
    if managed:
        return True, f"browser-use CLI already installed ({managed})"

    def _managed_uv() -> Optional[str]:
        from hermes_cli.managed_uv import ensure_uv
        return str(ensure_uv() or "") or None
    uv_bin = _quiet(_managed_uv, None, "Managed uv bootstrap unavailable") or shutil.which("uv")
    if not uv_bin:
        return False, ("uv is not available and could not be bootstrapped. Install uv "
                       "(https://docs.astral.sh/uv/) and run `uv tool install browser-use`.")
    env = {**os.environ, "UV_NO_CONFIG": "1"}
    try:
        Path(bin_dir).mkdir(parents=True, exist_ok=True)
        env["UV_TOOL_BIN_DIR"] = bin_dir
    except OSError as e:
        logger.debug("Could not prepare %s: %s", bin_dir, e)

    try:
        result = subprocess.run([uv_bin, "tool", "install", "browser-use"], capture_output=True, text=True, encoding="utf-8",
                                errors="replace", env=env, timeout=timeout_s, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return False, f"`uv tool install browser-use` timed out after {timeout_s}s"
    except Exception as e:
        return False, f"Failed to run `uv tool install browser-use`: {e}"

    if result.returncode != 0:
        tail = "\n".join((result.stderr or result.stdout or "").strip().splitlines()[-3:])
        return False, f"`uv tool install browser-use` failed:\n{tail}"
    found = _find_cli()
    if not found or len(found) != 1:
        return False, ("install reported success but the browser-use binary is still not resolvable — "
                       "run `uv tool install browser-use` manually")
    return True, f"browser-use CLI installed ({found[0]})"


def _workspace_dir(task_id: Optional[str]) -> Optional[str]:
    """Stable per-task scratch dir that persists across browser_exec calls"""
    if os.environ.get("BH_AGENT_WORKSPACE"):
        return os.environ["BH_AGENT_WORKSPACE"]
    try:
        safe = _TASK_ID_SAFE_RE.sub("_", str(task_id or "default"))[:80] or "default"
        path = Path(get_hermes_home()) / "cache" / "browser-use" / "workspace" / safe
        path.mkdir(parents=True, exist_ok=True)
        return str(path)
    except Exception as e:
        logger.debug("browser_exec workspace unavailable: %s", e)
        return None


def _find_screenshot(stdout: str, since: float) -> Optional[str]:
    """Last screenshot path printed during this exec that exists and was written after
    the exec started, or None."""
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
        from tools.vision_tools import (_EMBED_MAX_DIMENSION, _EMBED_TARGET_BYTES,
                                        _resize_image_for_vision, _should_use_native_vision_fast_path)
        if not _should_use_native_vision_fast_path():
            return None
        # History-reuse cap: this data URL bakes into the tool result and is re-sent every later turn —
        # same policy as the vision_analyze / browser_vision native embeds.
        data_url = _resize_image_for_vision(Path(path), mime_type="image/png", max_base64_bytes=_EMBED_TARGET_BYTES,
                                            max_dimension=_EMBED_MAX_DIMENSION, force_jpeg=True)
        text = json.dumps(result, ensure_ascii=False)
        attached = text + "\n\nThe screenshot from this call is attached — inspect it with your native vision."
        return {"_multimodal": True, "text_summary": text, "meta": {"screenshot_path": path, "native_vision": True},
                "content": [{"type": "text", "text": attached}, {"type": "image_url", "image_url": {"url": data_url}}]}
    except Exception as e:
        logger.debug("Native screenshot attach failed (falling back to text): %s", e)
        return None


def _backend_cache_key(task_id: Optional[str], session_name: str = "") -> str:
    """Session-cache key for a backend browser: named sessions get their own."""
    return f"bu-named-{session_name}" if session_name else (task_id or "browser-exec-default")


def _resolve_lightpanda_cdp(env: dict, task_id: Optional[str], session_name: str = "") -> Optional[str]:
    """Point the harness at a Hermes-spawned ``lightpanda serve`` (``browser.engine: lightpanda`` and
    nothing of higher precedence claimed the session). Each cache key gets its own process via the
    legacy ``_get_session_info()`` (cache, reaper, atexit): private browser, own-tab preamble skipped."""
    try:
        from tools.browser_tool_session import _get_session_info
        from tools.browser_tool_lightpanda_fallback import _using_lightpanda_engine
        if not _using_lightpanda_engine():
            return None
    except Exception as e:  # stubbed browser_tool in tests / engine lookup failure
        logger.debug("browser engine lookup failed: %s", e)
        return None
    err = _export_session_cdp(
        env, _get_session_info, _backend_cache_key(task_id, session_name),
        lambda e: (f"Lightpanda could not be started: {e} Set browser.engine to auto "
                   "to use local Chrome, or switch backends via `hermes tools` → Browser Automation."),
        "Lightpanda session returned no CDP endpoint. Set browser.engine to auto to use local Chrome.",
    )
    if err is None:
        env[_PRIVATE_BROWSER_SENTINEL] = "1"
    return err


def _resolve_managed_chromium_cdp(env: dict, task_id: Optional[str], session_name: str = "") -> Optional[str]:
    """Point the harness at Hermes' packaged Chromium, launched through agent-browser for this cache key —
    the same browser the built-in tools drive. Left alone, the harness discovers the user's INSTALLED
    Chrome on its default profile, which needs the chrome://inspect toggle + an Allow popup per run and
    is blocked outright on Chrome >=136; on a headless box it just reports ``chrome-not-running``.
    ``get cdp-url`` runs through ``_run_browser_command`` (legacy cache, inactivity reaper, atexit, Chromium
    preflight/auto-install) on EVERY call: it launches the browser cold, follows a relaunch, and refreshes
    the agent-browser daemon's idle timer, which never sees the harness's direct CDP traffic."""
    try:
        from tools.browser_tool_session import _run_browser_command
        from tools.browser_tool import _get_open_command_timeout
    except Exception as e:  # pragma: no cover — stubbed browser_tool in tests
        logger.debug("managed chromium resolution unavailable: %s", e)
        return None
    res = _run_browser_command(_backend_cache_key(task_id, session_name), "get", ["cdp-url"],
                               timeout=_get_open_command_timeout(first_open=True))
    cdp = str(((res or {}).get("data") or {}).get("cdpUrl") or "") if (res or {}).get("success") else ""
    if not cdp:
        return (f"The local browser could not be started: {(res or {}).get('error') or 'agent-browser returned no CDP endpoint'} "
                "Run `hermes tools` → Browser Automation to (re)install Chromium, or switch backends.")
    _set_cdp_env(env, cdp)
    env[_PRIVATE_BROWSER_SENTINEL] = "1"  # one Chromium per cache key: nothing to share a tab with
    return None


def _resolve_local_engine_cdp(env: dict, task_id: Optional[str], session_name: str = "") -> Optional[str]:
    """Local engine (no provider / override): ``browser.engine: lightpanda`` or the packaged Chromium."""
    err = _resolve_lightpanda_cdp(env, task_id, session_name)
    if err or _has_cdp_env(env):
        return err
    return _resolve_managed_chromium_cdp(env, task_id, session_name)


def _resolve_backend_cdp(env: dict, task_id: Optional[str], session_name: str = "") -> Optional[str]:
    """Point the harness at the configured backend's CDP endpoint; error string on failure.

    Precedence: (1) ``BU_CDP_WS``/``BU_CDP_URL`` already in env (operator override); (2) ``BROWSER_CDP_URL``
    env / ``browser.cdp_url`` (``/browser connect``); (3) a cloud provider via the legacy ``_get_session_info()``
    so browser_exec shares the SAME session machinery (per-task cache, expiry, reaper, atexit);
    (4) the local engine — ``browser.engine: lightpanda`` or Hermes' packaged Chromium via agent-browser
    (never the harness's own discovery of the user's installed Chrome); (5) BU direct-API configs → None:
    the CLI reaches BU cloud natively (BU_AUTOSPAWN). ``session_name`` (BU_NAME) keys the session cache so
    each name gets its OWN browser — what makes named sessions concurrent-safe.
    """
    if _has_cdp_env(env):
        return None
    try:
        from tools.browser_tool_cloud import _get_cloud_provider
        from tools.browser_tool_session import _get_session_info
        from tools.browser_tool_cdp import _get_cdp_override
    except Exception as e:  # pragma: no cover — stubbed browser_tool in tests
        logger.debug("browser_tool backend resolution unavailable: %s", e)
        return None
    override = _quiet(_get_cdp_override, "")
    if override:
        _set_cdp_env(env, override)
        return None
    provider = _quiet(_get_cloud_provider, None, "Cloud provider lookup failed")
    if provider is None:
        return _resolve_local_engine_cdp(env, task_id, session_name)

    # Browser Use direct-API configs: the CLI talks to BU cloud natively (BU_AUTOSPAWN / auth login) — the
    # legacy provider would create a second, redundant session. The Nous-gateway variant (use_gateway: true)
    # DOES resolve through the provider: the gateway provisions the browser server-side and returns its CDP URL.
    provider_key = str(getattr(provider, "name", "") or "").strip().lower()
    if provider_key == _BACKEND_KEY and not _use_gateway(_read_browser_cfg()):
        env[_PRIVATE_BROWSER_SENTINEL] = "1"  # named BU cloud browsers are exclusive to their daemon
        return None

    provider_name = type(provider).__name__
    err = _export_session_cdp(
        env, _get_session_info, _backend_cache_key(task_id, session_name),
        lambda e: (f"Cloud browser provider {provider_name} failed to provide a session: {e}. "
                   "Fix the provider configuration or switch backends via `hermes tools` → Browser Automation."),
        f"Cloud browser provider {provider_name} returned no CDP endpoint, so Browser Use mode "
        "cannot drive it. Switch to the built-in browser tools for this provider.",
    )
    # A provider browser keyed bu-named-<name> is exclusive to this session — the
    # own-tab preamble would just leak a blank tab into it.
    if err is None and session_name:
        env[_PRIVATE_BROWSER_SENTINEL] = "1"
    return err


def _resolve_real_profile_cdp(env: dict, force_local: bool) -> Optional[str]:
    """Point the harness at the user's real-profile copy-browser (a SNAPSHOT of their default Chromium
    profile, hermes_cli.browser_connect) when consented. Two ways in: the effective backend is already local
    (no provider, CDP override, or legacy BU cloud config) → silent upgrade; or ``force_local`` (consent-gated
    ``local`` arg) → the user's browser even under a cloud backend. Operator overrides (BU_CDP_* env,
    /browser connect, ``browser.cdp_url``) own the session either way. Fail closed: a launch error is
    returned so a consented user is never silently downgraded."""
    if not _real_profile_consented() or _has_cdp_env(env):
        return None
    try:
        from tools.browser_tool_cdp import _get_cdp_override_raw
        from tools.browser_tool_cloud import _get_cloud_provider
        from tools.browser_tool_real_profile import _real_profile_cdp
    except Exception as e:  # pragma: no cover — stubbed browser_tool in tests
        logger.debug("real-profile backend resolution unavailable: %s", e)
        return None
    if _quiet(_get_cdp_override_raw, ""):
        return None
    # Only auto-upgrade genuinely-local attaches; any cloud path (provider, provider lookup failure, or
    # legacy BU cloud config) stays on its backend unless the model passes local=true.
    if not force_local and (_quiet(_get_cloud_provider, object()) is not None
                            or is_legacy_browser_use_cloud_config(_read_browser_cfg())):
        return None
    cdp, err = _real_profile_cdp()
    if cdp and not err:
        _set_cdp_env(env, cdp)
    return err or None


def _route_backend(env: dict, session: str, task_id: Optional[str], local: bool) -> Optional[str]:
    """Resolve where the harness connects; returns an error string or None. Real-profile consent runs
    BEFORE provider resolution so a hit short-circuits the cloud path via the BU_CDP_* env contract. Named
    sessions compose with the backend: BU_NAME namespaces the harness daemon (IPC socket, log, pid) and on
    provider backends additionally keys its own cloud browser."""
    rp_err = _resolve_real_profile_cdp(env, force_local=local)
    if rp_err:
        return rp_err
    # local=True is only served by the real-profile route; consent off must not pretend.
    if local and not _has_cdp_env(env) and not _real_profile_consented():
        return ("local=true was requested but browser.use_real_profile is off. Enable it in config.yaml "
                "(browser.use_real_profile: true) or the desktop Settings → Browser section, then retry.")
    return _resolve_backend_cdp(env, task_id, session_name=session)


def _windows_popen_kwargs() -> dict:
    """Hide the console the .cmd shim would flash on Windows (as browser_tool does)."""
    def _flags() -> dict:
        from hermes_cli._subprocess_compat import windows_hide_flags
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return {"creationflags": windows_hide_flags(), "startupinfo": si}
    return _quiet(_flags, {}, "Windows hide-flags unavailable") if os.name == "nt" else {}


def _clamp_timeout(timeout_s: Any) -> int:
    try:
        return max(_MIN_TIMEOUT_S, min(int(timeout_s), _MAX_TIMEOUT_S))
    except (TypeError, ValueError):
        return _DEFAULT_TIMEOUT_S


def browser_exec(code: str, session: str = "", timeout_s: int = _DEFAULT_TIMEOUT_S,
                 task_id: Optional[str] = None, local: bool = False):
    """Run Python code through the browser-use CLI, and return its output"""
    from tools.registry import tool_error, tool_result
    if not code or not code.strip():
        return tool_error("No code provided. Pass Python that uses the pre-imported helpers, e.g. new_tab(\"https://example.com\") then print(page_info()).")

    blocked = _blocked_url_in_code(code)
    if blocked:
        return tool_error(blocked)

    cmd = _find_cli()
    if not cmd:
        return tool_error("browser-use CLI not found on PATH, and uvx is unavailable for a zero-install run. "
                          "Install it with `uv tool install browser-use` (or `pipx install browser-use`), "
                          "then run `browser-use --doctor` to verify the setup.")

    env = _base_subprocess_env()
    if session:
        if not _SESSION_RE.match(session):
            return tool_error(f"Invalid session name {session!r}: use 1-64 letters, digits, "
                              "dashes, or underscores (e.g. 'r7k2').")
        env["BU_NAME"] = session
    route_err = _route_backend(env, session, task_id, bool(local))
    if route_err:
        return tool_error(route_err)

    run_owned_err = _ensure_run_owned_browser(env, task_id)
    if run_owned_err:
        return tool_error(run_owned_err)

    # SHARED browser (/browser connect CDP override): pin each named session to its own tab (see
    # _OWN_TAB_PREAMBLE). Private per-name browsers skip this — nothing to collide with.
    private_browser = env.pop(_PRIVATE_BROWSER_SENTINEL, None)  # always pop: never exported to the CLI
    if session and not private_browser:
        code = _OWN_TAB_PREAMBLE + code

    workspace = _workspace_dir(task_id)
    if workspace:
        env["BH_AGENT_WORKSPACE"] = workspace
        _set_run_owned_browser_workspace(workspace)

    # BU_AUTOSPAWN makes the CLI start a Browser Use cloud browser when no local
    # Chrome/CDP endpoint is reachable (their API key authenticates it)
    if "BU_AUTOSPAWN" not in env and is_legacy_browser_use_cloud_config(_read_browser_cfg()):
        env["BU_AUTOSPAWN"] = "1"

    timeout = _clamp_timeout(timeout_s)
    started = time.time()
    stdout_text = ""
    stderr_text = ""
    try:
        # Harness daemons may inherit stdio. Temp files keep the one-shot call
        # from waiting forever for a descendant to close inherited pipes.
        with tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace") as stdout_file, \
                tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace") as stderr_file:
            proc = subprocess.Popen(
                cmd, stdin=subprocess.PIPE, stdout=stdout_file, stderr=stderr_file,
                text=True, env=env, **_windows_popen_kwargs(),
            )
            try:
                proc.communicate(input=code, timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
                return tool_error(
                    f"browser-use exec timed out after {timeout}s. The daemon may still be working; retry "
                    f"with a larger timeout_s (max {_MAX_TIMEOUT_S}), or split the work into several calls that "
                    "append to workspace files — anything already written to the workspace is preserved."
                )
            stdout_file.seek(0)
            stderr_file.seek(0)
            stdout_text = stdout_file.read()
            stderr_text = stderr_file.read()
    except OSError as e:
        return tool_error(f"Failed to launch browser-use CLI: {e}")

    result = {"success": proc.returncode == 0, "exit_code": proc.returncode, "output": stdout_text}
    if workspace:
        result["workspace"] = workspace
    if session:
        result["session"] = session
    stderr = stderr_text.strip()
    if len(stderr) > _STDERR_CAP_CHARS:
        stderr = stderr[:_STDERR_CAP_CHARS] + "\n… (stderr truncated)"
    if stderr:
        result["stderr"] = stderr
    screenshot = _find_screenshot(stdout_text, started)
    if screenshot:
        result["screenshot_path"] = screenshot
        native = _native_screenshot_result(result, screenshot)
        if native is not None:
            return native
    return tool_result(result)


_HEADER_BASE = (
    "Drive a real web browser via the Browser Use CLI: `code` runs as full Python (stdlib available) "
    "with pre-imported browser helpers; stdout comes back in the result. Start `code` with a one-line "
    "comment describing the step for the user in plain language, max 60 chars "
    "(e.g. `# Searching Amazon for paper towels`) — the UI shows it as the step label.\n\n"
    "STATE: the browser session and workspace persist across calls; Python variables do NOT (fresh "
    "interpreter each call). The workspace dir is $BH_AGENT_WORKSPACE (also `workspace` in every result); "
    "functions defined in agent_helpers.py there are auto-imported into every call. For multi-item tasks "
    "('all N products / every entry'), append each batch to a JSON/CSV file in the workspace, then read it "
    "back and aggregate in code — dedupe/count/sort with Python, not in your head — and verify the "
    "collected count against what was asked before answering.\n\n"
    "Batch each sub-procedure (navigate, wait, extract, act) into one call — do not spend a call per "
    "action — but for long extractions prefer several medium calls that append to workspace files over "
    "one giant call, so progress survives timeouts."
)

_HEADER_VISION = (
    " Screenshots are attached to your context automatically: when the exec output contains a "
    "capture_screenshot() path, the image arrives with this tool's result and you inspect it directly "
    "with your own vision — never send browser screenshots to a separate vision tool."
)

_HEADER_TEXT_ONLY = (
    " Your model cannot view images, so work text-first: page_info() for state, js() for "
    "reading/extracting DOM text, fill_input(selector, text) for inputs, and "
    "js(\"document.querySelector('…').click()\") for clicks — skip the screenshot-driven workflow described below."
)

# Appended when the local engine is Lightpanda: no graphical renderer, and one CDP
# connection holds one page — a second Target.createTarget fails with
# TargetAlreadyLoaded (drop the new_tab() sentence once lightpanda-io/browser#1962 lands).
_HEADER_LIGHTPANDA = (
    " The local engine is Lightpanda (no graphical renderer, one page per session): capture_screenshot() "
    "is unavailable, so work text-first; navigate with new_tab(url) exactly once, then goto_url(url) for "
    "every later navigation — a second new_tab() fails with TargetAlreadyLoaded."
)

# Pinned quick-reference for the CLI's pre-imported helpers, replacing the live
# ``browser-use skill`` fetch (uncontrolled third-party text in every schema: version
# drift, supply-chain exposure, byte-unstable prompt). A/B benchmarked ~equal.
_HELPERS_DIGEST = (
    "\n\nHELPERS (pre-imported): new_tab(url) opens/navigates (use for the FIRST navigation), goto_url(url) "
    "navigates the current tab, wait_for_load() after navigation, page_info() summarizes the current page "
    "state, js(expr) evaluates a JS expression and returns its value (js('document.title'); wrap function "
    "bodies as js('(() => {...})()') — a bare '() => {...}' returns the function itself, uncalled), "
    "fill_input(selector, text) types into inputs, click_at_xy(x, y) clicks viewport coordinates, "
    "capture_screenshot() saves and prints a screenshot path, cdp('Domain.method', **kwargs) is raw CDP — "
    "cdp('Accessibility.getFullAXTree')['nodes'] lists every element's role/name/backendDOMNodeId (filter "
    "in Python before printing; it is thousands of nodes), then cdp('DOM.getBoxModel', backendNodeId=n) "
    "gives click coordinates. ensure_real_tab() recovers from a stale/internal tab. Login walls: stop and "
    "ask the user; never guess credentials."
)


def _description_header() -> str:
    """Header tailored to whether the active model can see images natively"""
    if _lazy_call("tools.browser_tool_lightpanda_fallback", "lightpanda_engine_status", (False, ""),
                  "lightpanda engine status unavailable")[0]:  # no screenshots, whatever the model sees
        return _HEADER_BASE + _HEADER_TEXT_ONLY + _HEADER_LIGHTPANDA
    vision = _lazy_call("tools.vision_tools", "_should_use_native_vision_fast_path", False, "")
    return _HEADER_BASE + (_HEADER_VISION if vision else _HEADER_TEXT_ONLY)


def _dynamic_schema_overrides() -> dict:
    overrides: dict = {"description": _description_header() + _HELPERS_DIGEST}
    # ``local`` exists ONLY when the user consented to real-profile browsing — everyone
    # else's schema carries zero extra surface. The caller memoizes on config.yaml mtime,
    # so toggling consent applies next session, not mid-chat.
    if _real_profile_consented():
        props = dict(BROWSER_EXEC_SCHEMA["parameters"]["properties"])
        props["local"] = {
            "type": "boolean", "default": False,
            "description": ("Drive the user's own local browser (a Hermes-managed copy of their real "
                            "default-Chromium profile, logins/cookies included) instead of the configured "
                            "cloud browser backend. Use when the user asks to act as themselves — their "
                            "accounts, their sessions. No-op when the backend is already local. Default false."),
        }
        overrides["parameters"] = {**BROWSER_EXEC_SCHEMA["parameters"], "properties": props}
    return overrides


BROWSER_EXEC_SCHEMA = {
    "name": "browser_exec",
    # Static fallback description, used only when the CLI (and uvx) is unavailable
    "description": (_HEADER_BASE + _HELPERS_DIGEST
                    + "\n\n(The browser-use CLI is not installed yet. Install it with `uv tool install browser-use`.)"),
    "parameters": {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Python code to execute using the pre-imported browser helpers. Use print(...) for any data you need back."},
            "session": {"type": "string", "description": "Named isolated browser session — its own daemon and (on cloud backends) own browser, so concurrent tasks don't share tabs. Reuse the same name on every related call; omit for the shared default session."},
            "timeout_s": {"type": "integer", "default": _DEFAULT_TIMEOUT_S,
                          "description": f"Max seconds to wait for the code to finish (default {_DEFAULT_TIMEOUT_S}, max {_MAX_TIMEOUT_S})."},
        },
        "required": ["code"],
    },
}


# browser_exec is additionally gated at tool-definition time — sessions whose toolsets
# lack ``terminal`` never see it (model_tools._compute_tool_definitions). check_fn only
# answers "is Browser Use mode configured"; surface policy lives with the session.
from tools.registry import registry

registry.register(
    name="browser_exec",
    toolset="browser-use",
    schema=BROWSER_EXEC_SCHEMA,
    handler=lambda args, **kw: browser_exec(
        code=args.get("code", ""), session=args.get("session", "") or "",
        timeout_s=args.get("timeout_s", _DEFAULT_TIMEOUT_S), task_id=kw.get("task_id"),
        local=bool(args.get("local", False)),
    ),
    check_fn=is_browser_use_cli_mode,
    dynamic_schema_overrides=_dynamic_schema_overrides,
    emoji="🌐",
)

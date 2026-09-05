"""DingTalk platform adapter (Stream Mode via dingtalk-stream >=0.20; replies via session webhook markdown or AI Cards).
Requires ``pip install "dingtalk-stream>=0.20" httpx``. config.yaml ``platforms.dingtalk``: ``enabled``, group gating
(``require_mention``, ``free_response_chats``, ``mention_patterns``, ``allowed_users``/``allowed_chats``) and
``extra.client_id`` / ``extra.client_secret`` (or DINGTALK_CLIENT_ID / DINGTALK_CLIENT_SECRET)."""

import asyncio
import json
import logging
import mimetypes
import os
import re
import subprocess
import tempfile
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Optional SDKs: catch broad Exception, not just ImportError — their transitive cryptography
# dependency can raise AttributeError on version skew; a broken optional SDK must degrade gracefully.
try:
    import dingtalk_stream
    from dingtalk_stream import ChatbotMessage
    from dingtalk_stream.frames import CallbackMessage, AckMessage

    DINGTALK_STREAM_AVAILABLE = True
except Exception:  # noqa: BLE001
    DINGTALK_STREAM_AVAILABLE = False
    dingtalk_stream = ChatbotMessage = CallbackMessage = None  # type: ignore[assignment]
    AckMessage = type("AckMessage", (), {"STATUS_OK": 200, "STATUS_SYSTEM_EXCEPTION": 500})  # type: ignore[assignment]

try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    httpx = None  # type: ignore[assignment]

try:
    from alibabacloud_dingtalk.card_1_0 import client as dingtalk_card_client, models as dingtalk_card_models
    from alibabacloud_dingtalk.robot_1_0 import client as dingtalk_robot_client, models as dingtalk_robot_models
    from alibabacloud_tea_openapi import models as open_api_models
    from alibabacloud_tea_util import models as tea_util_models

    CARD_SDK_AVAILABLE = True
except Exception:
    CARD_SDK_AVAILABLE = False
    dingtalk_card_client = dingtalk_card_models = dingtalk_robot_client = dingtalk_robot_models = None
    open_api_models = tea_util_models = None

from gateway.config import Platform, PlatformConfig
from gateway.platforms.helpers import MessageDeduplicator, compile_mention_patterns
from gateway.platforms.base import (
    BasePlatformAdapter, MessageEvent, SendResult, cache_audio_from_bytes,
    cache_document_from_bytes,
)
from gateway.platforms._shared import get_scoped_secret as _get_scoped_secret
from plugins.platforms.dingtalk.inbound import collect_download_codes, extract_media, extract_text


logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 20000
RECONNECT_BACKOFF = [2, 5, 10, 30, 60]
_SESSION_WEBHOOKS_MAX = 500
_DINGTALK_WEBHOOK_RE = re.compile(r'^https://(?:api|oapi)\.dingtalk\.com/')
_DINGTALK_MEDIA_UPLOAD_URL = "https://oapi.dingtalk.com/media/upload"
_DINGTALK_OTO_BATCH_SEND_URL = "https://api.dingtalk.com/v1.0/robot/oToMessages/batchSend"
_DINGTALK_OTO_READ_STATUS_URL = "https://api.dingtalk.com/v1.0/robot/oToMessages/readStatus"
_DINGTALK_MEDIA_MAX_BYTES = 20 * 1024 * 1024
_FILE_STATUS_POLL_DELAYS = (0.25, 0.75, 2.0, 5.0)
_TRUTHY = {"true", "1", "yes", "on"}
_EMOTION_ID = "2659900"
_EMOTION_BG = "im_bg_1"
# recall? -> (TextEmotion model, Request model, Headers model, robot SDK method), resolved on ``dingtalk_robot_models`` at call time.
_EMOTION_SDK = {recall: (f"Robot{v}EmotionRequestTextEmotion", f"Robot{v}EmotionRequest", f"Robot{v}EmotionHeaders", f"robot_{v.lower()}_emotion_with_options_async")
                for recall, v in ((True, "Recall"), (False, "Reply"))}
_NUMBERED_RE = re.compile(r"^\d+\.\s")
_NO_LOCAL_UPLOAD = "DingTalk session webhook replies do not support local %s. Only markdown/text replies are supported without OpenAPI %s."


def _csv_set(raw: Any) -> Set[str]:
    """Split a list or comma-separated string into a set of stripped, non-empty items."""
    parts = raw if isinstance(raw, list) else str(raw).split(",")
    return {str(part).strip() for part in parts if str(part).strip()}


def dingtalk_deps_present() -> bool:
    """PASSIVE registry ``check_fn`` — must never install; credentials are gated separately.

    Registry ``check_fn`` — called from status displays and config loading, so it must never install
    anything. The ACTIVE lazy-installer (``check_dingtalk_requirements``) is registered as
    ``ensure_deps_fn`` and runs from ``create_adapter()`` when this returns False (#79812).
    """
    return DINGTALK_STREAM_AVAILABLE and HTTPX_AVAILABLE


def ensure_dingtalk_deps() -> bool:
    """ACTIVE deps-only installer (registry ``ensure_deps_fn``); rebinds module globals. Deliberately does NOT
    check credentials: an ``extra``-configured platform would otherwise be vetoed before ever installing (deadlock).

    Lazy-installs dingtalk-stream/httpx and rebinds module globals. Deliberately does NOT check credentials
    — ``ensure_deps_fn``'s contract is deps-only ("Returns True once deps are importable"); credentials are
    gated by ``is_connected``/``validate_config``. Otherwise a platform configured via
    ``PlatformConfig.extra`` (which ``_is_connected`` accepts) would pass enablement, reach
    ``create_adapter()``, and have the installer veto on env-var grounds before ever installing —
    re-creating the #79812 deadlock for extra-configured setups.
    """
    global DINGTALK_STREAM_AVAILABLE, dingtalk_stream, ChatbotMessage, CallbackMessage, AckMessage, HTTPX_AVAILABLE, httpx
    if DINGTALK_STREAM_AVAILABLE and HTTPX_AVAILABLE:
        return True
    try:
        from tools.lazy_deps import ensure as _lazy_ensure
        _lazy_ensure("platform.dingtalk", prompt=False)
        import dingtalk_stream as _ds, httpx as _httpx  # noqa: E401
        from dingtalk_stream import ChatbotMessage as _CM
        from dingtalk_stream.frames import CallbackMessage as _CBM, AckMessage as _AM
    except Exception:
        return False
    dingtalk_stream, ChatbotMessage, CallbackMessage, AckMessage, httpx = _ds, _CM, _CBM, _AM, _httpx
    DINGTALK_STREAM_AVAILABLE = HTTPX_AVAILABLE = True
    return True


def _credentials(extra: Optional[dict]) -> tuple:
    """(client_id, client_secret) from PlatformConfig.extra first, then env / scoped secret."""
    extra = extra or {}
    return (extra.get("client_id") or os.getenv("DINGTALK_CLIENT_ID", ""), extra.get("client_secret") or _get_scoped_secret("DINGTALK_CLIENT_SECRET", ""))


def check_dingtalk_requirements() -> bool:
    """Combined deps (lazy-installed) + credentials check for setup/status callers."""
    return ensure_dingtalk_deps() and all(_credentials(None))


class DingTalkAdapter(BasePlatformAdapter):
    """Stream Mode adapter: the SDK keeps a long-lived WebSocket and messages arrive via a ChatbotHandler
    callback; replies go through the message's session_webhook (httpx) or, with ``card_template_id``, AI Cards."""

    MAX_MESSAGE_LENGTH = MAX_MESSAGE_LENGTH

    @property
    def SUPPORTS_MESSAGE_EDITING(self) -> bool:  # noqa: N802
        """Edits only exist with AI Cards; the gateway gates streaming cursor/edit on this."""
        return bool(self._card_template_id and self._card_sdk)

    REQUIRES_EDIT_FINALIZE = SUPPORTS_MESSAGE_EDITING  # AI Cards need an explicit ``finalize=True`` edit to close the streaming indicator

    def __init__(self, config: PlatformConfig):
        super().__init__(config, Platform.DINGTALK)
        extra = config.extra or {}
        self._client_id, self._client_secret = _credentials(extra)
        # Group-chat gating; mention state is the SDK's structured ``is_in_at_list``, not text parsing.
        self._mention_patterns: List[re.Pattern] = self._compile_mention_patterns()
        self._allowed_users: Set[str] = {item.lower() for item in self._csv_setting("allowed_users", "DINGTALK_ALLOWED_USERS")}
        self._stream_client = self._stream_task = self._http_client = self._card_sdk = self._robot_sdk = None
        self._robot_code: str = extra.get("robot_code") or self._client_id
        self._dedup = MessageDeduplicator(max_size=1000)
        self._session_webhooks: Dict[str, tuple[str, int]] = {}  # chat_id -> (webhook, expired_time_ms)
        self._message_contexts: Dict[str, Any] = {}  # chat_id -> last inbound ChatbotMessage (per-chat: no clobber)
        self._card_template_id: Optional[str] = extra.get("card_template_id")
        self._done_emoji_fired: Set[str] = set()  # chats whose Done reaction fired this turn; reset per inbound
        # Open streaming cards: chat_id -> {out_track_id: last_content}. ``edit_message(finalize=False)``
        # re-opens a finalized card, so we track them and auto-close as siblings on the next ``send()``.
        self._streaming_cards: Dict[str, Dict[str, str]] = {}
        self._bg_tasks: Set[asyncio.Task] = set()  # fire-and-forget emoji tasks, kept referenced (GC) + cancellable

    async def connect(self, *, is_reconnect: bool = False) -> bool:
        """Connect to DingTalk via Stream Mode."""
        for ok, problem in ((DINGTALK_STREAM_AVAILABLE, "dingtalk-stream not installed. Run: pip install 'dingtalk-stream>=0.20'"),
                            (HTTPX_AVAILABLE, "httpx not installed. Run: pip install httpx"),
                            (self._client_id and self._client_secret, "DINGTALK_CLIENT_ID and DINGTALK_CLIENT_SECRET required")):
            if not ok:
                logger.warning("[%s] " + problem, self.name)
                return False
        try:
            from gateway.platforms._http_client_limits import platform_httpx_limits  # tighter keepalive: idle CLOSE_WAIT drains promptly
            self._http_client = httpx.AsyncClient(timeout=30.0, limits=platform_httpx_limits())
            self._stream_client = dingtalk_stream.DingTalkStreamClient(dingtalk_stream.Credential(self._client_id, self._client_secret))
            if CARD_SDK_AVAILABLE:
                sdk_config = open_api_models.Config()
                sdk_config.protocol, sdk_config.region_id = "https", "central"
                if self._card_template_id:
                    self._card_sdk = dingtalk_card_client.Client(sdk_config)
                self._robot_sdk = dingtalk_robot_client.Client(sdk_config)  # needed for media download even without cards
                if self._card_template_id:
                    logger.info("[%s] Card SDK initialized with template: %s", self.name, self._card_template_id)
                else:
                    logger.info("[%s] Robot SDK initialized (media download)", self.name)
            self._stream_client.register_callback_handler(dingtalk_stream.ChatbotMessage.TOPIC, _IncomingHandler(self, asyncio.get_running_loop()))
            self._stream_task = asyncio.create_task(self._run_stream())
            self._mark_connected()
            logger.info("[%s] Connected via Stream Mode", self.name)
            self._wire_plugin_handlers(self._stream_client)  # plugin-registered native handlers
            return True
        except Exception as e:
            logger.error("[%s] Failed to connect: %s", self.name, e)
            return False

    async def _run_stream(self) -> None:
        """Run the async stream client with auto-reconnection."""
        backoff_idx = 0
        while self._running:
            try:
                logger.debug("[%s] Starting stream client...", self.name)
                await self._stream_client.start()
            except asyncio.CancelledError:
                return
            except Exception as e:
                if self._running:
                    logger.warning("[%s] Stream client error: %s", self.name, e)
            if not self._running:
                return
            delay = RECONNECT_BACKOFF[min(backoff_idx, len(RECONNECT_BACKOFF) - 1)]
            logger.info("[%s] Reconnecting in %ds...", self.name, delay)
            await asyncio.sleep(delay)
            backoff_idx += 1

    async def _quiet(self, coro, debug_fmt: str = "", *args) -> None:
        """Await *coro*, swallowing any exception (logged at debug as ``debug_fmt % (name, *args, exc)`` when given)."""
        try:
            await coro
        except Exception as e:
            if debug_fmt:
                logger.debug(debug_fmt, self.name, *args, e)

    async def disconnect(self) -> None:
        """Disconnect from DingTalk."""
        self._running = False
        self._mark_disconnected()
        # Close the websocket first so the stream task sees the disconnect instead of awaiting frames that never arrive.
        websocket = getattr(self._stream_client, "websocket", None) if self._stream_client else None
        if websocket is not None:
            await self._quiet(websocket.close(), "[%s] websocket close during disconnect failed: %s")
        if self._stream_task:
            if hasattr(self._stream_client, "close"):
                await self._quiet(asyncio.to_thread(self._stream_client.close))  # sync close() may block on I/O
            self._stream_task.cancel()
            try:
                await asyncio.wait_for(self._stream_task, timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                logger.debug("[%s] stream task did not exit cleanly during disconnect", self.name)
            self._stream_task = None
        for task in list(self._bg_tasks):
            task.cancel()
        if self._bg_tasks:
            await asyncio.gather(*self._bg_tasks, return_exceptions=True)
        # Finalize open streaming cards BEFORE the HTTP client closes so they don't stay stuck
        # in streaming state after a gateway restart. Outer try guards the token fetch.
        for _chat_id in list(self._streaming_cards):
            await self._quiet(self._close_streaming_siblings(_chat_id), "[%s] Failed to finalize streaming card on disconnect for %s: %s", _chat_id)
        if self._http_client:
            await self._http_client.aclose()
        self._http_client = self._stream_client = None
        for store in (self._session_webhooks, self._message_contexts, self._streaming_cards, self._done_emoji_fired, self._dedup, self._bg_tasks):
            store.clear()
        logger.info("[%s] Disconnected", self.name)

    def _extra_get(self, key: str, env_name: str = "", env_default: str = ""):
        """config.extra[key]; when *env_name* is given, absent keys fall back to the env var."""
        value = self.config.extra.get(key) if self.config.extra else None
        return os.getenv(env_name, env_default) if value is None and env_name else value

    def _csv_setting(self, key: str, env_name: str) -> Set[str]:
        """List/CSV setting from config.extra[key], falling back to the env var."""
        return _csv_set(self._extra_get(key, env_name))

    def _dingtalk_require_mention(self) -> bool:
        """Whether group chats require an explicit bot trigger."""
        configured = self._extra_get("require_mention", "DINGTALK_REQUIRE_MENTION", "false")
        return configured.lower() in _TRUTHY if isinstance(configured, str) else bool(configured)

    def _dingtalk_allowed_chats(self) -> Set[str]:
        """Group chat whitelist; non-empty = hard gate even when @mentioned. DMs never filtered."""
        return self._csv_setting("allowed_chats", "DINGTALK_ALLOWED_CHATS")

    def _compile_mention_patterns(self) -> List[re.Pattern]:
        """Compile optional regex wake-word patterns (config list, or env as JSON / lines / CSV)."""
        patterns = self._extra_get("mention_patterns")
        if patterns is None and (raw := os.getenv("DINGTALK_MENTION_PATTERNS", "").strip()):
            try:
                patterns = json.loads(raw)
            except Exception:
                patterns = [part.strip() for part in raw.splitlines() if part.strip()]
                if not patterns:
                    patterns = [part.strip() for part in raw.split(",") if part.strip()]
        if patterns is None:  # return before touching ``self.name`` on the no-patterns path (historical parity)
            return []
        return compile_mention_patterns(patterns, log_prefix=self.name, platform_label="dingtalk", display_label="DingTalk", logger_=logger)

    def _is_user_allowed(self, sender_id: str, sender_staff_id: str) -> bool:
        if not self._allowed_users or "*" in self._allowed_users:
            return True
        return bool(({(sender_id or "").lower(), (sender_staff_id or "").lower()} - {""}) & self._allowed_users)

    def _message_matches_mention_patterns(self, text: str) -> bool:
        return bool(text and self._mention_patterns) and any(p.search(text) for p in self._mention_patterns)

    def _should_process_message(self, message: "ChatbotMessage", text: str, is_group: bool, chat_id: str) -> bool:
        """Group trigger rules (DMs always pass; ``allowed_users`` is enforced earlier): ``allowed_chats`` is a hard
        gate, then any of free_response_chats / require_mention off / @mentioned (SDK ``is_in_at_list``) / wake-word."""
        if not is_group:
            return True
        allowed = self._dingtalk_allowed_chats()
        if allowed and chat_id and chat_id not in allowed:
            return False
        return (
            bool(chat_id and chat_id in self._csv_setting("free_response_chats", "DINGTALK_FREE_RESPONSE_CHATS"))
            or not self._dingtalk_require_mention()
            or bool(getattr(message, "is_in_at_list", False))
            or self._message_matches_mention_patterns(text)
        )

    def _spawn_bg(self, coro) -> None:
        """Start a fire-and-forget coroutine and track it for cleanup."""
        self._bg_tasks.add(task := asyncio.create_task(coro))
        task.add_done_callback(self._bg_tasks.discard)

    async def _close_streaming_siblings(self, chat_id: str) -> None:
        """Finalize open streaming cards for this chat at the start of every ``send()`` — the gateway has no "turn end" signal, so this is what closes lingering tool-progress cards."""
        cards = self._streaming_cards.pop(chat_id, None)
        token = await self._get_access_token() if cards else None
        for out_track_id, last_content in list(cards.items()) if token else ():
            try:
                await self._stream_card_content(out_track_id, token, last_content, finalize=True)
                logger.debug("[%s] AI Card sibling closed: %s", self.name, out_track_id)
            except Exception as e:
                logger.debug("[%s] Sibling close failed for %s: %s", self.name, out_track_id, e)

    def _fire_done_reaction(self, chat_id: str) -> None:
        """Swap 🤔Thinking → 🥳Done on the original user message; idempotent per chat_id."""
        if chat_id in self._done_emoji_fired:
            return
        self._done_emoji_fired.add(chat_id)
        msg = self._message_contexts.get(chat_id)
        msg_id, conversation_id = (getattr(msg, "message_id", None) or "", getattr(msg, "conversation_id", None) or "") if msg else ("", "")
        if not (msg_id and conversation_id):
            return
        async def _swap() -> None:
            await self._send_emotion(msg_id, conversation_id, "🤔Thinking", recall=True)
            await self._send_emotion(msg_id, conversation_id, "🥳Done", recall=False)
        self._spawn_bg(_swap())

    async def _on_message(self, message: "ChatbotMessage") -> None:
        """Process an incoming DingTalk chatbot message."""
        msg_id = getattr(message, "message_id", None) or uuid.uuid4().hex
        if self._dedup.is_duplicate(msg_id):
            return logger.debug("[%s] Duplicate message %s, skipping", self.name, msg_id)
        conversation_id, sender_id, sender_nick, sender_staff_id = (getattr(message, k, "") or "" for k in ("conversation_id", "sender_id", "sender_nick", "sender_staff_id"))
        is_group = str(getattr(message, "conversation_type", "1")) == "2"
        sender_nick = sender_nick or sender_id
        chat_id = conversation_id or sender_id
        if not self._is_user_allowed(sender_id, sender_staff_id):
            return logger.debug("[%s] Dropping message from non-allowlisted user staff_id=%s sender_id=%s", self.name, sender_staff_id, sender_id)
        if not self._should_process_message(message, self._extract_text(message) or "", is_group, chat_id):  # wake-word gate needs text early
            return logger.debug("[%s] Dropping group message that failed mention gate message_id=%s chat_id=%s", self.name, msg_id, chat_id)
        # Per-chat context; reset the Done marker so this message gets its own Thinking→Done cycle.
        if chat_id:
            self._message_contexts[chat_id] = message
            self._done_emoji_fired.discard(chat_id)
        session_webhook = getattr(message, "session_webhook", None) or ""
        if session_webhook and chat_id and _DINGTALK_WEBHOOK_RE.match(session_webhook):
            if len(self._session_webhooks) >= _SESSION_WEBHOOKS_MAX:
                self._session_webhooks.pop(next(iter(self._session_webhooks)))  # evict oldest (dict is non-empty here)
            self._session_webhooks[chat_id] = (session_webhook, getattr(message, "session_webhook_expired_time", 0) or 0)
        await self._resolve_media_codes(message)  # download codes -> URLs so vision tools can use them
        text = self._extract_text(message)
        msg_type, media_urls, media_types = self._extract_media(message)
        cached_paths = getattr(message, "_cached_file_paths", {})
        if cached_paths:
            media_urls = [cached_paths.get(value, value) for value in media_urls]
        if not text and not media_urls:
            return logger.debug("[%s] Empty message, skipping", self.name)
        source = self.build_source(chat_id=chat_id, chat_name=getattr(message, "conversation_title", None), chat_type="group" if is_group else "dm",
                                   user_id=sender_id, user_name=sender_nick, user_id_alt=sender_staff_id if sender_staff_id else None)
        create_at = getattr(message, "create_at", None)
        try:
            timestamp = datetime.fromtimestamp(int(create_at) / 1000, tz=timezone.utc) if create_at else datetime.now(tz=timezone.utc)
        except (ValueError, OSError, TypeError):
            timestamp = datetime.now(tz=timezone.utc)
        logger.debug("[%s] Message from %s in %s: %s", self.name, sender_nick, chat_id[:20] if chat_id else "?", text[:80] if text else "(media)")
        await self.handle_message(MessageEvent(text=text, message_type=msg_type, source=source, message_id=msg_id, raw_message=message,
                                               media_urls=media_urls, media_types=media_types, timestamp=timestamp))

    _extract_text = staticmethod(extract_text)

    def _extract_media(self, message: "ChatbotMessage"):
        return extract_media(message)

    async def send(self, chat_id: str, content: str, reply_to: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> SendResult:
        """Send a reply via AI Card (when configured) or DingTalk session webhook markdown."""
        metadata = metadata or {}
        logger.debug("[%s] send() chat_id=%s card_enabled=%s", self.name, chat_id, bool(self._card_template_id and self._card_sdk))
        session_webhook = metadata.get("session_webhook") or (self._get_valid_webhook(chat_id) or ("",))[0]
        if not session_webhook:
            logger.warning("[%s] No valid session_webhook for chat_id=%s", self.name, chat_id)
            return SendResult(success=False, error="No valid session_webhook available. Reply must follow an incoming message.")
        if not self._http_client:
            return SendResult(success=False, error="HTTP client not initialized")
        current_message = self._message_contexts.get(chat_id)
        # ``reply_to`` is only set by base.py:_send_with_retry for the FINAL reply to an inbound message;
        # tool-progress, commentary and stream first-sends leave it None. It decides (1) finalize-on-create
        # (intermediate cards stay open so edits don't flicker) and (2) whether to fire the Done reaction.
        is_final_reply = reply_to is not None
        if self._card_template_id and current_message and self._card_sdk:
            await self._close_streaming_siblings(chat_id)  # close lingering tool-progress cards before creating a new one
            result = await self._create_and_stream_card(chat_id, current_message, content, finalize=is_final_reply)
            if result and result.success:
                if is_final_reply:
                    self._fire_done_reaction(chat_id)
                else:  # keep open + track so the next send() auto-closes it, or edit_message(finalize=True) does
                    self._streaming_cards.setdefault(chat_id, {})[result.message_id] = content
                return result
            logger.warning("[%s] AI Card send failed, falling back to webhook", self.name)
        logger.debug("[%s] Sending via webhook", self.name)
        payload = {"msgtype": "markdown", "markdown": {"title": "Hermes", "text": self._normalize_markdown(content[: self.MAX_MESSAGE_LENGTH])}}
        try:
            resp = await self._http_client.post(session_webhook, json=payload, timeout=15.0)
            if resp.status_code < 300:
                if is_final_reply:
                    self._fire_done_reaction(chat_id)
                return SendResult(success=True, message_id=uuid.uuid4().hex[:12])
            logger.warning("[%s] Send failed HTTP %d: %s", self.name, resp.status_code, resp.text[:200])
            return SendResult(success=False, error=f"HTTP {resp.status_code}: {resp.text[:200]}")
        except httpx.TimeoutException:
            return SendResult(success=False, error="Timeout sending message to DingTalk")
        except Exception as e:
            logger.error("[%s] Send error: %s", self.name, e)
            return SendResult(success=False, error=str(e))

    async def send_typing(self, chat_id: str, metadata=None) -> None:
        """DingTalk does not support typing indicators."""

    async def send_image(self, chat_id: str, image_url: str, caption: Optional[str] = None, reply_to: Optional[str] = None, metadata=None) -> SendResult:
        """Render a remote image inline via markdown (session webhook has no native attachments)."""
        image_block = f"![image]({image_url})"
        return await self.send(chat_id=chat_id, content=f"{caption}\n\n{image_block}" if caption else image_block, reply_to=reply_to, metadata=metadata)

    async def send_image_file(
        self,
        chat_id: str,
        image_path: str,
        caption: Optional[str] = None,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> SendResult:
        """DingTalk webhook replies cannot send local image files directly."""
        return SendResult(
            success=False,
            error=(
                "DingTalk session webhook replies do not support local image uploads. "
                "Only markdown/text replies are supported without OpenAPI media upload."
            ),
        )


    async def send_document(
        self,
        chat_id: str,
        file_path: str,
        caption: Optional[str] = None,
        file_name: Optional[str] = None,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> SendResult:
        """Upload and send a local document to the verified current DM user.

        Session webhooks cannot carry attachments, so this uses DingTalk's
        authenticated media upload + robot one-to-one ``sampleFile`` APIs. The
        recipient is read only from the inbound message's ``sender_staff_id``;
        conversation IDs, sender IDs and AgentIds are never guessed as UserIds.
        """
        path = Path(file_path).expanduser()
        if not path.is_file():
            return SendResult(success=False, error=f"Local file not found: {path}")
        try:
            file_size = path.stat().st_size
        except OSError as exc:
            return SendResult(success=False, error=f"Cannot stat local file: {exc}")
        if file_size <= 0:
            return SendResult(success=False, error="Cannot send an empty file")
        if file_size > _DINGTALK_MEDIA_MAX_BYTES:
            return SendResult(
                success=False,
                error=(
                    f"DingTalk media upload limit is {_DINGTALK_MEDIA_MAX_BYTES} bytes; "
                    f"file is {file_size} bytes"
                ),
            )
        if not self._http_client:
            return SendResult(success=False, error="HTTP client not initialized")
        http_client = self._http_client

        current_message = self._message_contexts.get(chat_id)
        if current_message is None:
            return SendResult(
                success=False,
                error=(
                    "No inbound DingTalk context for this chat; refusing to guess "
                    "a recipient UserId without sender_staff_id"
                ),
            )
        if str(getattr(current_message, "conversation_type", "1")) == "2":
            return SendResult(
                success=False,
                error=(
                    "Local file OpenAPI delivery is currently limited to DingTalk DM; "
                    "group delivery requires the separate groupMessages contract"
                ),
            )
        staff_id = str(getattr(current_message, "sender_staff_id", "") or "").strip()
        if not staff_id:
            return SendResult(
                success=False,
                error="Inbound DingTalk DM is missing verified sender_staff_id",
            )

        try:
            token = await self._get_access_token()
        except Exception as exc:
            logger.warning(
                "[%s] Could not obtain DingTalk access token (%s)",
                self.name,
                type(exc).__name__,
            )
            return SendResult(
                success=False,
                error="Could not obtain DingTalk access token",
            )
        if not token:
            return SendResult(success=False, error="No DingTalk access token")

        safe_name = Path(file_name or path.name).name.strip() or path.name
        file_type = Path(safe_name).suffix.lower().lstrip(".") or "file"
        mime_type = mimetypes.guess_type(safe_name)[0] or "application/octet-stream"
        try:
            with path.open("rb") as handle:
                upload_response = await http_client.post(
                    _DINGTALK_MEDIA_UPLOAD_URL,
                    params={"access_token": token, "type": "file"},
                    files={"media": (safe_name, handle, mime_type)},
                    timeout=30.0,
                )
            upload_payload, upload_error = self._decode_openapi_response(
                upload_response, "media upload",
            )
            if upload_error:
                return SendResult(success=False, error=upload_error)
            media_id = str(
                upload_payload.get("media_id") or upload_payload.get("mediaId") or ""
            ).strip()
            if not media_id:
                return SendResult(
                    success=False,
                    error="DingTalk media upload returned no media_id",
                )

            send_response = await http_client.post(
                _DINGTALK_OTO_BATCH_SEND_URL,
                headers={"x-acs-dingtalk-access-token": token},
                json={
                    "robotCode": self._robot_code,
                    "userIds": [staff_id],
                    "msgKey": "sampleFile",
                    "msgParam": json.dumps(
                        {
                            "mediaId": media_id,
                            "fileName": safe_name,
                            "fileType": file_type,
                        },
                        ensure_ascii=False,
                    ),
                },
                timeout=30.0,
            )
            send_payload, send_error = self._decode_openapi_response(
                send_response, "one-to-one file send",
            )
            if send_error:
                return SendResult(success=False, error=send_error)
            invalid = {str(value) for value in send_payload.get("invalidStaffIdList", [])}
            throttled = {
                str(value) for value in send_payload.get("flowControlledStaffIdList", [])
            }
            if staff_id in invalid:
                return SendResult(
                    success=False,
                    error="DingTalk rejected the verified sender_staff_id as invalid",
                )
            if staff_id in throttled:
                return SendResult(
                    success=False,
                    error="DingTalk flow-controlled the file recipient",
                    retryable=True,
                )
            process_query_key = str(send_payload.get("processQueryKey") or "").strip()
            if not process_query_key:
                return SendResult(
                    success=False,
                    error="DingTalk file send returned no processQueryKey",
                )

            confirmed, status_payload, status_error = await self._confirm_oto_delivery(
                token, process_query_key, staff_id,
            )
            if not confirmed:
                return SendResult(
                    success=False,
                    error=status_error or "DingTalk delivery did not reach SUCCESS",
                    raw_response=status_payload,
                    retryable=(status_payload or {}).get("sendStatus") == "PROCESSING",
                )
            read_status = next(
                (
                    str(item.get("readStatus") or "")
                    for item in status_payload.get("messageReadInfoList", [])
                    if str(item.get("userId") or "") == staff_id
                ),
                "",
            )
            logger.info(
                "[%s] DingTalk file delivered: query=%s read=%s",
                self.name,
                process_query_key[:16],
                read_status or "unknown",
            )
            if caption:
                logger.debug(
                    "[%s] DingTalk sampleFile does not carry a separate caption; file sent without caption",
                    self.name,
                )
            return SendResult(
                success=True,
                message_id=process_query_key,
                raw_response=status_payload,
            )
        except Exception as exc:
            error = str(exc).replace(token, "[REDACTED]")
            logger.warning("[%s] DingTalk local file send failed: %s", self.name, error)
            return SendResult(success=False, error=error)


    @staticmethod
    def _probe_voice_audio(audio_path: str) -> tuple[str, int]:
        """Return ffprobe format name and duration in milliseconds."""
        proc = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=format_name,duration",
                "-of", "json", audio_path,
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=True,
        )
        data = json.loads(proc.stdout or "{}")
        fmt = str((data.get("format") or {}).get("format_name") or "").lower()
        seconds = float((data.get("format") or {}).get("duration") or 0)
        if seconds <= 0:
            raise RuntimeError("Unable to determine DingTalk voice duration")
        return fmt, max(1, int(round(seconds * 1000)))

    @classmethod
    def _prepare_dingtalk_voice(cls, audio_path: str) -> tuple[str, int, Optional[str]]:
        """Guarantee a real Ogg/Opus payload accepted by sampleAudio."""
        source = Path(audio_path).expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError(f"Audio file not found: {source}")
        fmt, duration_ms = cls._probe_voice_audio(str(source))
        if "ogg" in fmt and source.suffix.lower() == ".ogg":
            prepared = str(source)
            cleanup = None
        else:
            fd, converted = tempfile.mkstemp(prefix="hermes-dingtalk-", suffix=".ogg")
            os.close(fd)
            try:
                subprocess.run(
                    [
                        "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                        "-i", str(source), "-vn", "-ac", "1", "-ar", "48000",
                        "-c:a", "libopus", "-b:a", "32k", converted,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=True,
                )
                converted_fmt, duration_ms = cls._probe_voice_audio(converted)
                if "ogg" not in converted_fmt:
                    raise RuntimeError("FFmpeg did not produce an Ogg voice file")
                prepared, cleanup = converted, converted
            except Exception:
                try:
                    os.remove(converted)
                except OSError:
                    pass
                raise
        if os.path.getsize(prepared) > 2 * 1024 * 1024:
            if cleanup:
                try:
                    os.remove(cleanup)
                except OSError:
                    pass
            raise RuntimeError("DingTalk voice file exceeds the official 2 MB limit")
        return prepared, duration_ms, cleanup

    def _send_dingtalk_voice_sync(
        self,
        chat_id: str,
        audio_path: str,
        metadata: Optional[Dict[str, Any]],
        token: str,
    ) -> SendResult:
        import requests

        prepared = None
        cleanup = None
        try:
            prepared, duration_ms, cleanup = self._prepare_dingtalk_voice(audio_path)
            with open(prepared, "rb") as handle:
                upload = requests.post(
                    "https://oapi.dingtalk.com/media/upload",
                    params={"access_token": token, "type": "voice"},
                    files={"media": (Path(prepared).name, handle, "audio/ogg")},
                    timeout=60,
                )
            upload.raise_for_status()
            upload_data = upload.json()
            media_id = upload_data.get("media_id")
            if upload_data.get("errcode", 0) != 0 or not media_id:
                raise RuntimeError(
                    f"DingTalk voice upload failed: {upload_data.get('errmsg', 'missing media_id')}"
                )

            headers = {
                "x-acs-dingtalk-access-token": token,
                "Content-Type": "application/json",
            }
            params = json.dumps(
                {"mediaId": media_id, "duration": str(duration_ms)},
                ensure_ascii=False,
            )
            meta = metadata or {}
            current_message = self._message_contexts.get(chat_id)
            conversation_id = str(meta.get("conversation_id") or "").strip()
            sender_staff_id = str(meta.get("sender_staff_id") or "").strip()
            is_group = str(meta.get("conversation_type") or "") == "2"
            if current_message is not None:
                current_type = str(getattr(current_message, "conversation_type", "1"))
                if current_type == "2":
                    is_group = True
                    conversation_id = str(
                        getattr(current_message, "conversation_id", "") or conversation_id
                    ).strip()
                else:
                    sender_staff_id = str(
                        getattr(current_message, "sender_staff_id", "") or sender_staff_id
                    ).strip()
            if is_group:
                if not conversation_id:
                    raise RuntimeError(
                        "DingTalk group voice delivery requires a verified conversation_id"
                    )
                endpoint = "https://api.dingtalk.com/v1.0/robot/groupMessages/send"
                payload = {
                    "robotCode": self._client_id,
                    "openConversationId": conversation_id,
                    "msgKey": "sampleAudio",
                    "msgParam": params,
                }
            else:
                if not sender_staff_id:
                    raise RuntimeError(
                        "DingTalk DM voice delivery requires a verified sender_staff_id"
                    )
                endpoint = "https://api.dingtalk.com/v1.0/robot/oToMessages/batchSend"
                payload = {
                    "robotCode": self._client_id,
                    "userIds": [sender_staff_id],
                    "msgKey": "sampleAudio",
                    "msgParam": params,
                }
            sent = requests.post(endpoint, headers=headers, json=payload, timeout=30)
            if not sent.ok:
                try:
                    failure = sent.json()
                    detail = failure.get("message") or failure.get("errmsg") or failure.get("code")
                except Exception:
                    detail = sent.text[:500]
                raise RuntimeError(f"DingTalk sampleAudio send failed (HTTP {sent.status_code}): {detail}")
            data = sent.json() if sent.content else {}
            message_id = data.get("processQueryKey") or data.get("messageId") or media_id
            return SendResult(success=True, message_id=str(message_id))
        except Exception as exc:
            logger.error("[DingTalk] Voice send failed: %s", exc, exc_info=True)
            return SendResult(success=False, error=str(exc))
        finally:
            if cleanup:
                try:
                    os.remove(cleanup)
                except OSError:
                    pass

    async def send_voice(
        self,
        chat_id: str,
        audio_path: str,
        caption: Optional[str] = None,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> SendResult:
        """Upload Ogg voice media and deliver a native sampleAudio message."""
        del caption, reply_to, kwargs  # sampleAudio has no caption/reply fields.
        token = await self._get_access_token()
        if not token:
            return SendResult(success=False, error="Could not obtain DingTalk access token")
        return await asyncio.to_thread(
            self._send_dingtalk_voice_sync,
            chat_id,
            audio_path,
            metadata,
            token,
        )

    @staticmethod
    def _decode_openapi_response(
        response: Any,
        operation: str,
    ) -> tuple[dict, Optional[str]]:
        """Decode DingTalk JSON without leaking request credentials."""
        try:
            payload = response.json()
        except Exception:
            payload = {}
        status_code = int(getattr(response, "status_code", 0) or 0)
        code = payload.get("code") or payload.get("errcode")
        if status_code >= 300 or code not in (None, 0, "0"):
            message = payload.get("message") or payload.get("errmsg") or "unknown error"
            return (
                payload,
                f"DingTalk {operation} failed "
                f"(HTTP {status_code}, code={code}): {message}",
            )
        return payload, None

    async def _confirm_oto_delivery(
        self,
        token: str,
        process_query_key: str,
        staff_id: str,
    ) -> tuple[bool, dict, Optional[str]]:
        """Poll DingTalk until the one-to-one message is confirmed SUCCESS."""
        last_payload: dict = {}
        http_client = self._http_client
        if http_client is None:
            return False, last_payload, "HTTP client not initialized"
        for index, delay in enumerate(_FILE_STATUS_POLL_DELAYS):
            if delay:
                await asyncio.sleep(delay)
            response = await http_client.get(
                _DINGTALK_OTO_READ_STATUS_URL,
                headers={"x-acs-dingtalk-access-token": token},
                params={
                    "robotCode": self._robot_code,
                    "processQueryKey": process_query_key,
                },
                timeout=15.0,
            )
            payload, error = self._decode_openapi_response(response, "delivery status query")
            if error:
                code = str(payload.get("code") or payload.get("errcode") or "")
                # DingTalk uses the same code while the asynchronous query row
                # is not generated yet and after it expires. Within this short
                # post-send window it is safe to retry; an actually expired key
                # remains a failure when the bounded poll window ends.
                if (
                    code in {"processQueryKey.expireTime", "unknown.send.result"}
                    and index + 1 < len(_FILE_STATUS_POLL_DELAYS)
                ):
                    last_payload = payload
                    continue
                return False, payload, error
            last_payload = payload
            send_status = str(payload.get("sendStatus") or "").upper()
            if send_status == "SUCCESS":
                recipients = {
                    str(item.get("userId") or "")
                    for item in payload.get("messageReadInfoList", [])
                }
                if recipients and staff_id not in recipients:
                    return (
                        False,
                        payload,
                        "DingTalk SUCCESS receipt did not contain the intended sender_staff_id",
                    )
                return True, payload, None
            if send_status and send_status != "PROCESSING":
                return False, payload, f"DingTalk delivery status is {send_status}, not SUCCESS"
        return (
            False,
            last_payload,
            "DingTalk delivery remained PROCESSING and did not reach SUCCESS",
        )

    async def get_chat_info(self, chat_id: str) -> Dict[str, Any]:
        """Return basic info about a DingTalk conversation."""
        return {"name": chat_id, "type": "group" if "group" in chat_id.lower() else "dm"}

    def _get_valid_webhook(self, chat_id: str) -> Optional[tuple[str, int]]:
        """Get a non-expired session webhook for chat_id (5-minute safety margin)."""
        info = self._session_webhooks.get(chat_id)
        expired_time_ms = info[1] if info else 0
        if expired_time_ms and expired_time_ms > 0 and int(datetime.now(tz=timezone.utc).timestamp() * 1000) + 5 * 60 * 1000 >= expired_time_ms:
            self._session_webhooks.pop(chat_id, None)
            return None
        return info or None

    async def _create_and_stream_card(self, chat_id: str, message: Any, content: str, *, finalize: bool = True) -> Optional[SendResult]:
        """Create, deliver and stream an AI Card; ``finalize=False`` leaves it open for ``edit_message`` by out_track_id."""
        try:
            token = await self._get_access_token()
            if not token:
                return None
            out_track_id, models = f"hermes_{uuid.uuid4().hex[:12]}", dingtalk_card_models
            is_group = str(getattr(message, "conversation_type", "1")) == "2"
            sender_staff_id = getattr(message, "sender_staff_id", "") or ""
            create_request = models.CreateCardRequest(
                card_template_id=self._card_template_id, out_track_id=out_track_id, callback_type="STREAM",
                card_data=models.CreateCardRequestCardData(card_param_map={"content": ""}),
                im_group_open_space_model=models.CreateCardRequestImGroupOpenSpaceModel(support_forward=True),
                im_robot_open_space_model=models.CreateCardRequestImRobotOpenSpaceModel(support_forward=True))
            await self._sdk_call(self._card_sdk.create_card_with_options_async, create_request, models.CreateCardHeaders, token)
            if is_group:
                open_space_id = f"dtv1.card//IM_GROUP.{getattr(message, 'conversation_id', '') or ''}"
                deliver_model = {"im_group_open_deliver_model": models.DeliverCardRequestImGroupOpenDeliverModel(robot_code=self._robot_code)}
            elif sender_staff_id:
                open_space_id = f"dtv1.card//IM_ROBOT.{sender_staff_id}"
                deliver_model = {"im_robot_open_deliver_model": models.DeliverCardRequestImRobotOpenDeliverModel(space_type="IM_ROBOT")}
            else:
                return logger.warning("[%s] AI Card skipped: missing sender_staff_id for DM", self.name)
            deliver_request = models.DeliverCardRequest(out_track_id=out_track_id, user_id_type=1, open_space_id=open_space_id, **deliver_model)
            await self._sdk_call(self._card_sdk.deliver_card_with_options_async, deliver_request, models.DeliverCardHeaders, token)
            await self._stream_card_content(out_track_id, token, content, finalize=finalize)
            logger.info("[%s] AI Card %s: %s", self.name, "created+finalized" if finalize else "created (streaming)", out_track_id)
            return SendResult(success=True, message_id=out_track_id)
        except Exception as e:
            logger.warning("[%s] AI Card create failed: %s\n%s", self.name, e, traceback.format_exc())
            return None

    async def edit_message(self, chat_id: str, message_id: str, content: str, *, finalize: bool = False) -> SendResult:
        """Stream updated content to an AI Card; ``message_id`` is the creating ``send()``'s out_track_id (callers track their own ids so parallel flows on one chat don't interfere)."""
        token = await self._get_access_token() if message_id else None
        if not token:
            return SendResult(success=False, error="message_id required" if not message_id else "No access token")
        try:
            await self._stream_card_content(message_id, token, content, finalize=finalize)
            if finalize:  # canonical "response ended" signal from the stream consumer's final edit
                self._streaming_cards.get(chat_id, {}).pop(message_id, None)
                if not self._streaming_cards.get(chat_id):
                    self._streaming_cards.pop(chat_id, None)
                logger.debug("[%s] AI Card finalized (edit): %s", self.name, message_id)
                self._fire_done_reaction(chat_id)
            else:  # non-final edit reopens the card into streaming state — track for sibling close
                self._streaming_cards.setdefault(chat_id, {})[message_id] = content
            return SendResult(success=True, message_id=message_id)
        except Exception as e:
            logger.warning("[%s] Card edit failed: %s", self.name, e)
            return SendResult(success=False, error=str(e))

    @staticmethod
    async def _sdk_call(method, request, headers_cls, token: str):
        """``await method(request, headers_cls(token), RuntimeOptions())`` — the alibabacloud SDK call shape."""
        return await method(request, headers_cls(x_acs_dingtalk_access_token=token), tea_util_models.RuntimeOptions())

    async def _stream_card_content(self, out_track_id: str, token: str, content: str, finalize: bool = False) -> None:
        """Stream content to an existing AI Card."""
        stream_request = dingtalk_card_models.StreamingUpdateRequest(
            out_track_id=out_track_id, guid=str(uuid.uuid4()), key="content", content=content[: self.MAX_MESSAGE_LENGTH],
            is_full=True, is_finalize=finalize, is_error=False,
        )
        await self._sdk_call(self._card_sdk.streaming_update_with_options_async, stream_request, dingtalk_card_models.StreamingUpdateHeaders, token)

    async def _get_access_token(self) -> Optional[str]:
        """Get access token via the SDK's cached (sync, requests-based) getter."""
        if not self._stream_client:
            return None
        try:
            return await asyncio.to_thread(self._stream_client.get_access_token)
        except Exception as e:
            logger.error("[%s] Failed to get access token: %s", self.name, e)
            return None

    async def _send_emotion(self, open_msg_id: str, open_conversation_id: str, emoji_name: str, *, recall: bool = False) -> None:
        """Add (or recall) an emoji reaction on a message."""
        if not self._robot_sdk or not open_msg_id or not open_conversation_id:
            return
        action = "recall" if recall else "reply"
        try:
            token = await self._get_access_token()
            if not token:
                return
            text_emotion_cls, request_cls, headers_cls, sdk_method = _EMOTION_SDK[recall]
            text_emotion = getattr(dingtalk_robot_models, text_emotion_cls)(emotion_id=_EMOTION_ID, emotion_name=emoji_name, text=emoji_name, background_id=_EMOTION_BG)
            request = getattr(dingtalk_robot_models, request_cls)(robot_code=self._robot_code, open_msg_id=open_msg_id, open_conversation_id=open_conversation_id,
                                                                  emotion_type=2, emotion_name=emoji_name, text_emotion=text_emotion)
            await self._sdk_call(getattr(self._robot_sdk, sdk_method), request, getattr(dingtalk_robot_models, headers_cls), token)
            logger.info("[%s] _send_emotion: %s %s on msg=%s", self.name, action, emoji_name, open_msg_id[:24])
        except Exception:
            logger.debug("[%s] _send_emotion %s failed", self.name, action, exc_info=True)

    async def _fetch_and_cache_file(
        self,
        code: str,
        robot_code: str,
        token: str,
        filename: str,
        message: Any,
        *,
        media_kind: str = "document",
    ) -> None:
        """Resolve a native DingTalk download code, download bytes, cache locally.

        DingTalk's temporary download URLs are not durable and STT/document
        tooling needs local readable paths. On success, ``message._cached_file_paths``
        maps the original download code to the local cache path; ``_extract_media``
        still returns the original code and the caller substitutes the cached path.
        """
        if not self._robot_sdk:
            logger.warning("[%s] Robot SDK not initialized, cannot download file", self.name)
            return
        if not self._http_client:
            logger.warning("[%s] HTTP client not available, cannot download file", self.name)
            return

        try:
            request = dingtalk_robot_models.RobotMessageFileDownloadRequest(
                download_code=code,
                robot_code=robot_code,
            )
            headers = dingtalk_robot_models.RobotMessageFileDownloadHeaders(
                x_acs_dingtalk_access_token=token,
            )
            runtime = tea_util_models.RuntimeOptions()
            response = await self._robot_sdk.robot_message_file_download_with_options_async(
                request, headers, runtime
            )
            body = response.body if response else None
            download_url = getattr(body, "download_url", None) if body else None
            if not download_url:
                logger.warning("[%s] No download_url in response for code %s", self.name, code)
                return

            resp = await self._http_client.get(
                download_url,
                headers={"User-Agent": "HermesAgent/1.0"},
                follow_redirects=True,
            )
            resp.raise_for_status()
            file_bytes = resp.content
            if not file_bytes:
                logger.warning("[%s] Empty file bytes for %s", self.name, filename or code)
                return

            if media_kind == "audio":
                safe_name = (filename or "").strip().lower()
                ext = os.path.splitext(safe_name)[1] if safe_name else ""
                if not ext:
                    if file_bytes[:4] == b"OggS":
                        ext = ".ogg"
                    elif file_bytes[:4] == b"\x1a\x45\xdf\xa3":
                        ext = ".webm"
                    else:
                        ext = ".ogg"
                cached_path = cache_audio_from_bytes(file_bytes, ext)
            else:
                cached_path = cache_document_from_bytes(file_bytes, filename or "document")

            logger.info(
                "[%s] Cached DingTalk %s '%s' → %s (%d bytes)",
                self.name, media_kind, filename or code, cached_path, len(file_bytes),
            )
            if not hasattr(message, "_cached_file_paths"):
                message._cached_file_paths = {}
            message._cached_file_paths[code] = cached_path

        except Exception as exc:
            logger.error("[%s] Failed to download/cache file (code=%s): %s", self.name, code, exc)

    async def _resolve_media_codes(self, message: "ChatbotMessage") -> None:
        """Resolve download codes in message to actual URLs."""
        token = await self._get_access_token()
        if not token:
            return

        robot_code = getattr(message, "robot_code", None) or self._client_id
        codes_to_resolve = []

        # Collect codes and references to update
        # 1. Single image content
        img_content = getattr(message, "image_content", None)
        if img_content and getattr(img_content, "download_code", None):
            codes_to_resolve.append((img_content, "download_code"))

        # 2. Rich text list
        rich_text = getattr(message, "rich_text_content", None)
        if rich_text:
            rich_list = getattr(rich_text, "rich_text_list", []) or []
            for item in rich_list:
                if isinstance(item, dict):
                    for key in ("downloadCode", "pictureDownloadCode", "download_code"):
                        if item.get(key):
                            codes_to_resolve.append((item, key))

        # 3. Native voice/audio and file attachments from extensions.content.
        # Runs before _extract_media, so read the raw message_type directly.
        msg_type_str_here = getattr(message, "message_type", "") or ""
        extensions_here = getattr(message, "extensions", None) or {}
        native_content_here = (
            extensions_here.get("content")
            if isinstance(extensions_here, dict)
            else None
        )

        if msg_type_str_here in {"voice", "audio"} and isinstance(native_content_here, dict):
            dl_code_here = (
                native_content_here.get("downloadCode")
                or native_content_here.get("download_code")
                or native_content_here.get("mediaId")
                or native_content_here.get("media_id")
                or ""
            )
            recognition_here = str(native_content_here.get("recognition", "") or "").strip()
            if dl_code_here and (msg_type_str_here == "voice" or not recognition_here):
                message._native_audio_meta = getattr(message, "_native_audio_meta", {})
                message._native_audio_meta[dl_code_here] = (
                    native_content_here.get("fileName")
                    or native_content_here.get("file_name")
                    or ""
                )

        if msg_type_str_here == "file" and isinstance(native_content_here, dict):
            dl_code_here = (
                native_content_here.get("downloadCode")
                or native_content_here.get("download_code")
                or ""
            )
            fname_here = (
                native_content_here.get("fileName")
                or native_content_here.get("file_name")
                or ""
            )
            if dl_code_here:
                message._native_file_meta = getattr(message, "_native_file_meta", {})
                message._native_file_meta[dl_code_here] = fname_here

        audio_codes_to_download: list[tuple[str, str]] = [
            (dl_code, fname)
            for dl_code, fname in getattr(message, "_native_audio_meta", {}).items()
            if dl_code
        ]
        file_codes_to_download: list[tuple[str, str]] = [
            (dl_code, filename)
            for dl_code, filename in getattr(message, "_native_file_meta", {}).items()
            if dl_code
        ]

        # Upstream also resolves native image download codes to temporary URLs.
        # Native files stay on the local-cache path above so document tools get
        # a durable readable file instead of a short-lived URL.
        if msg_type_str_here == "image" and isinstance(native_content_here, dict):
            if native_content_here.get("downloadCode"):
                codes_to_resolve.append((native_content_here, "downloadCode"))

        if not codes_to_resolve and not file_codes_to_download and not audio_codes_to_download:
            return

        # Resolve all codes in parallel
        tasks = []
        for obj, key in codes_to_resolve:
            code = getattr(obj, key, None) if hasattr(obj, key) else obj.get(key)
            if code:
                tasks.append(
                    self._fetch_download_url(code, robot_code, token, obj, key)
                )

        for dl_code, filename in audio_codes_to_download:
            tasks.append(
                self._fetch_and_cache_file(
                    dl_code, robot_code, token, filename, message, media_kind="audio"
                )
            )
        for dl_code, filename in file_codes_to_download:
            tasks.append(
                self._fetch_and_cache_file(
                    dl_code, robot_code, token, filename, message, media_kind="document"
                )
            )

        await asyncio.gather(*tasks, return_exceptions=True)


    async def _fetch_download_url(
        self, code: str, robot_code: str, token: str, obj, key: str
    ) -> None:
        """Fetch download URL for a single code using the robot SDK."""
        if not self._robot_sdk:
            logger.warning(
                "[%s] Robot SDK not initialized, cannot resolve media code",
                self.name,
            )
            return
        try:
            request = dingtalk_robot_models.RobotMessageFileDownloadRequest(
                download_code=code,
                robot_code=robot_code,
            )
            headers = dingtalk_robot_models.RobotMessageFileDownloadHeaders(
                x_acs_dingtalk_access_token=token,
            )
            runtime = tea_util_models.RuntimeOptions()
            response = await self._robot_sdk.robot_message_file_download_with_options_async(
                request, headers, runtime
            )
            body = response.body if response else None
            if body:
                url = getattr(body, "download_url", None)
                if url:
                    if hasattr(obj, key):
                        setattr(obj, key, url)
                    elif isinstance(obj, dict):
                        obj[key] = url
            else:
                logger.warning(
                    "[%s] Failed to download media: empty response for code %s",
                    self.name,
                    code,
                )
        except Exception as e:
            logger.error("[%s] Error resolving media code %s: %s", self.name, code, e)


    @staticmethod
    def _normalize_markdown(text: str) -> str:
        """Work around DingTalk renderer quirks: blank line before numbered lists, dedent ``` fences."""
        lines = text.split("\n")
        out = []
        for i, line in enumerate(lines):
            prev = lines[i - 1].strip() if i > 0 else ""
            if prev and _NUMBERED_RE.match(line.strip()) and not _NUMBERED_RE.match(prev):
                out.append("")
            out.append(line.lstrip() if line.strip().startswith("```") else line)
        return "\n".join(out)


class _IncomingHandler(dingtalk_stream.ChatbotHandler if DINGTALK_STREAM_AVAILABLE else object):
    """ChatbotHandler forwarding to the adapter (SDK >= 0.20: async ``process()`` gets a CallbackMessage ``.data`` dict)."""

    def __init__(self, adapter: DingTalkAdapter, loop: Optional[asyncio.AbstractEventLoop] = None):
        if DINGTALK_STREAM_AVAILABLE:
            super().__init__()
        self._adapter, self._loop = adapter, loop

    def pre_start(self) -> None:
        """No-op hook the SDK calls on every handler before opening the WebSocket (missing → AttributeError)."""
        return

    async def process(self, message: "CallbackMessage"):
        """Convert to ChatbotMessage, dispatch as a background task, ACK immediately (blocking would stall SDK heartbeats)."""
        try:
            data = json.loads(message.data) if isinstance(message.data, str) else message.data
            chatbot_msg = ChatbotMessage.from_dict(data)
            data = data if isinstance(data, dict) else {}  # backfill fields from_dict() may not map (names vary across SDK versions)
            webhook = data.get("sessionWebhook") or data.get("session_webhook") or ""
            if webhook and not getattr(chatbot_msg, "session_webhook", None):
                chatbot_msg.session_webhook = webhook
            if not getattr(chatbot_msg, "is_in_at_list", False) and data.get("isInAtList"):
                chatbot_msg.is_in_at_list = True
            msg_id, conversation_id = getattr(chatbot_msg, "message_id", None) or "", getattr(chatbot_msg, "conversation_id", None) or ""
            if msg_id and conversation_id:
                self._adapter._spawn_bg(self._adapter._send_emotion(msg_id, conversation_id, "🤔Thinking", recall=False))
            asyncio.create_task(self._safe_on_message(chatbot_msg))  # surfaces exceptions in logs instead of losing them
        except Exception:
            logger.exception("[%s] Error preparing incoming message", self._adapter.name)
            return AckMessage.STATUS_SYSTEM_EXCEPTION, "error"
        return AckMessage.STATUS_OK, "OK"

    async def _safe_on_message(self, chatbot_msg: "ChatbotMessage") -> None:
        try:
            await self._adapter._on_message(chatbot_msg)
        except Exception:
            logger.exception("[%s] Error processing incoming message", self._adapter.name)


async def _standalone_send(pconfig, chat_id, message, *, thread_id=None, media_files=None, force_document=False):
    """Out-of-process delivery (standalone_sender_fn) via the static robot webhook (DINGTALK_WEBHOOK_URL / extra
    ``webhook_url``) — per-session webhooks aren't available to cron jobs."""
    try:
        import httpx
    except ImportError:
        return {"error": "httpx not installed"}
    webhook_url = (getattr(pconfig, "extra", {}) or {}).get("webhook_url") or os.getenv("DINGTALK_WEBHOOK_URL", "")
    if not webhook_url:
        return {"error": "DingTalk not configured. Set DINGTALK_WEBHOOK_URL env var or webhook_url in dingtalk platform extra config."}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(webhook_url, json={"msgtype": "text", "text": {"content": message}})
            resp.raise_for_status()
            data = resp.json()
        if data.get("errcode", 0) != 0:
            return {"error": f"DingTalk API error: {data.get('errmsg', 'unknown')}"}
        return {"success": True, "platform": "dingtalk", "chat_id": chat_id}
    except Exception as e:
        try:  # send_message_tool._error redacts access_token from webhook URLs (lazy import avoids a circular)
            from tools.send_message_tool import _error as _redact_error
            return _redact_error(f"DingTalk send failed: {e}")
        except Exception:
            return {"error": f"DingTalk send failed: {e}"}


def interactive_setup() -> None:
    """Configure DingTalk — QR scan (recommended) or manual credential entry."""
    from hermes_cli.config import get_env_value, save_env_value
    from hermes_cli.setup import prompt_choice
    from hermes_cli.cli_output import prompt, prompt_yes_no, print_header, print_success, print_warning
    print_header("DingTalk")
    if existing := get_env_value("DINGTALK_CLIENT_ID"):
        print_success(f"DingTalk is already configured (Client ID: {existing}).")
        if not prompt_yes_no("Reconfigure DingTalk?", False):
            return
    choices = ["QR Code Scan (Recommended, auto-obtain Client ID and Client Secret)", "Manual Input (Client ID and Client Secret)"]
    result = None
    if prompt_choice("Choose setup method", choices, default=0) == 0:
        try:
            from hermes_cli.dingtalk_auth import dingtalk_qr_auth
            result = dingtalk_qr_auth()
            if result is None:
                print_warning("QR auth incomplete, falling back to manual input.")
        except ImportError as exc:
            print_warning(f"QR auth module failed to load ({exc}), falling back to manual input.")
        if result is not None:
            for key, value in zip(("DINGTALK_CLIENT_ID", "DINGTALK_CLIENT_SECRET"), result):
                save_env_value(key, value)
            return print_success("DingTalk configured via QR scan!")
    _manual_credential_entry(prompt, save_env_value, print_success)


def _manual_credential_entry(prompt, save_env_value, print_success) -> None:
    client_id = prompt("DingTalk Client ID (app key)")
    if not client_id:
        return
    save_env_value("DINGTALK_CLIENT_ID", client_id)
    if client_secret := prompt("DingTalk Client Secret", password=True):
        save_env_value("DINGTALK_CLIENT_SECRET", client_secret)
    print_success("DingTalk credentials saved")


def _bridge_list_env(env_name: str, value) -> None:
    """Export a YAML list/scalar as a comma-joined env var unless the env var is already set."""
    if value is not None and not os.getenv(env_name):
        os.environ[env_name] = ",".join(str(v) for v in value) if isinstance(value, list) else str(value)


def _nested_allowed_users(yaml_cfg: dict, dingtalk_cfg: dict):
    """Allowlist from ``extra.allowed_users``: this block's own extra first, then ``gateway.platforms.dingtalk.extra`` and ``platforms.dingtalk.extra``."""
    _gw = yaml_cfg.get("gateway")
    containers = (_gw.get("platforms") if isinstance(_gw, dict) else None, yaml_cfg.get("platforms"))
    for holder in (dingtalk_cfg, *(c.get("dingtalk") if isinstance(c, dict) else None for c in containers)):
        _extra = holder.get("extra") if isinstance(holder, dict) else None
        if isinstance(_extra, dict) and _extra.get("allowed_users") is not None:
            return _extra.get("allowed_users")
    return None


def _apply_yaml_config(yaml_cfg: dict, dingtalk_cfg: dict) -> dict | None:
    """Translate config.yaml dingtalk: keys into DINGTALK_* env vars (apply_yaml_config_fn); env wins, returns None. The docs put the allowlist at
    ``gateway.platforms.dingtalk.extra.allowed_users`` but gateway authz only consults DINGTALK_ALLOWED_USERS, so nested-only allowlists are bridged too.

    Implements the apply_yaml_config_fn contract (#24849). Mirrors the legacy dingtalk_cfg block from
    gateway/config.py::load_gateway_config(). Env vars take precedence over YAML (each assignment guarded by
    not os.getenv(...)). Returns None — everything flows through env.
    """
    for key, env, encode in (("require_mention", "DINGTALK_REQUIRE_MENTION", lambda v: str(v).lower()), ("mention_patterns", "DINGTALK_MENTION_PATTERNS", json.dumps)):
        if key in dingtalk_cfg and not os.getenv(env):
            os.environ[env] = encode(dingtalk_cfg[key])
    allowed = dingtalk_cfg.get("allowed_users")
    for env, value in (("DINGTALK_FREE_RESPONSE_CHATS", dingtalk_cfg.get("free_response_chats")), ("DINGTALK_ALLOWED_CHATS", dingtalk_cfg.get("allowed_chats")),
                       ("DINGTALK_ALLOWED_USERS", _nested_allowed_users(yaml_cfg, dingtalk_cfg) if allowed is None else allowed)):
        _bridge_list_env(env, value)
    return None


def _is_connected(config) -> bool:
    """Connected when client_id + client_secret are present (PlatformConfig.extra first, then env)."""
    return all(_credentials(getattr(config, "extra", {})))


def _build_adapter(config):
    return DingTalkAdapter(config)


def register(ctx) -> None:
    """Plugin entry point — called by the Hermes plugin system."""
    ctx.register_platform(
        name="dingtalk", label="DingTalk", adapter_factory=_build_adapter, check_fn=dingtalk_deps_present,
        ensure_deps_fn=ensure_dingtalk_deps, is_connected=_is_connected, validate_config=_is_connected,
        required_env=["DINGTALK_CLIENT_ID", "DINGTALK_CLIENT_SECRET"], install_hint="pip install 'dingtalk-stream>=0.20' httpx",
        setup_fn=interactive_setup, apply_yaml_config_fn=_apply_yaml_config, allowed_users_env="DINGTALK_ALLOWED_USERS",
        allow_all_env="DINGTALK_ALLOW_ALL_USERS", cron_deliver_env_var="DINGTALK_HOME_CHANNEL",
        standalone_sender_fn=_standalone_send, emoji="🐳", allow_update_command=True,
    )


# ---- BEGIN PLUGIN-COMPAT (revert-scheduled; see COMPAT_MANIFEST.md) ----
# Names external plugins imported from this module before the Sep 2026 decomposition.
# Internal code MUST NOT use these (scripts/check_compat_pointers.py fails CI if it does).
# The whole block is removed by reverting the commit that added it.

EXT_MAP = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "md": "text/markdown",
    "txt": "text/plain",
    "csv": "text/csv",
    "zip": "application/zip",
    "mp4": "video/mp4",
}


_PLUGIN_COMPAT_LAZY = {
    'DINGTALK_TYPE_MAPPING': ('plugins.platforms.dingtalk.inbound', 'DINGTALK_TYPE_MAPPING'),
    'MessageType': ('gateway.platforms.base', 'MessageType'),
}


def __getattr__(name):  # PEP 562 — lazy so no import cycles
    target = _PLUGIN_COMPAT_LAZY.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib
    from hermes_cli.plugin_compat import warn_once
    warn_once(__name__, name, *target)
    return getattr(importlib.import_module(target[0]), target[1])
# ---- END PLUGIN-COMPAT ----

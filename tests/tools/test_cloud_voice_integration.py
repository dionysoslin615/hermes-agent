import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from gateway.config import PlatformConfig
from plugins.platforms.dingtalk.adapter import DingTalkAdapter


def test_dingtalk_voice_dm_uses_official_sample_audio(tmp_path):
    adapter = DingTalkAdapter(
        PlatformConfig(
            enabled=True,
            token="unused",
            extra={"client_id": "robot-code", "client_secret": "secret"},
        )
    )
    ogg = tmp_path / "voice.ogg"
    ogg.write_bytes(b"OggS")
    upload = Mock()
    upload.raise_for_status.return_value = None
    upload.json.return_value = {"errcode": 0, "media_id": "@media"}
    sent = Mock()
    sent.raise_for_status.return_value = None
    sent.json.return_value = {"processQueryKey": "message-key"}
    sent.content = b"{}"
    adapter._message_contexts["cid-dm"] = SimpleNamespace(
        conversation_type="1", sender_staff_id="staff-id"
    )

    with (
        patch.object(
            adapter,
            "_prepare_dingtalk_voice",
            return_value=(str(ogg), 1234, None),
        ),
        patch("requests.post", side_effect=[upload, sent]) as post,
    ):
        result = adapter._send_dingtalk_voice_sync(
            "cid-dm", str(ogg), None, "access-token"
        )

    assert result.success is True
    assert post.call_args_list[0].kwargs["params"]["type"] == "voice"
    endpoint = post.call_args_list[1].args[0]
    body = post.call_args_list[1].kwargs["json"]
    assert endpoint.endswith("/v1.0/robot/oToMessages/batchSend")
    assert body["msgKey"] == "sampleAudio"
    assert body["userIds"] == ["staff-id"]
    assert json.loads(body["msgParam"]) == {
        "mediaId": "@media",
        "duration": "1234",
    }


def test_dingtalk_voice_group_uses_official_sample_audio(tmp_path):
    audio = tmp_path / "voice.ogg"
    audio.write_bytes(b"OggS")
    adapter = DingTalkAdapter(
        PlatformConfig(enabled=True, token="", extra={"client_id": "robot-code"})
    )
    adapter._prepare_dingtalk_voice = Mock(return_value=(audio, 1234, None))
    upload = Mock()
    upload.raise_for_status.return_value = None
    upload.json.return_value = {"media_id": "@media"}
    sent = Mock()
    sent.ok = True
    sent.content = b"{}"
    sent.json.return_value = {"messageId": "message-id"}
    adapter._message_contexts["cid-group"] = SimpleNamespace(
        conversation_type="2", conversation_id="cid-group"
    )
    with patch("requests.post", side_effect=[upload, sent]) as post:
        result = adapter._send_dingtalk_voice_sync(
            "cid-group", str(audio), None, "access-token"
        )
    assert result.success
    assert post.call_args_list[1].args[0].endswith(
        "/v1.0/robot/groupMessages/send"
    )
    body = post.call_args_list[1].kwargs["json"]
    assert body["openConversationId"] == "cid-group"
    assert body["msgKey"] == "sampleAudio"
    assert json.loads(body["msgParam"]) == {
        "mediaId": "@media",
        "duration": "1234",
    }


def test_dingtalk_voice_refuses_to_guess_dm_recipient(tmp_path):
    audio = tmp_path / "voice.ogg"
    audio.write_bytes(b"OggS")
    adapter = DingTalkAdapter(
        PlatformConfig(enabled=True, token="", extra={"client_id": "robot-code"})
    )
    adapter._prepare_dingtalk_voice = Mock(return_value=(audio, 1234, None))
    upload = Mock()
    upload.raise_for_status.return_value = None
    upload.json.return_value = {"media_id": "@media"}
    with patch("requests.post", return_value=upload) as post:
        result = adapter._send_dingtalk_voice_sync(
            "unverified-chat-id", str(audio), None, "access-token"
        )
    assert not result.success
    assert result.error and "verified sender_staff_id" in result.error
    assert post.call_count == 1


@pytest.mark.asyncio
async def test_dingtalk_access_token_uses_official_oauth_fallback():
    adapter = DingTalkAdapter(
        PlatformConfig(
            enabled=True,
            token="",
            extra={"client_id": "app", "client_secret": "secret"},
        )
    )
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"accessToken": "token"}
    with patch("requests.post", return_value=response) as post:
        assert await adapter._get_access_token() == "token"
    assert post.call_args.args[0].endswith("/v1.0/oauth2/accessToken")
    assert post.call_args.kwargs["json"] == {
        "appKey": "app",
        "appSecret": "secret",
    }

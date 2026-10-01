from types import SimpleNamespace

from gateway.run_turn_runner import TurnRunner


def test_remote_native_image_reaches_url_channel(monkeypatch):
    captured = {}

    def fake_build(text, *, image_paths, image_urls):
        captured.update(text=text, image_paths=image_paths, image_urls=image_urls)
        return ([{"type": "text", "text": text}, {"type": "image_url", "image_url": {"url": image_urls[0]}}], [])

    monkeypatch.setattr("agent.image_routing.build_native_content_parts", fake_build)
    runner = SimpleNamespace(
        _consume_pending_native_image_paths=lambda _key: [
            "/tmp/local.png", "https://example.invalid/remote.png"
        ]
    )
    ctx = SimpleNamespace(session_key="session", message="look")

    result = TurnRunner(runner, ctx)._native_image_run_message()

    assert captured == {
        "text": "look",
        "image_paths": ["/tmp/local.png"],
        "image_urls": ["https://example.invalid/remote.png"],
    }
    assert result[-1]["image_url"]["url"] == "https://example.invalid/remote.png"

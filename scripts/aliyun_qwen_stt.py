#!/usr/bin/env python3
"""Hermes command-STT adapter for Alibaba Model Studio Qwen ASR.

Reads one local audio file, calls the Beijing-region multimodal generation
endpoint, and writes only the transcript to stdout or --output. The API key is
read exclusively from DASHSCOPE_API_KEY in the process environment.
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request

DEFAULT_ENDPOINT = (
    "https://dashscope.aliyuncs.com/api/v1/services/"
    "aigc/multimodal-generation/generation"
)
DEFAULT_MODEL = "qwen-audio-3.0-asr-flash"


def _extract_transcript(payload: dict) -> str:
    output = payload.get("output") or {}
    choices = output.get("choices") or []
    if choices:
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    value = item.get("text") or item.get("transcript")
                    if value:
                        parts.append(str(value))
            if parts:
                return "".join(parts).strip()
    for owner in (output, payload):
        for key in ("text", "transcript"):
            value = owner.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    raise RuntimeError("Alibaba ASR response contained no transcript")


def transcribe(audio_path: str, model: str = DEFAULT_MODEL, timeout: float = 120.0) -> str:
    key = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    if not key:
        raise RuntimeError("DASHSCOPE_API_KEY is not set")
    path = Path(audio_path).expanduser().resolve()
    if not path.is_file():
        raise RuntimeError(f"Audio file not found: {path}")
    mime = mimetypes.guess_type(path.name)[0] or "audio/mpeg"
    audio_format = path.suffix.lower().lstrip(".") or "mp3"
    if audio_format == "wave":
        audio_format = "wav"
    audio_uri = f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"
    body = {
        "model": model or DEFAULT_MODEL,
        "input": {
            "messages": [{
                "role": "user",
                "content": [{
                    "type": "input_audio",
                    "input_audio": {"data": audio_uri},
                }],
            }]
        },
        "parameters": {"format": audio_format, "language_hints": ["zh", "en"]},
    }
    endpoint = os.environ.get("DASHSCOPE_ASR_ENDPOINT", DEFAULT_ENDPOINT).strip()
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "X-DashScope-SSE": "disable",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"Alibaba ASR HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"Alibaba ASR request failed: {exc}") from exc
    return _extract_transcript(payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()
    try:
        text = transcribe(args.input, args.model, args.timeout)
        if args.output:
            Path(args.output).write_text(text, encoding="utf-8")
        else:
            print(text)
        return 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

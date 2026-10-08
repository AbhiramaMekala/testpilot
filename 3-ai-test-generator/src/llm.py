"""
Model access with a deterministic offline fallback.

Two reasons the fallback exists and is not a toy:
  1. CI build boxes often have no outbound network and no API key. A QA tool
     that only works on a laptop with a key does not get adopted.
  2. Test artefacts must be reproducible. The same requirements file has to
     produce the same cases today and in six months, or diffs are unreadable.

So the LLM path enriches wording and catches cases the rules miss; the rule
path guarantees a usable baseline. Output passes the same schema check either
way, and every record records which path produced it.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

CLAUDE_URL = "https://api.anthropic.com/v1/messages"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"


class ModelUnavailable(RuntimeError):
    pass


def available() -> str | None:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    return None


def _post(url: str, payload: dict, headers: dict, timeout: float) -> dict:
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"content-type": "application/json", **headers})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ModelUnavailable(str(exc)) from exc


def complete(prompt: str, *, system: str = "", max_tokens: int = 2000,
             timeout: float = 60.0) -> str:
    """Return raw model text. Raises ModelUnavailable if no key or no network."""
    provider = available()
    if provider is None:
        raise ModelUnavailable("no ANTHROPIC_API_KEY or OPENAI_API_KEY set")

    if provider == "anthropic":
        data = _post(CLAUDE_URL, {
            "model": os.environ.get("MODEL", "claude-sonnet-4-5"),
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        }, {"x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01"}, timeout)
        return "".join(b.get("text", "") for b in data.get("content", []))

    data = _post(OPENAI_URL, {
        "model": os.environ.get("MODEL", "gpt-4o-mini"),
        "max_tokens": max_tokens,
        "messages": ([{"role": "system", "content": system}] if system else [])
                    + [{"role": "user", "content": prompt}],
    }, {"authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"}, timeout)
    return data["choices"][0]["message"]["content"]


def complete_json(prompt: str, *, system: str = "", **kw) -> list | dict:
    """Model output parsed as JSON. Tolerates a fenced code block."""
    text = complete(prompt, system=system, **kw).strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        text = text[4:] if text.lower().startswith("json") else text
    return json.loads(text.strip())

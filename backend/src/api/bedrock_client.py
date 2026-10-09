"""Bedrock Converse calls for bill extraction, shared by the API Lambda and eval/run_bench.py.

Per-model quirks found in the benchmark (eval/results/SUMMARY-full-noclaude.md):
  - mode "tool": forced tool use (toolChoice = tool). Mistral Large 3, Qwen, Nova, Claude.
  - mode "tool_auto": the model rejects toolChoice.tool; offer the tool with auto, fall back to text JSON (Llama 4).
  - mode "json": JSON-in-text with a strict instruction; for models that ignore toolChoice (Kimi K2.5, Gemma).
  - Reasoning models (Kimi) need a large maxTokens; some reject `temperature` (Kimi K3) or a system prompt (Palmyra).
  - Replies may wrap the fields ({"record_bill": {...}}) or echo the schema per field; `unwrap` fixes both.

Only boto3/botocore here (no Pillow), so this imports fine anywhere.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from dataclasses import dataclass
from typing import Any

from . import extract_prompt as P

# Aliases so EXTRACT_MODELS can use the names from the benchmark's "mode used" column.
MODE_ALIASES = {
    "tool": "tool",
    "tool_forced": "tool",
    "tool_auto": "tool_auto",
    "json": "json",
    "json_text": "json",
}

RETRYABLE = {"ThrottlingException", "ServiceUnavailableException", "ModelNotReadyException", "InternalServerException",
             "ModelErrorException", "ServiceQuotaExceededException", "TooManyRequestsException"}

# Defaults by model id (matched by substring) so EXTRACT_MODELS can stay short.
_KNOWN = {
    "kimi-k2.5": {"max_tokens": 12000},
    "kimi-k3": {"max_tokens": 12000, "temperature": False},
    "magistral": {"max_tokens": 12000},
    "palmyra-vision": {"max_tokens": 1000, "system_in_user": True},
}


@dataclass(frozen=True)
class ModelSpec:
    id: str
    region: str
    mode: str  # tool | tool_auto | json
    max_tokens: int = 4096
    temperature: bool = True  # False: the model rejects the temperature field
    system_in_user: bool = False  # True: the model rejects a system prompt
    pdf_document: bool = False  # True: the model accepts Converse document blocks for PDFs

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ModelSpec:
        mid = str(d["id"])
        mode = MODE_ALIASES.get(str(d.get("mode", "tool")).lower())
        if not mode:
            raise ValueError(f"unknown mode {d.get('mode')!r} for {mid}")
        known: dict[str, Any] = {}
        for frag, vals in _KNOWN.items():
            if frag in mid:
                known = vals
        return cls(
            id=mid,
            region=str(d.get("region") or os.environ.get("AWS_REGION") or "ap-south-1"),
            mode=mode,
            max_tokens=int(d.get("max_tokens", known.get("max_tokens", 4096))),
            temperature=bool(d.get("temperature", known.get("temperature", True))),
            system_in_user=bool(d.get("system_in_user", known.get("system_in_user", False))),
            pdf_document=bool(d.get("pdf_document", False)),
        )


DEFAULT_MODELS = [
    {"id": "moonshotai.kimi-k2.5", "region": "ap-south-1", "mode": "json_text"},
    {"id": "mistral.mistral-large-3-675b-instruct", "region": "ap-south-1", "mode": "tool"},
]


def models_from_env(raw: str | None = None) -> list[ModelSpec]:
    """EXTRACT_MODELS: JSON list of {id, region, mode[, max_tokens, temperature, system_in_user, pdf_document]}."""
    raw = os.environ.get("EXTRACT_MODELS", "") if raw is None else raw
    items = json.loads(raw) if raw and raw.strip() else DEFAULT_MODELS
    if not isinstance(items, list) or not items:
        raise ValueError("EXTRACT_MODELS must be a non-empty JSON list")
    return [ModelSpec.from_dict(d) for d in items]


# ------------------------------------------------------------------ clients

_clients: dict[tuple, Any] = {}
_clients_lock = threading.Lock()


def client(region: str, read_timeout: int = 300, max_attempts: int = 1):
    import boto3
    from botocore.config import Config

    key = (region, read_timeout, max_attempts)
    with _clients_lock:
        if key not in _clients:
            cfg = Config(read_timeout=read_timeout, connect_timeout=10,
                         retries={"max_attempts": max_attempts, "mode": "standard"})
            _clients[key] = boto3.client("bedrock-runtime", region_name=region, config=cfg)
        return _clients[key]


# ------------------------------------------------------------------ request / response

def build_request(model_id: str, mode: str, blocks: list[dict], *, max_tokens: int = 4096, temperature: bool = True,
                  system_in_user: bool = False) -> dict:
    """Converse request for one bill. `blocks` are the image/document content blocks."""
    instruction = P.USER_INSTRUCTION_JSON if mode == "json" else P.USER_INSTRUCTION_TOOL
    if system_in_user:
        instruction = P.SYSTEM_PROMPT + "\n\n" + instruction
    req: dict[str, Any] = {
        "modelId": model_id,
        "messages": [{"role": "user", "content": list(blocks) + [{"text": instruction}]}],
        "inferenceConfig": {"maxTokens": max_tokens},
    }
    if not system_in_user:
        req["system"] = [{"text": P.SYSTEM_PROMPT}]
    if temperature:
        req["inferenceConfig"]["temperature"] = 0
    if mode == "tool":
        req["toolConfig"] = {"tools": [P.tool_spec()], "toolChoice": {"tool": {"name": P.TOOL_NAME}}}
    elif mode == "tool_auto":
        req["toolConfig"] = {"tools": [P.tool_spec()], "toolChoice": {"auto": {}}}
    return req


def parse_response(resp: dict, mode: str) -> tuple[dict | None, str, str, list]:
    """Return (prediction or None, mode actually used, text, raw tool inputs)."""
    content = resp.get("output", {}).get("message", {}).get("content", [])
    tool_inputs = [c["toolUse"]["input"] for c in content if "toolUse" in c]
    text = "\n".join(c["text"] for c in content if "text" in c)
    pred, used = None, mode
    if tool_inputs:
        ti = tool_inputs[0]
        if isinstance(ti, str):
            ti = extract_json(ti)
        pred = ti if isinstance(ti, dict) else None
        used = "tool_forced" if mode == "tool" else "tool_auto"
    if pred is None:
        pred = extract_json(text)
        used = "json_text" if mode == "json" else f"{mode}->text_fallback"
    if pred is not None:
        pred = unwrap(pred)
    return pred, used, text, tool_inputs


class ModelCallError(RuntimeError):
    def __init__(self, code: str, message: str = ""):
        super().__init__(f"{code}: {message}"[:300])
        self.code = code


def converse_extract(spec: ModelSpec, blocks: list[dict], *, read_timeout: int = 45, max_retries: int = 2,
                     deadline: float | None = None) -> dict:
    """One extraction call with small retries. Returns {prediction, mode_used, latency_ms, usage, stop_reason}.

    Raises ModelCallError on failure or unparseable output. `deadline` is a time.monotonic() value
    after which no retry is started.
    """
    from botocore.exceptions import (
        ClientError,
        ConnectionClosedError,
        EndpointConnectionError,
        ReadTimeoutError,
    )

    req = build_request(spec.id, spec.mode, blocks, max_tokens=spec.max_tokens, temperature=spec.temperature,
                        system_in_user=spec.system_in_user)
    last: ModelCallError | None = None
    for attempt in range(1, max_retries + 1):
        t0 = time.monotonic()
        try:
            resp = client(spec.region, read_timeout).converse(**req)
        except ClientError as e:
            err = e.response.get("Error", {})
            last = ModelCallError(err.get("Code", "ClientError"), err.get("Message", ""))
            if last.code not in RETRYABLE:
                raise last from None
        except (ReadTimeoutError, ConnectionClosedError, EndpointConnectionError) as e:
            last = ModelCallError(type(e).__name__, str(e))
        else:
            latency_ms = int((time.monotonic() - t0) * 1000)
            pred, used, _text, _ti = parse_response(resp, spec.mode)
            if pred is None:
                raise ModelCallError("UNPARSEABLE_OUTPUT", f"stop_reason={resp.get('stopReason')}")
            return {"prediction": pred, "mode_used": used, "latency_ms": latency_ms, "usage": resp.get("usage", {}),
                    "stop_reason": resp.get("stopReason"), "attempts": attempt}
        backoff = min(4.0, 0.5 * 2 ** attempt)
        if attempt >= max_retries or (deadline is not None and time.monotonic() + backoff + 5 > deadline):
            break
        time.sleep(backoff)
    raise last or ModelCallError("UNKNOWN")


# ------------------------------------------------------------------ JSON extraction

def _strip_reasoning(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<reasoning>.*?</reasoning>", "", text, flags=re.DOTALL | re.IGNORECASE)
    return text


def _loads_lenient(s: str):
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    t = re.sub(r",\s*([}\]])", r"\1", s)  # trailing commas
    t = re.sub(r"//[^\n\"]*\n", "\n", t)  # line comments
    t = re.sub(r"\bNone\b", "null", t)
    t = re.sub(r"\bTrue\b", "true", t)
    t = re.sub(r"\bFalse\b", "false", t)
    return json.loads(t)


def extract_json(text: str) -> dict | None:
    """Find the best JSON object in free text (fences, prose, think tags)."""
    text = _strip_reasoning(text or "")
    candidates = re.findall(r"```(?:json|JSON)?\s*(.*?)```", text, flags=re.DOTALL)
    # every balanced {...} span, longest first
    spans, depth, start, in_str, esc = [], 0, None, False, False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
            if depth == 0:
                spans.append(text[start:i + 1])
    candidates += sorted(spans, key=len, reverse=True)
    if text.strip().startswith("{"):
        candidates.append(text.strip())
    for c in candidates:
        try:
            obj = _loads_lenient(c.strip())
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(obj, dict):
            return obj
    return None


def unwrap(obj: dict) -> dict:
    """Models sometimes nest the fields: {"record_bill": {...}}, {"fields": {...}}, {"properties": {...}},
    or echo the schema per field: {"state": {"type": ["string", "null"], "value": "Delhi"}}."""
    for _ in range(3):
        if any(k in obj for k in P.FIELD_ORDER):
            break
        dicts = [v for v in obj.values() if isinstance(v, dict)]
        if len(dicts) == 1:
            obj = dicts[0]
        else:
            break
    out = {}
    for k, v in obj.items():
        if isinstance(v, dict) and k != "consumption_history" and ("value" in v or "type" in v or "description" in v):
            v = v.get("value")
        if k == "consumption_history" and isinstance(v, dict):
            v = v.get("value", v.get("items"))
        out[k] = v
    return out

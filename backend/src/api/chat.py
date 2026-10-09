"""POST /chat: the plan assistant (Strands Agents + a Bedrock model, tools in chat_tools.py).

    {sessionId?, planId?, message, lang?} -> {reply, sessionId}

History lives in ChatsTable (one item per turn: sessionId + ts, TTL expiresAt); the last
HISTORY_TURNS turns are sent back to the model as plain text. Messages and turns per session are
capped to protect credits. Logs hold only sizes, timings, token counts and tool names, never text.
Strands is imported lazily so the other routes don't pay for it on a cold start.
"""

from __future__ import annotations

import logging
import os
import re
import secrets
import time
import traceback
from functools import cache
from typing import Any

from aws_lambda_powertools import Logger
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from . import aws
from .chat_prompt import system_prompt
from .chat_tools import get_plan_data, load_stored_plan, make_tools
from .errors import ApiError
from .plan import PLAN_ID_RE

logger = Logger(child=True)

CHAT_MODEL_ID = os.environ.get("CHAT_MODEL_ID", "moonshotai.kimi-k2.5")
CHAT_MODEL_REGION = os.environ.get("CHAT_MODEL_REGION", "ap-south-1")
MAX_MESSAGE_CHARS = int(os.environ.get("CHAT_MAX_MESSAGE_CHARS", "1000"))
MAX_TURNS = int(os.environ.get("CHAT_MAX_TURNS", "30"))
HISTORY_TURNS = 10
CHAT_TTL_DAYS = int(os.environ.get("CHAT_TTL_DAYS", "7"))

SESSION_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
LANG_RE = re.compile(r"^[a-z]{2,3}(-[A-Za-z]{2})?$")
# 9+ digits (spaces/hyphens allowed between them): Aadhaar, bank account and card numbers.
# Dropped before the model sees the message and before it is stored.
LONG_NUMBER_RE = re.compile(r"\d(?:[ -]?\d){8,}")

# A reply with a digit but no tool call this turn probably took numbers from history or made them up.
HAS_NUMBER_RE = re.compile(r"\d")
RETRY_NOTE = ("(Check: your last answer used numbers but you called no tool in this turn. Call the right tool "
              "now and answer my previous question again, using only numbers from the tool, in the same "
              "language and script as my previous question.)")

FALLBACK_REPLY = "Sorry, I couldn't answer that. Please try asking in a different way."

# Strands logs at WARNING and above can include model text; keep only errors.
logging.getLogger("strands").setLevel(logging.ERROR)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    sessionId: str | None = None
    planId: str | None = None
    message: str = Field(default="")
    lang: str | None = None


def scrub(text: str) -> str:
    return LONG_NUMBER_RE.sub("[number removed]", text)


def _validate(body: dict) -> ChatRequest:
    try:
        req = ChatRequest.model_validate(body)
    except ValidationError as e:
        errs = [{"loc": ".".join(str(x) for x in err["loc"]), "msg": err["msg"]}
                for err in e.errors(include_input=False)]
        raise ApiError("BAD_REQUEST", "Some fields are invalid.", 400, {"details": errs}) from None
    req.message = req.message.strip()
    if not req.message:
        raise ApiError("EMPTY_MESSAGE", "Type a question first.", 400)
    if len(req.message) > MAX_MESSAGE_CHARS:
        raise ApiError("MESSAGE_TOO_LONG", f"Please keep your message under {MAX_MESSAGE_CHARS} characters.", 400,
                       {"maxChars": MAX_MESSAGE_CHARS})
    if req.sessionId is not None and not SESSION_RE.match(req.sessionId):
        raise ApiError("BAD_SESSION", "This chat session id isn't valid.", 400)
    if req.planId is not None and not PLAN_ID_RE.match(req.planId):
        raise ApiError("BAD_PLAN_ID", "This plan id isn't valid.", 400)
    if req.lang is not None and not LANG_RE.match(req.lang):
        req.lang = None
    return req


# ---------------------------------------------------------------- history


def load_turns(session_id: str) -> list[dict]:
    """All turns of a session, newest first (at most MAX_TURNS + a few, so one page is enough)."""
    resp = aws.dynamodb().query(
        TableName=aws.CHATS_TABLE,
        KeyConditionExpression="sessionId = :s",
        ExpressionAttributeValues={":s": {"S": session_id}},
        ScanIndexForward=False,
        Limit=MAX_TURNS + 5,
    )
    now = time.time()
    out = []
    for it in resp.get("Items", []):
        if int(it.get("expiresAt", {}).get("N", "0")) < now:
            continue
        out.append({"ts": int(it["ts"]["N"]), "user": it.get("user", {}).get("S", ""),
                    "assistant": it.get("assistant", {}).get("S", ""), "planId": it.get("planId", {}).get("S")})
    return out


def save_turn(session_id: str, user: str, assistant: str, plan_id: str | None, lang: str | None) -> None:
    now_ms = time.time_ns() // 1_000_000
    item: dict[str, Any] = {
        "sessionId": {"S": session_id},
        "ts": {"N": str(now_ms)},
        "user": {"S": user},
        "assistant": {"S": assistant},
        "expiresAt": {"N": str(now_ms // 1000 + CHAT_TTL_DAYS * 86400)},
    }
    if plan_id:
        item["planId"] = {"S": plan_id}
    if lang:
        item["lang"] = {"S": lang}
    aws.dynamodb().put_item(TableName=aws.CHATS_TABLE, Item=item)


def history_messages(turns_newest_first: list[dict]) -> list[dict]:
    """Last HISTORY_TURNS turns as Bedrock/Strands messages, oldest first, alternating user/assistant."""
    msgs: list[dict] = []
    for t in reversed(turns_newest_first[:HISTORY_TURNS]):
        if t["user"] and t["assistant"]:
            msgs.append({"role": "user", "content": [{"text": t["user"]}]})
            msgs.append({"role": "assistant", "content": [{"text": t["assistant"]}]})
    return msgs


# ---------------------------------------------------------------- model


def _model_config(model_id: str) -> dict:
    # Kimi is a reasoning model: thinking tokens count against max_tokens.
    if "kimi" in model_id:
        return {"max_tokens": 8000, "temperature": 0.3}
    return {"max_tokens": 1200, "temperature": 0.3}


@cache
def _model():
    from botocore.config import Config
    from strands.models.bedrock import BedrockModel

    # streaming=False: plain Converse (bedrock:InvokeModel), the reply is returned in one piece anyway.
    return BedrockModel(model_id=CHAT_MODEL_ID, region_name=CHAT_MODEL_REGION, streaming=False,
                        boto_client_config=Config(read_timeout=40, connect_timeout=5,
                                                  retries={"max_attempts": 2, "mode": "standard"}),
                        **_model_config(CHAT_MODEL_ID))


def run_agent(history: list[dict], message: str, plan_id: str | None, lang: str | None) -> tuple[str, dict]:
    """Returns (reply text, metrics without any text)."""
    from strands import Agent

    # The plan goes into the system prompt, so most follow-ups need no tool round trip (and no retry).
    try:
        facts = get_plan_data(plan_id, load_stored_plan) if plan_id else None
    except Exception:  # noqa: BLE001 - the get_plan tool is still there as a fallback
        facts = None
    has_facts = bool(facts) and "error" not in facts
    agent = Agent(model=_model(), system_prompt=system_prompt(plan_id, lang, message, facts if has_facts else None),
                  tools=make_tools(plan_id, load_stored_plan), messages=history, callback_handler=None)
    result = agent(message)
    reply = str(result).strip()
    retried = False
    if not has_facts and not _tool_calls(result) and HAS_NUMBER_RE.search(reply):
        # Kimi ignores toolChoice, so tool use can't be forced; ask once more instead.
        result = agent(RETRY_NOTE)
        reply, retried = str(result).strip() or reply, True
    m = result.metrics  # one Agent per request, so these cover this turn (both calls when retried)
    usage = m.accumulated_usage or {}
    metrics = {"cycles": m.cycle_count, "tools": {k: v.call_count for k, v in m.tool_metrics.items()},
               "retried": retried, "input_tokens": usage.get("inputTokens"),
               "output_tokens": usage.get("outputTokens"), "stop_reason": str(result.stop_reason)}
    return reply, metrics


def _tool_calls(result) -> int:
    return sum(v.call_count for v in result.metrics.tool_metrics.values())


# ---------------------------------------------------------------- entry


def chat(body: dict, runner=None) -> dict:
    t0 = time.monotonic()
    runner = runner or run_agent
    req = _validate(body)
    session_id = req.sessionId or secrets.token_urlsafe(16)
    turns = load_turns(session_id) if req.sessionId else []
    if len(turns) >= MAX_TURNS:
        raise ApiError("SESSION_LIMIT", "This chat has reached its limit. Start a new chat to keep going.", 429,
                       {"maxTurns": MAX_TURNS})
    plan_id = req.planId or next((t["planId"] for t in turns if t.get("planId")), None)
    message = scrub(req.message)
    t_hist = time.monotonic()

    try:
        reply, metrics = runner(history_messages(turns), message, plan_id, req.lang)
    except ApiError:
        raise
    except Exception as e:  # noqa: BLE001 - any model/SDK failure becomes a 503
        # Type and frames only: exception messages can echo model text.
        logger.error("chat model error", extra={"type": type(e).__name__, "model": CHAT_MODEL_ID,
                                                "trace": "".join(traceback.format_tb(e.__traceback__))[-2000:]})
        raise ApiError("CHAT_UNAVAILABLE", "The assistant is busy right now. Please try again in a minute.",
                       503) from None
    reply = scrub(reply).strip() or FALLBACK_REPLY
    t_model = time.monotonic()

    save_turn(session_id, message, reply, plan_id, req.lang)
    latency = {"total": int((time.monotonic() - t0) * 1000), "history": int((t_hist - t0) * 1000),
               "model": int((t_model - t_hist) * 1000)}
    logger.info("chat turn", extra={"model": CHAT_MODEL_ID, "turn": len(turns) + 1, "has_plan": bool(plan_id),
                                    "lang": req.lang, "message_chars": len(message), "reply_chars": len(reply),
                                    "latency_ms": latency, **metrics})
    return {"reply": reply, "sessionId": session_id}

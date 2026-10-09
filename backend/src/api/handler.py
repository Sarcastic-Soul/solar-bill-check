"""ApiFunction entry point: Powertools LambdaFunctionUrlResolver routes.

    POST /upload-url   {contentType | filename, size?}    -> presigned S3 POST
    POST /extract      {key}                               -> fields + confidence (bill deleted after read)
    POST /plan         {fields, pincode, answers, overrides} -> plan + planId (saved, masked)
    GET  /plan/{id}                                         -> stored plan (shareable link)
    POST /speak        {text, lang: hi|en}                 -> base64 MP3 (Polly Kajal neural)
    POST /chat         {sessionId?, planId?, message, lang?} -> {reply, sessionId} (Strands agent)
    GET  /health

CORS is configured on the Function URL (template.yaml), so no CORS headers are added here.
Errors are JSON: {"error": CODE, "message": "..."}.
"""

from __future__ import annotations

import json
import traceback

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import (
    LambdaFunctionUrlResolver,
    Response,
    content_types,
)
from aws_lambda_powertools.event_handler.exceptions import NotFoundError

from . import chat as chat_mod
from . import extract as extract_mod
from . import plan as plan_mod
from . import speak as speak_mod
from . import upload as upload_mod
from .errors import ApiError

logger = Logger()
app = LambdaFunctionUrlResolver()


def _json(status: int, body: dict) -> Response:
    return Response(status_code=status, content_type=content_types.APPLICATION_JSON,
                    body=json.dumps(body, ensure_ascii=False, separators=(",", ":")),
                    headers={"Cache-Control": "no-store"})


def _body() -> dict:
    try:
        body = app.current_event.json_body
    except (json.JSONDecodeError, TypeError, ValueError):
        raise ApiError("BAD_JSON", "The request body must be JSON.", 400) from None
    if body is None:
        return {}
    if not isinstance(body, dict):
        raise ApiError("BAD_JSON", "The request body must be a JSON object.", 400)
    return body


@app.exception_handler(ApiError)
def _api_error(e: ApiError) -> Response:
    logger.info("api error", extra={"code": e.code, "status": e.status})
    return _json(e.status, e.body())


@app.exception_handler(NotFoundError)
def _not_found(_e: NotFoundError) -> Response:
    return _json(404, {"error": "NOT_FOUND", "message": "No such route."})


@app.exception_handler(Exception)
def _unhandled(e: Exception) -> Response:
    # Type and stack frames only: exception messages can carry user values.
    logger.error("unhandled error", extra={"type": type(e).__name__,
                                           "trace": "".join(traceback.format_tb(e.__traceback__))[-3000:]})
    return _json(500, {"error": "INTERNAL", "message": "Something went wrong. Please try again."})


@app.get("/health")
def health():
    return _json(200, {"ok": True})


@app.post("/upload-url")
def upload_url():
    return _json(200, upload_mod.create_upload(_body()))


@app.post("/extract")
def extract():
    body = _body()
    ctx = app.lambda_context
    remaining = ctx.get_remaining_time_in_millis if ctx is not None else None
    return _json(200, extract_mod.extract(str(body.get("key") or ""), remaining))


@app.post("/plan")
def plan():
    return _json(200, plan_mod.make_plan(_body()))


@app.get("/plan/<plan_id>")
def get_plan(plan_id: str):
    return _json(200, plan_mod.get_plan(plan_id))


@app.post("/speak")
def speak():
    return _json(200, speak_mod.speak(_body()))


@app.post("/chat")
def chat():
    return _json(200, chat_mod.chat(_body()))


@logger.inject_lambda_context(log_event=False, clear_state=True)
def lambda_handler(event, context):
    return app.resolve(event, context)

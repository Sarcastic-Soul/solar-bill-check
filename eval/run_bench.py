# /// script
# requires-python = ">=3.12"
# dependencies = ["boto3[crt]", "pymupdf", "pillow"]
# ///
"""Benchmark Bedrock vision models on Indian electricity bill extraction.

Run (from repo root):
    uv run eval/run_bench.py --list-models
    uv run eval/run_bench.py --dry-run
    uv run eval/run_bench.py                          # all enabled models, all bills in eval/bills/
    uv run eval/run_bench.py --models haiku45,nova_pro --bills 'msedcl-*' --repeat 3

Each bill is eval/bills/<id>/ with bill.{png,jpg,jpeg,webp,pdf} + label.json (see eval/SCHEMA.md).
Folders starting with "_" (e.g. _smoke-*) are skipped unless --bills matches them.

`boto3[crt]` is needed because the AWS CLI login uses the "login" credential provider.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import fnmatch
import io
import json
import random
import re
import statistics
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import boto3
import pymupdf
from botocore.config import Config
from botocore.exceptions import ClientError, ReadTimeoutError, ConnectionClosedError, EndpointConnectionError
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from api import extract_prompt as P  # noqa: E402
import score as S  # noqa: E402

BILLS_DIR = ROOT / "eval" / "bills"
RESULTS_DIR = ROOT / "eval" / "results"

# ------------------------------------------------------------------ models
# mode:
#   tool       forced tool use (toolChoice = tool)
#   tool_auto  model rejects toolChoice.tool; offer the tool with toolChoice auto (falls back to text JSON)
#   json       JSON-in-text with a strict instruction
# pdf: "document" = model accepts Converse document blocks; "image" = always render pages to PNG.
# price_in/price_out: USD per 1M tokens for the region/profile we call (AWS Price List API, 2026-10-09).
# reasoning: model thinks before answering by default -> needs more output tokens.


@dataclass
class ModelCfg:
    key: str
    model_id: str
    region: str
    mode: str
    price_in: float
    price_out: float
    family: str
    pdf: str = "image"
    max_tokens: int = 4096
    reasoning: bool = False
    temperature: bool = True  # False: model rejects the temperature field
    system_in_user: bool = False  # True: model rejects the system field; prepend the prompt to the user text
    enabled: bool = True
    note: str = ""


MODELS: list[ModelCfg] = [
    # --- Anthropic (latest accessible). global.* routes worldwide; in.* stays in India.
    ModelCfg("haiku45", "in.anthropic.claude-haiku-4-5-20251001-v1:0", "ap-south-1", "tool", 1.10, 5.50, "anthropic", pdf="document",
             note="in. profile = India-only routing (+10% price). 2026-10-09 probe: 'use case details not submitted' error (also global./us.)"),
    ModelCfg("sonnet46", "global.anthropic.claude-sonnet-4-6", "ap-south-1", "tool", 3.00, 15.00, "anthropic", pdf="document"),
    ModelCfg("sonnet45", "global.anthropic.claude-sonnet-4-5-20250929-v1:0", "ap-south-1", "tool", 3.00, 15.00, "anthropic", pdf="document"),
    ModelCfg("opus46", "global.anthropic.claude-opus-4-6-v1", "ap-south-1", "tool", 5.00, 25.00, "anthropic", pdf="document"),
    ModelCfg("opus45", "global.anthropic.claude-opus-4-5-20251101-v1:0", "ap-south-1", "tool", 5.00, 25.00, "anthropic", pdf="document"),
    # --- Amazon Nova
    ModelCfg("nova_lite", "apac.amazon.nova-lite-v1:0", "ap-south-1", "tool", 0.071, 0.284, "amazon", pdf="document"),
    ModelCfg("nova_pro", "apac.amazon.nova-pro-v1:0", "ap-south-1", "tool", 0.94, 3.76, "amazon", pdf="document"),
    ModelCfg("nova2_lite", "global.amazon.nova-2-lite-v1:0", "ap-south-1", "tool", 0.35, 2.95, "amazon", pdf="document"),
    # --- Meta Llama 4 (US only)
    ModelCfg("llama4_maverick", "us.meta.llama4-maverick-17b-instruct-v1:0", "us-east-1", "tool_auto", 0.24, 0.97, "meta"),
    ModelCfg("llama4_scout", "us.meta.llama4-scout-17b-instruct-v1:0", "us-east-1", "tool_auto", 0.17, 0.66, "meta"),
    # --- Mistral
    ModelCfg("pixtral_large", "us.mistral.pixtral-large-2502-v1:0", "us-east-1", "json", 2.00, 6.00, "mistral",
             note="rejects toolChoice.tool; with auto it answers in text"),
    ModelCfg("mistral_large3", "mistral.mistral-large-3-675b-instruct", "ap-south-1", "tool", 0.59, 1.76, "mistral"),
    ModelCfg("ministral14b", "mistral.ministral-3-14b-instruct", "ap-south-1", "tool", 0.24, 0.24, "mistral"),
    ModelCfg("ministral8b", "mistral.ministral-3-8b-instruct", "ap-south-1", "tool", 0.18, 0.18, "mistral"),
    ModelCfg("ministral3b", "mistral.ministral-3-3b-instruct", "ap-south-1", "tool", 0.12, 0.12, "mistral"),
    ModelCfg("magistral_small", "mistral.magistral-small-2509", "ap-south-1", "json", 0.59, 1.76, "mistral", reasoning=True, max_tokens=12000,
             note="accepts toolChoice but ignores it"),
    # --- Qwen / Google / others
    ModelCfg("qwen3_vl", "qwen.qwen3-vl-235b-a22b", "ap-south-1", "tool", 0.62, 3.13, "qwen"),
    ModelCfg("gemma3_27b", "google.gemma-3-27b-it", "ap-south-1", "json", 0.27, 0.45, "google", note="ignores toolChoice"),
    ModelCfg("gemma3_12b", "google.gemma-3-12b-it", "ap-south-1", "json", 0.11, 0.34, "google", note="ignores toolChoice"),
    ModelCfg("gemma3_4b", "google.gemma-3-4b-it", "ap-south-1", "json", 0.05, 0.09, "google", note="ignores toolChoice"),
    ModelCfg("kimi_k25", "moonshotai.kimi-k2.5", "ap-south-1", "json", 0.72, 3.60, "moonshot", reasoning=True, max_tokens=12000,
             note="ignores toolChoice"),
    ModelCfg("kimi_k3", "in.moonshotai.kimi-k3", "ap-south-1", "tool", 3.30, 16.50, "moonshot", reasoning=True, max_tokens=12000,
             temperature=False, note="rejects temperature"),
    ModelCfg("nemotron_vl", "nvidia.nemotron-nano-12b-v2", "ap-south-1", "json", 0.24, 0.71, "nvidia", note="ignores toolChoice"),
    ModelCfg("palmyra_vision", "writer.palmyra-vision-7b", "us-east-1", "json", 0.15, 0.60, "writer", system_in_user=True, max_tokens=1000,
             note="errors when tools or a system prompt are passed; ~4K context so maxTokens 1000"),
    # --- Listed but not usable for this account (2026-10-09 probe). Kept for re-probing with --models <key>.
    ModelCfg("haiku55", "global.anthropic.claude-haiku-5-5", "ap-south-1", "tool", 0.10, 0.50, "anthropic", pdf="document", enabled=False, note="AccessDenied"),
    ModelCfg("sonnet55", "global.anthropic.claude-sonnet-5-5", "ap-south-1", "tool", 2.00, 10.00, "anthropic", pdf="document", enabled=False, note="AccessDenied"),
    ModelCfg("sonnet5", "in.anthropic.claude-sonnet-5", "ap-south-1", "tool", 2.20, 11.00, "anthropic", pdf="document", enabled=False, note="AccessDenied"),
    ModelCfg("opus55", "global.anthropic.claude-opus-5-5", "ap-south-1", "tool", 4.00, 20.00, "anthropic", pdf="document", enabled=False, note="AccessDenied"),
    ModelCfg("opus5", "in.anthropic.claude-opus-5", "ap-south-1", "tool", 5.50, 27.50, "anthropic", pdf="document", enabled=False, note="AccessDenied"),
    ModelCfg("opus48", "global.anthropic.claude-opus-4-8", "ap-south-1", "tool", 5.00, 25.00, "anthropic", pdf="document", enabled=False, note="AccessDenied"),
    ModelCfg("opus47", "global.anthropic.claude-opus-4-7", "ap-south-1", "tool", 5.00, 25.00, "anthropic", pdf="document", enabled=False, note="AccessDenied"),
    ModelCfg("fable51", "global.anthropic.claude-fable-5-1", "ap-south-1", "tool", 0.0, 0.0, "anthropic", pdf="document", enabled=False, note="AccessDenied; price unknown"),
    ModelCfg("gpt61_sol", "global.openai.gpt-6.1-sol", "ap-south-1", "tool", 0.0, 0.0, "openai", enabled=False, note="AccessDenied; price unknown"),
    ModelCfg("grok47", "global.xai.grok-4.7", "ap-south-1", "tool", 0.0, 0.0, "xai", enabled=False, note="AccessDenied; price unknown"),
    ModelCfg("nova_premier", "us.amazon.nova-premier-v1:0", "us-east-1", "tool", 2.50, 12.50, "amazon", pdf="document", enabled=False, note="end of life"),
    ModelCfg("llama32_90b", "us.meta.llama3-2-90b-instruct-v1:0", "us-east-1", "json", 0.72, 0.72, "meta", enabled=False, note="end of life"),
]
MODEL_BY_KEY = {m.key: m for m in MODELS}

NON_LATIN = {"hi", "mr", "ta", "te", "kn", "ml", "bn", "gu", "pa", "or", "as", "ur", "ne", "kok", "sa"}
RETRYABLE = {"ThrottlingException", "ServiceUnavailableException", "ModelNotReadyException", "InternalServerException",
             "ModelErrorException", "ServiceQuotaExceededException", "TooManyRequestsException"}

_clients: dict[str, object] = {}
_clients_lock = threading.Lock()


def client(region: str):
    with _clients_lock:
        if region not in _clients:
            cfg = Config(read_timeout=300, connect_timeout=20, retries={"max_attempts": 1, "mode": "standard"})
            _clients[region] = boto3.client("bedrock-runtime", region_name=region, config=cfg)
        return _clients[region]


# ------------------------------------------------------------------ bills / inputs
@dataclass
class Bill:
    id: str
    path: Path
    label: dict
    kind: str  # image | pdf

    @property
    def difficulty(self) -> str:
        return self.label.get("difficulty") or "clean"

    @property
    def non_latin(self) -> bool:
        return bool(set(self.label.get("languages") or []) & NON_LATIN)


def find_bills(pattern: str | None) -> list[Bill]:
    out = []
    if not BILLS_DIR.exists():
        return out
    for d in sorted(p for p in BILLS_DIR.iterdir() if p.is_dir()):
        if pattern:
            if not any(fnmatch.fnmatch(d.name, pat.strip()) for pat in pattern.split(",")):
                continue
        elif d.name.startswith("_"):
            continue
        label_p = d / "label.json"
        files = [f for f in d.iterdir() if f.stem == "bill" and f.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".pdf"}]
        if not label_p.exists() or not files:
            print(f"  skip {d.name}: missing label.json or bill.*", file=sys.stderr)
            continue
        try:
            label = json.loads(label_p.read_text())
        except json.JSONDecodeError as e:
            print(f"  skip {d.name}: bad label.json ({e})", file=sys.stderr)
            continue
        f = files[0]
        for w in lint_label(label):
            print(f"  label warning {d.name}: {w}", file=sys.stderr)
        out.append(Bill(d.name, f, label, "pdf" if f.suffix.lower() == ".pdf" else "image"))
    return out


def lint_label(label: dict) -> list[str]:
    """Cheap sanity checks so label mistakes don't silently look like model mistakes."""
    f = label.get("fields") or {}
    warns = [f"missing field '{k}'" for k in P.FIELD_ORDER if k not in f]
    iseb = f.get("is_electricity_bill")
    if not isinstance(iseb, bool):
        warns.append(f"is_electricity_bill should be true/false, got {iseb!r}")
    elif iseb is False and any(f.get(k) is not None for k in P.FIELD_ORDER if k != "is_electricity_bill"):
        warns.append("non-bill label has non-null fields")
    for k in ("billing_period_start", "billing_period_end"):
        if f.get(k) is not None and not re.match(r"^\d{4}-\d{2}-\d{2}$", str(f[k])):
            warns.append(f"{k} not YYYY-MM-DD: {f[k]!r}")
    for h in f.get("consumption_history") or []:
        if not re.match(r"^\d{4}-\d{2}$", str(h.get("month"))):
            warns.append(f"history month not YYYY-MM: {h.get('month')!r}")
            break
    if label.get("difficulty") not in (None, "clean", "phone_photo", "blurry", "rotated", "low_light", "cropped"):
        warns.append(f"unknown difficulty {label.get('difficulty')!r}")
    return warns


def prep_image(data: bytes, max_edge: int) -> bytes:
    im = Image.open(io.BytesIO(data))
    im = ImageOps.exif_transpose(im)
    if im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    if max(im.size) > max_edge:
        im.thumbnail((max_edge, max_edge), Image.LANCZOS)
    q = 90
    while True:
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=q)
        if buf.tell() < 3_500_000 or q <= 50:
            return buf.getvalue()
        q -= 10


def pdf_pages_png(path: Path, max_pages: int, max_edge: int) -> list[bytes]:
    doc = pymupdf.open(path)
    out = []
    for page in list(doc)[:max_pages]:
        zoom = min(200 / 72, max_edge / max(page.rect.width, page.rect.height))
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
        out.append(prep_image(pix.tobytes("png"), max_edge))
    return out


def pdf_has_text(path: Path, max_pages: int) -> bool:
    doc = pymupdf.open(path)
    return sum(len(p.get_text().strip()) for p in list(doc)[:max_pages]) > 200


_input_cache: dict[tuple, list[dict]] = {}
_input_lock = threading.Lock()


def content_blocks(bill: Bill, m: ModelCfg, args) -> tuple[list[dict], str]:
    """Return (Converse content blocks for the bill, input kind)."""
    use_doc = (bill.kind == "pdf" and m.pdf == "document" and args.pdf_mode == "auto"
               and pdf_has_text(bill.path, args.pdf_pages))
    key = (bill.id, "doc" if use_doc else "img")
    with _input_lock:
        if key not in _input_cache:
            if use_doc:
                # Trim to the first N pages so all models see the same pages.
                src = pymupdf.open(bill.path)
                dst = pymupdf.open()
                dst.insert_pdf(src, from_page=0, to_page=min(args.pdf_pages, len(src)) - 1)
                _input_cache[key] = [{"document": {"format": "pdf", "name": "electricity bill", "source": {"bytes": dst.tobytes()}}}]
            elif bill.kind == "pdf":
                _input_cache[key] = [{"image": {"format": "jpeg", "source": {"bytes": b}}}
                                     for b in pdf_pages_png(bill.path, args.pdf_pages, args.max_edge)]
            else:
                _input_cache[key] = [{"image": {"format": "jpeg", "source": {"bytes": prep_image(bill.path.read_bytes(), args.max_edge)}}}]
    return _input_cache[key], ("pdf_document" if use_doc else ("pdf_rendered" if bill.kind == "pdf" else "image"))


# ------------------------------------------------------------------ JSON extraction
def _strip_reasoning(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S | re.I)
    text = re.sub(r"<reasoning>.*?</reasoning>", "", text, flags=re.S | re.I)
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
    candidates = re.findall(r"```(?:json|JSON)?\s*(.*?)```", text, flags=re.S)
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


# ------------------------------------------------------------------ one call
def call_model(m: ModelCfg, bill: Bill, args) -> dict:
    blocks, input_kind = content_blocks(bill, m, args)
    mode = m.mode
    instruction = P.USER_INSTRUCTION_JSON if mode == "json" else P.USER_INSTRUCTION_TOOL
    if m.system_in_user:
        instruction = P.SYSTEM_PROMPT + "\n\n" + instruction
    req = {
        "modelId": m.model_id,
        "messages": [{"role": "user", "content": blocks + [{"text": instruction}]}],
        "inferenceConfig": {"maxTokens": m.max_tokens},
    }
    if not m.system_in_user:
        req["system"] = [{"text": P.SYSTEM_PROMPT}]
    if m.temperature:
        req["inferenceConfig"]["temperature"] = 0
    if mode == "tool":
        req["toolConfig"] = {"tools": [P.tool_spec()], "toolChoice": {"tool": {"name": P.TOOL_NAME}}}
    elif mode == "tool_auto":
        req["toolConfig"] = {"tools": [P.tool_spec()], "toolChoice": {"auto": {}}}

    rec = {"model": m.key, "model_id": m.model_id, "region": m.region, "bill": bill.id, "mode": mode,
           "input_kind": input_kind, "n_images": sum("image" in b for b in blocks)}
    attempts, last_err = 0, None
    t0 = time.time()
    while attempts < args.max_retries:
        attempts += 1
        t0 = time.time()
        try:
            resp = client(m.region).converse(**req)
            last_err = None
            break
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            last_err = f"{code}: {e.response.get('Error', {}).get('Message', '')}"[:500]
            if code not in RETRYABLE:
                break
        except (ReadTimeoutError, ConnectionClosedError, EndpointConnectionError) as e:
            last_err = f"{type(e).__name__}: {e}"[:500]
        time.sleep(min(60, 2 ** attempts + random.random() * 2))
    rec["attempts"] = attempts
    if last_err:
        rec.update(error=last_err, latency_s=None, input_tokens=0, output_tokens=0, cost_usd=0.0,
                   json_valid=False, schema_complete=False, prediction=None, raw=None)
        return rec

    latency = time.time() - t0
    usage = resp.get("usage", {})
    itok, otok = usage.get("inputTokens", 0), usage.get("outputTokens", 0)
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
    rec.update(
        error=None,
        latency_s=round(latency, 2),
        input_tokens=itok,
        output_tokens=otok,
        cost_usd=round(itok * m.price_in / 1e6 + otok * m.price_out / 1e6, 6),
        stop_reason=resp.get("stopReason"),
        mode_used=used,
        json_valid=pred is not None,
        schema_complete=pred is not None and all(k in pred for k in P.FIELD_ORDER),
        prediction=pred,
        raw={"text": text[-4000:], "tool_inputs": tool_inputs},
    )
    return rec


# ------------------------------------------------------------------ cost estimate
def estimate_cost(models: list[ModelCfg], bills: list[Bill], repeat: int, args) -> float:
    total = 0.0
    for m in models:
        for b in bills:
            n_img = min(args.pdf_pages, len(pymupdf.open(b.path))) if b.kind == "pdf" else 1
            itok = 2500 + 2000 * n_img  # prompt+schema + ~2k tokens per image
            otok = 900 * (4 if m.reasoning else 1)
            total += (itok * m.price_in + otok * m.price_out) / 1e6 * repeat
    return total


# ------------------------------------------------------------------ summary
def pct(xs: list[float], q: float):
    if not xs:
        return None
    xs = sorted(xs)
    k = max(0, min(len(xs) - 1, int(round(q * len(xs) + 0.5)) - 1))
    return xs[k]


def fmt(v, nd=1, suffix=""):
    return "-" if v is None else f"{v:.{nd}f}{suffix}"


def summarize(run: dict) -> str:
    recs = run["records"]
    bills = {b["id"]: b for b in run["bills"]}
    models = list(dict.fromkeys(r["model"] for r in recs))
    lines = [f"# Bill extraction benchmark", "",
             f"Run `{run['run_id']}` · prompt `{run['prompt_version']}` · {len(bills)} bills · repeat {run['args']['repeat']} · "
             f"total cost ${run['total_cost_usd']:.3f}", "",
             "Scores are out of 100 (weights in eval/SCHEMA.md). Failed calls score 0. "
             "\"photo\" = any difficulty other than clean. \"non-Latin\" = label languages include an Indian script.", ""]
    hdr = "| model | invocation id | mode used | n | mean | clean | photo | non-Latin | JSON valid | errors | p50 s | p95 s | $/bill | score sd (repeats) |"
    lines += [hdr, "|" + "---|" * (hdr.count("|") - 1)]
    rows = []
    per_model_fields: dict[str, dict[str, float]] = {}
    for mk in models:
        rs = [r for r in recs if r["model"] == mk]
        sc = [r["score"] for r in rs]
        clean = [r["score"] for r in rs if bills[r["bill"]]["difficulty"] == "clean"]
        photo = [r["score"] for r in rs if bills[r["bill"]]["difficulty"] != "clean"]
        nonlat = [r["score"] for r in rs if bills[r["bill"]]["non_latin"]]
        lat = [r["latency_s"] for r in rs if r.get("latency_s") is not None]
        ok = [r for r in rs if not r.get("error")]
        cost = [r["cost_usd"] for r in ok]
        modes = sorted({r.get("mode_used") or r["mode"] for r in rs})
        # consistency: per-bill stddev across repeats
        sds = []
        for bid in {r["bill"] for r in rs}:
            s = [r["score"] for r in rs if r["bill"] == bid]
            if len(s) > 1:
                sds.append(statistics.pstdev(s))
        mean = statistics.mean(sc) if sc else None
        rows.append((mean or 0, f"| {mk} | `{rs[0]['model_id']}` | {', '.join(modes)} | {len(rs)} | {fmt(mean)} | "
                     f"{fmt(statistics.mean(clean) if clean else None)} | {fmt(statistics.mean(photo) if photo else None)} | "
                     f"{fmt(statistics.mean(nonlat) if nonlat else None)} | {fmt(100 * sum(r['json_valid'] for r in rs) / len(rs), 0, '%')} | "
                     f"{sum(1 for r in rs if r.get('error'))} | {fmt(pct(lat, .5))} | {fmt(pct(lat, .95))} | "
                     f"{fmt(statistics.mean(cost) if cost else None, 4)} | {fmt(statistics.mean(sds) if sds else None)} |"))
        per_model_fields[mk] = {f: statistics.mean(r["fields"][f] for r in rs) for f in S.ALL_FIELDS} if rs else {}
    lines += [r for _, r in sorted(rows, key=lambda x: -x[0])]
    order = [mk for mk, _ in sorted(((mk, statistics.mean(r["score"] for r in recs if r["model"] == mk)) for mk in models), key=lambda x: -x[1])]

    lines += ["", "## Per-field accuracy (% of bills where the field was right)", ""]
    lines += ["| field | weight | " + " | ".join(order) + " |", "|---|---|" + "---|" * len(order)]
    for f in S.ALL_FIELDS:
        lines.append(f"| {f} | {S.FIELD_WEIGHTS.get(f, 0):.2f} | " + " | ".join(fmt(100 * per_model_fields[mk][f], 0) for mk in order) + " |")

    lines += ["", "## Weakest fields per model (by points lost)", ""]
    for mk in order:
        lines.append(f"- **{mk}**: " + weakest(per_model_fields[mk]))

    errs = [r for r in recs if r.get("error")]
    if errs:
        lines += ["", "## Errors", ""]
        seen = set()
        for r in errs:
            k = (r["model"], r["error"][:120])
            if k in seen:
                continue
            seen.add(k)
            lines.append(f"- {r['model']} / {r['bill']}: {r['error'][:300]}")
    lines += ["", f"Raw results: `{run['results_path']}`", ""]
    return "\n".join(lines)


def weakest(fields: dict[str, float], n=4) -> str:
    lost = sorted(((S.FIELD_WEIGHTS.get(f, 0) * (1 - v), f, v) for f, v in fields.items() if S.FIELD_WEIGHTS.get(f)), reverse=True)
    return ", ".join(f"{f} ({100 * v:.0f}%, -{pts:.1f} pts)" for pts, f, v in lost[:n] if pts > 0) or "none"


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", help="comma list of model keys, or 'all' (incl. disabled). Default: all enabled.")
    ap.add_argument("--bills", help="comma list of globs on bill folder names (default: all not starting with '_')")
    ap.add_argument("--repeat", type=int, default=1, help="runs per (model, bill) for consistency")
    ap.add_argument("--out", help="results JSON path (default eval/results/<timestamp>.json)")
    ap.add_argument("--summary", default=str(RESULTS_DIR / "SUMMARY.md"))
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--per-model", type=int, default=2, help="max in-flight calls per model (low quotas, e.g. Pixtral)")
    ap.add_argument("--max-retries", type=int, default=8)
    ap.add_argument("--max-edge", type=int, default=2000, help="longest image side in px sent to the model")
    ap.add_argument("--pdf-pages", type=int, default=2)
    ap.add_argument("--pdf-mode", choices=["auto", "image"], default="auto",
                    help="auto: document block for models that support it when the PDF has a text layer, else render pages")
    ap.add_argument("--budget", type=float, default=8.0, help="abort if estimated cost is above this (USD) unless --yes")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="print plan + cost estimate and exit")
    ap.add_argument("--list-models", action="store_true")
    ap.add_argument("--resummarize", metavar="RESULTS_JSON", help="re-score an existing results file against current labels and rebuild SUMMARY.md")
    args = ap.parse_args()

    if args.list_models:
        print(f"{'key':16} {'on':3} {'mode':9} {'region':11} {'$in/M':>7} {'$out/M':>7}  invocation id  note")
        for m in MODELS:
            print(f"{m.key:16} {'y' if m.enabled else '-':3} {m.mode:9} {m.region:11} {m.price_in:7.3f} {m.price_out:7.2f}  {m.model_id}  {m.note}")
        return

    if args.resummarize:
        # Re-score stored predictions against the labels currently on disk (no model calls).
        rpath = Path(args.resummarize)
        run = json.loads(rpath.read_text())
        labels = {b.id: b.label for b in find_bills("*")}
        for r in run["records"]:
            if r["bill"] in labels and r.get("prediction") is not None:
                sc = S.score(labels[r["bill"]].get("fields", {}), r["prediction"])
                r["score"], r["fields"] = sc["score"], sc["fields"]
        run["total_cost_usd"] = round(sum(r["cost_usd"] for r in run["records"]), 4)
        rpath.write_text(json.dumps(run, ensure_ascii=False, indent=1))
        Path(args.summary).write_text(summarize(run))
        print(f"wrote {args.summary}")
        return

    if args.models in (None, ""):
        models = [m for m in MODELS if m.enabled]
    elif args.models == "all":
        models = list(MODELS)
    else:
        keys = [k.strip() for k in args.models.split(",") if k.strip()]
        bad = [k for k in keys if k not in MODEL_BY_KEY]
        if bad:
            sys.exit(f"unknown model keys: {bad}. Use --list-models.")
        models = [MODEL_BY_KEY[k] for k in keys]

    bills = find_bills(args.bills)
    if not bills:
        sys.exit(f"no bills found in {BILLS_DIR} matching {args.bills or '[!_]*'}")

    est = estimate_cost(models, bills, args.repeat, args)
    n_calls = len(models) * len(bills) * args.repeat
    print(f"{len(models)} models x {len(bills)} bills x {args.repeat} = {n_calls} calls, estimated cost ${est:.2f}")
    if args.dry_run:
        for m in models:
            print(f"  {m.key:16} {m.model_id} ({m.region}, {m.mode})")
        return
    if est > args.budget and not args.yes:
        sys.exit(f"estimated cost ${est:.2f} > budget ${args.budget:.2f}; pass --yes to run anyway")

    run_id = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = Path(args.out) if args.out else RESULTS_DIR / f"{run_id}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    raw_dir = RESULTS_DIR / "raw" / run_id
    raw_dir.mkdir(parents=True, exist_ok=True)

    tasks = [(m, b, rep) for m in models for b in bills for rep in range(args.repeat)]
    model_sem = {m.key: threading.Semaphore(args.per_model) for m in models}
    random.Random(0).shuffle(tasks)  # interleave models to spread throttling
    records, spent, lock = [], 0.0, threading.Lock()

    def work(task):
        m, b, rep = task
        try:
            with model_sem[m.key]:
                rec = call_model(m, b, args)
        except Exception as e:  # never let one bad call kill the run
            rec = {"model": m.key, "model_id": m.model_id, "region": m.region, "bill": b.id, "mode": m.mode,
                   "error": f"{type(e).__name__}: {e}"[:500], "latency_s": None, "input_tokens": 0, "output_tokens": 0,
                   "cost_usd": 0.0, "json_valid": False, "schema_complete": False, "prediction": None, "raw": None}
        rec["repeat"] = rep
        sc = S.score(b.label.get("fields", {}), rec.get("prediction"))
        rec["score"], rec["fields"] = sc["score"], sc["fields"]
        if rec.get("prediction") is None:  # failed call or unparseable output scores 0
            rec["score"], rec["fields"] = 0.0, {f: 0.0 for f in sc["fields"]}
        (raw_dir / f"{m.key}__{b.id}__{rep}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
        rec.pop("raw", None)
        return rec

    t_start = time.time()
    with cf.ThreadPoolExecutor(args.workers) as ex:
        futs = [ex.submit(work, t) for t in tasks]
        for i, f in enumerate(cf.as_completed(futs), 1):
            r = f.result()
            with lock:
                records.append(r)
                spent += r["cost_usd"]
            status = f"ERR {r['error'][:90]}" if r.get("error") else (
                f"{r['score']:5.1f}  {r['latency_s']:5.1f}s  {r['input_tokens']}/{r['output_tokens']} tok  ${r['cost_usd']:.4f}  {r.get('mode_used')}")
            print(f"[{i:3d}/{len(tasks)}] {r['model']:16} {r['bill']:28} {status}", flush=True)

    run = {
        "run_id": run_id,
        "prompt_version": P.PROMPT_VERSION,
        "args": vars(args),
        "models": [m.__dict__ for m in models],
        "bills": [{"id": b.id, "difficulty": b.difficulty, "languages": b.label.get("languages"), "non_latin": b.non_latin,
                   "kind": b.kind} for b in bills],
        "records": sorted(records, key=lambda r: (r["model"], r["bill"], r["repeat"])),
        "total_cost_usd": round(spent, 4),
        "wall_s": round(time.time() - t_start, 1),
        "results_path": str(out_path.relative_to(ROOT)) if out_path.is_relative_to(ROOT) else str(out_path),
    }
    out_path.write_text(json.dumps(run, ensure_ascii=False, indent=1))
    Path(args.summary).write_text(summarize(run))

    print(f"\nspent ${spent:.4f} in {run['wall_s']}s. results: {out_path}  summary: {args.summary}\n")
    print("weakest fields per model:")
    for mk in dict.fromkeys(r["model"] for r in records):
        rs = [r for r in records if r["model"] == mk]
        fields = {f: statistics.mean(r["fields"][f] for r in rs) for f in S.ALL_FIELDS}
        print(f"  {mk:16} mean {statistics.mean(r['score'] for r in rs):5.1f}  weakest: {weakest(fields, 3)}")


if __name__ == "__main__":
    main()

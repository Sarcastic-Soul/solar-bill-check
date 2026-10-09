"""POST /speak {text, lang}: Polly Kajal (neural) reads the text aloud.

Returns JSON with base64 MP3 (the frontend plays it as a data: URL). This is simpler than a
presigned S3 link and works through the Function URL (an answer of ~1500 chars is ~150 KB).
"""

from __future__ import annotations

import base64
import re

from . import aws
from .errors import ApiError

MAX_CHARS = 1500
VOICES = {"hi": ("Kajal", "hi-IN"), "en": ("Kajal", "en-IN")}


def cap_text(text: str, limit: int = MAX_CHARS) -> tuple[str, bool]:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text, False
    cut = text[:limit]
    ends = [m.end() for m in re.finditer(r"[.!?।॥](\s|$)", cut)]  # . ! ? and Devanagari danda
    if ends and ends[-1] > limit // 2:
        return cut[:ends[-1]].strip(), True
    return cut.rsplit(" ", 1)[0], True


def speak(body: dict) -> dict:
    text = body.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ApiError("NO_TEXT", "Nothing to read out.", 400)
    lang = str(body.get("lang") or "en").lower()[:2]
    if lang not in VOICES:
        raise ApiError("LANG_NOT_SUPPORTED", "Listen is available in Hindi and English only.", 400,
                       {"supported": sorted(VOICES)})
    text, truncated = cap_text(text)
    voice, code = VOICES[lang]
    resp = aws.polly().synthesize_speech(Text=text, TextType="text", VoiceId=voice, LanguageCode=code,
                                         Engine="neural", OutputFormat="mp3", SampleRate="24000")
    audio = resp["AudioStream"].read()
    return {"audio": base64.b64encode(audio).decode("ascii"), "contentType": "audio/mpeg", "voice": voice,
            "languageCode": code, "chars": len(text), "truncated": truncated}

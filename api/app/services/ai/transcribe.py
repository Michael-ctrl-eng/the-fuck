"""Speech-to-text for voice notes (faster-whisper, fully local).

Long audio is handled internally by faster-whisper: it runs VAD and
transcribes in 30-second windows, so a 15-minute voice note is processed in
chunks without losing anything. Transcription is CPU-bound, so we run it in a
thread and cap concurrency to avoid stalling the event loop / CPU.

If faster-whisper is not installed, every call returns None and logs once —
the rest of the platform keeps working (voice notes are just left untranscribed).
"""

from __future__ import annotations

import asyncio
import shutil
import structlog
import tempfile
import threading
from pathlib import Path

import httpx

from ...config import Settings

log = structlog.get_logger("raqib.whisper")

try:  # pragma: no cover - import guard
    from faster_whisper import WhisperModel

    _WHISPER_AVAILABLE = True
except Exception:  # noqa: BLE001
    WhisperModel = None  # type: ignore[assignment,misc]
    _WHISPER_AVAILABLE = False

AUDIO_EXTENSIONS = {".m4a", ".ogg", ".mp3", ".wav", ".opus", ".amr", ".aac", ".oga", ".webm"}

_model_lock = threading.Lock()
_model: object | None = None
_model_meta: tuple[str, str, str] | None = None  # (model, device, compute)
_warned_missing = False


def _classify_attachment(att: dict) -> str | None:
    """Return 'audio' | 'image' | 'video' | None for a Meta attachment dict."""
    mime = str(att.get("mime_type") or "").lower()
    url = str(att.get("file_url") or "").lower()
    if mime.startswith("audio") or Path(url).suffix in AUDIO_EXTENSIONS:
        return "audio"
    if mime.startswith("image") or att.get("image_data") or Path(url).suffix in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic"}:
        return "image"
    if mime.startswith("video") or att.get("video_data"):
        return "video"
    if url:
        return "image"  # untyped file link — treat as media, not audio
    return None


def _get_model(settings: Settings):
    """Lazy singleton WhisperModel (thread-safe)."""
    global _model, _model_meta
    meta = (settings.whisper_model, settings.whisper_device, settings.whisper_compute_type)
    if _model is not None and _model_meta == meta:
        return _model
    with _model_lock:
        if _model is not None and _model_meta == meta:
            return _model
        if not _WHISPER_AVAILABLE:
            return None
        model = WhisperModel(
            settings.whisper_model,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )
        _model, _model_meta = model, meta
        log.info("whisper.model_loaded", model=settings.whisper_model, device=settings.whisper_device)
        return model


def _run_model(path: str, settings: Settings) -> str | None:
    model = _get_model(settings)
    if model is None:
        return None
    language = settings.whisper_language.strip() or None
    segments, _info = model.transcribe(
        path,
        language=language,
        vad_filter=True,
        beam_size=settings.whisper_beam_size,
    )
    parts = [seg.text.strip() for seg in segments]
    return " ".join(p for p in parts if p)


async def transcribe_audio(settings: Settings, url: str) -> str | None:
    """Download a voice-note URL and return its transcription (or None)."""
    global _warned_missing
    if not url or not _WHISPER_AVAILABLE:
        if not _warned_missing:
            _warned_missing = True
            log.warning("whisper.unavailable", hint="install faster-whisper (api/requirements-ai.txt)")
        return None

    tmp: Path | None = None
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=settings.whisper_download_timeout) as client:
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                size_hint = int(resp.headers.get("content-length") or 0)
                if size_hint > settings.whisper_max_audio_bytes:
                    log.warning("whisper.audio_too_large", size=size_hint)
                    return None
                tmp = Path(tempfile.mkstemp(suffix=".m4a")[1])
                written = 0
                with tmp.open("wb") as fh:
                    async for chunk in resp.aiter_bytes(64 * 1024):
                        written += len(chunk)
                        if written > settings.whisper_max_audio_bytes:
                            log.warning("whisper.audio_stream_too_large", written=written)
                            return None
                        fh.write(chunk)
        return await asyncio.to_thread(_run_model, str(tmp), settings)
    except Exception as exc:  # noqa: BLE001
        log.warning("whisper.transcribe_failed", url=url[:120], error=str(exc)[:300])
        return None
    finally:
        if tmp is not None:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                shutil.rmtree(tmp, ignore_errors=True)


_transcribe_semaphore = asyncio.Semaphore(2)


async def transcribe_message_audio(
    session,
    msg,
    settings: Settings,
) -> str | None:
    """Transcribe a message's voice notes and persist the text on the row.

    Idempotent: if the message already has a transcript it is returned as-is.
    Only the first audio URL is transcribed (a voice note is a single file);
    results are written to msg.transcribed_text plus the normalized fields so
    the rest of the pipeline (analysis, auto-reply) sees plain text.
    """
    audio_urls = list(msg.audio_urls or [])
    if not audio_urls:
        return None
    if msg.transcribed_text:
        return msg.transcribed_text

    async with _transcribe_semaphore:
        text = await transcribe_audio(settings, audio_urls[0])
    if not text:
        return None

    # Persist: keep user-supplied text (if any) and store the transcript too.
    msg.transcribed_text = text
    if not (msg.text_raw or "").strip():
        msg.text_raw = text
        from ..arabic import is_arabizi, normalize_arabic, transliterate_arabizi

        if is_arabizi(text):
            translit, _conf = transliterate_arabizi(text)
            msg.text_normalized = normalize_arabic(text, strong=True) or text
            msg.text_arabizi = translit or msg.text_arabizi
        else:
            msg.text_normalized = normalize_arabic(text, strong=True) or text
    return text


async def prewarm_whisper(settings: Settings) -> None:
    """Load the Whisper model at startup so the first voice note is instant.

    Runs in a worker thread (model load is blocking); failures are logged and
    swallowed so startup never breaks (transcription will lazy-load instead).
    """
    if not _WHISPER_AVAILABLE:
        return
    try:
        model = await asyncio.to_thread(_get_model, settings)
        if model is not None:
            log.info("whisper.prewarmed", model=settings.whisper_model, device=settings.whisper_device)
    except Exception as exc:  # noqa: BLE001
        log.warning("whisper.prewarm_failed", error=str(exc)[:300])
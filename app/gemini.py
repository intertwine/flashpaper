"""Gemini client wrapper for FlashPaper.

Handles Files API uploads, context caching (when available), generation with the master prompt,
and streaming for chat follow-ups.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from app.config import settings

logger = logging.getLogger(__name__)

_client: genai.Client | None = None


def get_client() -> genai.Client:
    """Lazy singleton Gemini client with long timeout suitable for massive paper + code-gen calls."""
    global _client
    if _client is None:
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not set and DEMO_MODE is false")

        # Very long timeout — some papers + rich HTML output can take 2-3 minutes of thinking + generation
        http_opts = types.HttpOptions(timeout=300)  # 5 minutes

        _client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=http_opts,
        )
    return _client


async def upload_pdf_to_gemini(pdf_bytes: bytes, display_name: str = "paper.pdf") -> str | bytes:
    """
    Upload PDF bytes using the Gemini Files API (for larger files) or return the bytes
    for inline use (small PDFs). Returns either a file URI string or the raw bytes.
    """
    client = get_client()
    size = len(pdf_bytes)

    # For small PDFs, sending inline is faster and more reliable in some network conditions.
    # Gemini supports several MB inline; we use a conservative threshold.
    INLINE_THRESHOLD = 1_500_000  # ~1.5 MB
    if size < INLINE_THRESHOLD:
        logger.info(f"Using inline bytes for small PDF ({size} bytes)")
        return pdf_bytes  # caller will wrap as Part.from_bytes

    # Larger file → use Files API
    try:
        cfg = types.UploadFileConfig(
            display_name=display_name[:40],
            mime_type="application/pdf",
        )
        file_like = io.BytesIO(pdf_bytes)
        uploaded = client.files.upload(file=file_like, config=cfg)
        logger.info(f"Uploaded PDF to Gemini Files: {uploaded.name} (size={uploaded.size_bytes})")
        return uploaded.uri or uploaded.name or uploaded.display_name or "unknown"
    except Exception as e:
        logger.exception("Gemini file upload failed")
        raise RuntimeError(f"Failed to upload PDF to Gemini: {e}") from e


def build_generation_config(extra: dict[str, Any] | None = None) -> types.GenerateContentConfig:
    """Return a sensible default config for paper analysis."""
    cfg = {
        "temperature": 0.35,
        "top_p": 0.95,
        "max_output_tokens": settings.gemini_max_output_tokens,
        "safety_settings": [
            # Research papers are technical; be permissive on science topics
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
            ),
        ],
    }
    if extra:
        cfg.update(extra)
    return types.GenerateContentConfig(**cfg)


async def generate_paper_explainer(
    pdf_file_uri: str | bytes,
    custom_instructions: str | None = None,
) -> str:
    """
    Core call: send the uploaded PDF + master prompt to Gemini and return the full HTML string.
    This is the expensive long-context + code-gen step.
    """
    client = get_client()

    # Read the master prompt (we will make it much richer in Phase 2)
    prompt_path = Path("prompts/master.txt")
    base_prompt = (
        prompt_path.read_text(encoding="utf-8")
        if prompt_path.exists()
        else "Analyze the paper and produce a beautiful interactive HTML explainer."
    )

    full_prompt = base_prompt
    if custom_instructions:
        full_prompt += "\n\n## USER FOCUS INSTRUCTIONS\n" + custom_instructions

    if isinstance(pdf_file_uri, (bytes, bytearray)):
        # Inline small PDF
        paper_part = types.Part.from_bytes(data=bytes(pdf_file_uri), mime_type="application/pdf")
    else:
        # File URI from the Files API
        paper_part = types.Part.from_uri(file_uri=pdf_file_uri, mime_type="application/pdf")

    contents = [paper_part, full_prompt]

    logger.info(
        f"Calling {settings.gemini_model} for paper explainer (max_tokens={settings.gemini_max_output_tokens})"
    )

    try:
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=contents,
            config=build_generation_config(),
        )
        html = response.text or ""
        if not html.strip().startswith("<!DOCTYPE"):
            # Sometimes the model adds markdown fences; try to extract
            if "```html" in html:
                html = html.split("```html", 1)[1].split("```", 1)[0].strip()
            elif "```" in html[:200]:
                html = html.split("```", 1)[1].split("```", 1)[0].strip()
        return html
    except Exception as e:
        logger.exception("Gemini generation failed")
        raise RuntimeError(f"Gemini generation error: {e}") from e


# --- Future: context caching + streaming chat helpers (Phase 5) ---
# async def create_paper_context_cache(...): ...
# async def stream_chat_answer(...): ...

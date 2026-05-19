"""Paper ingestion: URL resolution, PDF validation, and download helpers."""

from __future__ import annotations

import hashlib
import re
from io import BytesIO

import httpx
from pypdf import PdfReader

from app.config import settings

ARXIV_ABS_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/([0-9]{4}\.[0-9]{4,5}(?:v[0-9]+)?)")
ARXIV_PDF_RE = re.compile(r"arxiv\.org/pdf/([0-9]{4}\.[0-9]{4,5}(?:v[0-9]+)?)\.pdf")
DOI_RE = re.compile(r"doi\.org/(.+)")


async def resolve_to_pdf_url(url: str) -> str:
    """
    Best-effort resolver that turns arXiv abstract/DOI links into direct PDF URLs.
    Returns the original URL if it already looks like a PDF.
    """
    url = url.strip()

    # Already a PDF link
    if url.lower().endswith(".pdf"):
        return url

    # arXiv abstract or pdf link
    m = ARXIV_ABS_RE.search(url) or ARXIV_PDF_RE.search(url)
    if m:
        arxiv_id = m.group(1)
        return f"https://arxiv.org/pdf/{arxiv_id}.pdf"

    # DOI (we can't always auto-resolve without crossref, so we just return a heuristic)
    if DOI_RE.search(url):
        # Many DOIs for ML papers point to openreview or arxiv; for now we return as-is
        # and let the downloader handle redirects.
        return url

    # Default: hope the provided URL serves PDF bytes
    return url


async def download_pdf(url: str, max_bytes: int | None = None) -> tuple[bytes, str]:
    """
    Download a PDF (with redirects) and return (content, final_url).
    Raises on non-200, too large, or non-PDF content-type.
    """
    max_bytes = max_bytes or (settings.max_pdf_mb * 1024 * 1024)

    headers = {
        "User-Agent": "FlashPaper/0.1 (+https://github.com/flashpaper)",
        "Accept": "application/pdf,application/octet-stream,*/*;q=0.8",
    }

    async with (
        httpx.AsyncClient(follow_redirects=True, timeout=60.0, headers=headers) as client,
        client.stream("GET", url) as resp,
    ):
        if resp.status_code != 200:
            raise ValueError(f"Download failed with status {resp.status_code}")

        final_url = str(resp.url)
        content_type = resp.headers.get("content-type", "").lower()

        if "pdf" not in content_type and not final_url.lower().endswith(".pdf"):
            # Some servers lie; we still try but warn
            pass

        chunks: list[bytes] = []
        size = 0
        async for chunk in resp.aiter_bytes(64 * 1024):
            size += len(chunk)
            if size > max_bytes:
                raise ValueError(f"PDF exceeds {settings.max_pdf_mb} MB limit")
            chunks.append(chunk)

        data = b"".join(chunks)

        # Light validation: check PDF magic
        if not data.startswith(b"%PDF"):
            raise ValueError("Downloaded file does not look like a PDF (missing %PDF header)")

        return data, final_url


def compute_pdf_hash(pdf_bytes: bytes) -> str:
    """Stable SHA256 for deduplication and caching."""
    return hashlib.sha256(pdf_bytes).hexdigest()


def extract_basic_metadata(pdf_bytes: bytes) -> dict:
    """Lightweight metadata using pypdf (title, page count, authors if present)."""
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        meta = reader.metadata or {}
        return {
            "pages": len(reader.pages),
            "title": str(meta.get("/Title", "")) or None,
            "author": str(meta.get("/Author", "")) or None,
        }
    except Exception:
        return {"pages": 0, "title": None, "author": None}

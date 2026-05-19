"""FlashPaper FastAPI application entrypoint.

Beautiful zero-build web app (Jinja + Tailwind CDN + vanilla JS) that turns
academic papers into stunning interactive explanations using Gemini 3.5 Flash.
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.cors import CORSMiddleware

from app.config import settings

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("flashpaper")


# -----------------------------------------------------------------------------
# Lifespan (DB, caches, Gemini client init)
# -----------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: init resources, warm demo cache, etc."""
    logger.info("Starting FlashPaper...")
    logger.info(f"Demo mode: {settings.is_demo_mode}")
    logger.info(f"Model: {settings.gemini_model}")
    logger.info(f"Generated artifacts dir: {settings.generated_dir.resolve()}")

    # TODO Phase 3+: initialize SQLite connection pool here
    # TODO Phase 1+: initialize Gemini client

    # Warm up demo list
    demo_count = len(list(settings.demo_dir.glob("*.html"))) if settings.demo_dir.exists() else 0
    logger.info(f"Found {demo_count} demo explainers")

    yield

    logger.info("Shutting down FlashPaper...")


# -----------------------------------------------------------------------------
# FastAPI App
# -----------------------------------------------------------------------------
app = FastAPI(
    title="FlashPaper",
    description="Turn any academic paper into a beautiful, fully interactive visual website using Gemini 3.5 Flash.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None,  # We will have our own beautiful docs/landing
    redoc_url=None,
)

# CORS for local dev (tighten in prod)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: lock down for prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files (CSS/JS we control + generated artifacts served safely)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount(
    "/generated", StaticFiles(directory=str(settings.generated_dir), html=True), name="generated"
)

# Jinja2 templates
templates = Jinja2Templates(directory="app/templates")


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def get_request_ip(request: Request) -> str:
    """Best-effort client IP (works behind proxies in simple setups)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# -----------------------------------------------------------------------------
# Routes - Phase 0 (beautiful landing + health + basic viewer stub)
# -----------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def landing(request: Request) -> HTMLResponse:
    """The main landing page — elegant, fast, conversion-focused."""
    # Curated famous papers with rich metadata for the "instant try" casual-user section
    # Corresponding .html files must exist in demo/
    FAMOUS_PAPERS = {
        "attention-is-all-you-need": {
            "title": "Attention Is All You Need",
            "year": "2017",
            "venue": "NeurIPS",
            "tagline": "The paper that introduced the Transformer and changed AI forever.",
        },
        "deep-residual-learning": {
            "title": "Deep Residual Learning (ResNet)",
            "year": "2016",
            "venue": "CVPR",
            "tagline": "Skip connections that made training 100+ layer networks possible.",
        },
        "adam-optimizer": {
            "title": "Adam: A Method for Stochastic Optimization",
            "year": "2015",
            "venue": "ICLR",
            "tagline": "The optimizer behind almost every modern neural net training run.",
        },
    }

    demos = []
    if settings.demo_dir.exists():
        for path in sorted(settings.demo_dir.glob("*.html")):
            slug = path.stem
            meta = FAMOUS_PAPERS.get(slug, {})
            title = meta.get("title") or slug.replace("-", " ").title()
            demos.append(
                {
                    "slug": slug,
                    "title": title,
                    "year": meta.get("year"),
                    "venue": meta.get("venue"),
                    "tagline": meta.get("tagline"),
                }
            )

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "demo_mode": settings.is_demo_mode,
            "model_name": settings.gemini_model,
            "demos": demos,
            "year": time.strftime("%Y"),
        },
    )


@app.get("/health", response_class=JSONResponse)
async def health() -> dict[str, Any]:
    """Liveness + basic readiness for load balancers / monitoring."""
    demo_files = len(list(settings.demo_dir.glob("*.html"))) if settings.demo_dir.exists() else 0
    return {
        "status": "healthy",
        "demo_mode": settings.is_demo_mode,
        "model": settings.gemini_model,
        "demos_available": demo_files,
        "timestamp": int(time.time()),
    }


@app.get("/p/{slug}", response_class=HTMLResponse)
async def view_explainer(request: Request, slug: str) -> HTMLResponse:
    """
    Serve a generated or demo explainer.
    Demo files get a nice minimal chrome. Real generated files are served raw (they are self-contained websites).
    """
    demo_path = settings.demo_dir / f"{slug}.html"
    real_path = settings.generated_dir / f"{slug}.html"

    if demo_path.exists():
        html = demo_path.read_text(encoding="utf-8")
        # Nice thin chrome for demos
        return HTMLResponse(
            content=f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>FlashPaper • {slug}</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>body{{margin:0;background:#0a0a0a}}</style>
</head><body>
<div class="fixed top-0 inset-x-0 z-50 bg-black/80 backdrop-blur border-b border-white/10">
  <div class="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between text-sm text-white/70">
    <div class="flex items-center gap-3"><span class="font-semibold tracking-tight text-white">FlashPaper</span>
    <span class="text-emerald-400">•</span><span>Demo</span></div>
    <div class="flex items-center gap-4">
      <a href="/" class="hover:text-white">← New paper</a>
      <a href="/p/{slug}" download class="px-3 py-1 rounded bg-white/10 hover:bg-white/20">Download HTML</a>
    </div>
  </div>
</div>
<div class="pt-14">{html}</div>
</body></html>""",
            status_code=200,
        )

    if real_path.exists():
        # Real generated self-contained websites are served as-is
        return HTMLResponse(content=real_path.read_text(encoding="utf-8"))

    return HTMLResponse("<h1>Not found</h1><a href='/'>Home</a>", status_code=404)


@app.get("/examples", response_class=HTMLResponse)
async def examples(request: Request) -> HTMLResponse:
    """Gallery of beautiful pre-seeded explainers."""
    demos = []
    if settings.demo_dir.exists():
        for path in sorted(settings.demo_dir.glob("*.html")):
            demos.append({"slug": path.stem, "title": path.stem.replace("-", " ").title()})
    return templates.TemplateResponse(
        request=request,
        name="examples.html",
        context={"demos": demos},
    )


# -----------------------------------------------------------------------------
# Real analyze endpoint (Phase 3 wiring)
# -----------------------------------------------------------------------------

_jobs: dict[str, dict] = {}  # job_id -> status dict (MVP in-memory)


@app.post("/analyze")
async def analyze(
    request: Request,
    url: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
) -> JSONResponse:
    """Accept URL or PDF upload, start (or run) generation, return job or immediate result."""
    ip = get_request_ip(request)
    logger.info(f"Analyze from {ip} url={bool(url)} file={bool(file)} demo={settings.is_demo_mode}")

    if settings.is_demo_mode:
        best = "attention-is-all-you-need"
        return JSONResponse(
            {
                "job_id": "demo",
                "status": "completed",
                "slug": best,
                "url": f"/p/{best}",
                "message": "Demo mode active — showing curated high-quality explainer.",
            }
        )

    # Real path
    try:
        from app import gemini, ingest

        pdf_bytes: bytes | None = None
        original_ref = "uploaded.pdf"

        if file:
            if not file.filename or not file.filename.lower().endswith(".pdf"):
                return JSONResponse({"error": "Only PDF files are supported"}, status_code=400)
            pdf_bytes = await file.read()
            original_ref = file.filename
        elif url:
            pdf_url = await ingest.resolve_to_pdf_url(url)
            pdf_bytes, final_url = await ingest.download_pdf(pdf_url)
            original_ref = final_url
        else:
            return JSONResponse({"error": "Provide either 'url' or 'file'"}, status_code=400)

        # Size check (already done in download, but for upload)
        if len(pdf_bytes) > settings.max_pdf_mb * 1024 * 1024:
            return JSONResponse({"error": f"PDF > {settings.max_pdf_mb} MB"}, status_code=413)

        pdf_hash = ingest.compute_pdf_hash(pdf_bytes)
        slug = f"paper-{pdf_hash[:8]}"

        # Dedup: if we already generated this exact paper, return it
        existing = settings.generated_dir / f"{slug}.html"
        if existing.exists():
            return JSONResponse({"status": "completed", "slug": slug, "url": f"/p/{slug}"})

        # Create job (for future polling UI)
        job_id = f"job-{int(time.time())}-{pdf_hash[:6]}"
        _jobs[job_id] = {"status": "processing", "slug": slug, "ref": original_ref}

        # MVP: run generation synchronously (user waits ~60-120s).
        # This is acceptable for the first real end-to-end. We will add proper background + SSE later.
        try:
            file_uri = await gemini.upload_pdf_to_gemini(pdf_bytes, display_name=original_ref[:50])
            html = await gemini.generate_paper_explainer(file_uri, custom_instructions=None)
            if len(html) < 1500:
                raise ValueError(
                    "Generated output was too short — possible model error or truncation"
                )
            (settings.generated_dir / f"{slug}.html").write_text(html, encoding="utf-8")
            _jobs[job_id]["status"] = "completed"
            _jobs[job_id]["url"] = f"/p/{slug}"
            return JSONResponse(
                {"status": "completed", "slug": slug, "url": f"/p/{slug}", "job_id": job_id}
            )
        except Exception as exc:
            logger.exception("Real generation failed")
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["error"] = str(exc)[:400]
            return JSONResponse({"error": str(exc)[:400], "job_id": job_id}, status_code=500)

    except Exception as e:
        logger.exception("Analyze failed")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/jobs/{job_id}")
async def job_status(job_id: str) -> JSONResponse:
    job = _jobs.get(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    return JSONResponse(job)


# -----------------------------------------------------------------------------
# CLI entry for `flashpaper` script (future)
# -----------------------------------------------------------------------------
def cli_entry() -> None:
    """Entry point for `flashpaper` console script."""
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)

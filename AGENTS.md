# AGENTS.md — FlashPaper

For AI coding agents and future contributors.

## Architecture Summary
- Pure Python backend (FastAPI)
- Zero-build frontend (Jinja2 + Tailwind Play + vanilla JS)
- All generated output is one self-contained HTML file
- Gemini 3.5 Flash (or current best Flash) does the heavy lifting via Files API + long context

## Key Directories
- `app/` — all Python code
- `app/templates/` — Jinja pages (landing, viewer chrome, examples)
- `prompts/` — the master prompt (versioned, heavily documented)
- `demo/` — curated, high-quality, hand-verified interactive explainers (load instantly)
- `generated/` — runtime artifacts (gitignored)

## Running Linters (required)
```bash
uv run ruff check --fix && uv run ruff format && uv run basedpyright app/
```

## Adding a New Feature
1. Update the plan in the session `plan.md` (or note why you deviated)
2. Implement
3. Run linters + manual test
4. Update README + CLAUDE.md if user-facing

## The Generated Sites Must
- Be 100% self-contained (one .html)
- Use only the approved CDN list in the master prompt
- Never hallucinate paper content
- Feel like they were made by a world-class designer + engineer

## Current Phase
See the live plan file referenced from the root README.

This project ships when a complete stranger can generate a mind-blowing explainer of a 2026 arXiv paper on the first try.

# CLAUDE.md — FlashPaper Specific Rules

This file augments the root ~/.claude/Claude.md. All global rules still apply.

## Project Goals
FlashPaper turns PDFs of academic papers into stunning single-file interactive websites using Gemini 3.5 Flash's long context, PDF vision, and code generation.

## Critical Commands (always use these)
- `uv run uvicorn app.main:app --reload` — dev server
- `uv run ruff check --fix && uv run ruff format && uv run basedpyright app/` — **MUST run before finishing any code change**
- `uv add <package> && uv sync` — never pip or manual edits to pyproject
- `uv run python -c "..."` instead of bare python

## Code Style
- Keep Python code extremely clean and typed.
- New routes live in `app/routers/` when we split (currently all in main for speed).
- All HTML templates use Tailwind via CDN + minimal custom CSS.
- Generated explainers (in `demo/` and `generated/`) must be single-file, no external non-approved assets.

## Before Marking Anything "Done"
1. Run the full linter + typecheck command above and fix every issue.
2. Manually test the exact flow (URL or upload → working interactive explainer) with at least one real paper.
3. Update README.md + this file if architecture or commands changed.
4. Demo the viewer + chat (when implemented) to a colleague or record a 60s video.

## Demo Mode
While `DEMO_MODE=true` or no valid key, the site must still look and feel 100% production — using the hand-crafted demo HTMLs in `demo/`.

## The Prompt Is Sacred
`prompts/master.txt` is the single most important file for output quality. Every change must be tested against at least 3 different papers (different domains).

## Git
- Never force push.
- Commit messages are conventional (feat, fix, chore, docs).
- Large generated HTML files stay in `demo/` (curated) or `.gitignore`'d `generated/`.

## Launch Mindset
We are building something that researchers will tweet about. Every pixel and every interaction must feel intentional and delightful.

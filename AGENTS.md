# AGENTS.md

## What this project is

A small, flat three-module app: `app.py` (Streamlit UI) calls `api.py` (FastAPI), which
calls a local Ollama model, and `database.py` persists results to SQLite. There is no
installable package and no CLI. Keep it that way unless the user asks for a refactor.

## Toolchain

Python 3.14, `uv`, `pytest` (with coverage), `ruff`, `mypy`. Run everything through `uv run`.

## Working agreement

- **Responses:** Keep replies concise unless asked otherwise.
- **Planning:** For new features or design changes not covered here, ask clarifying questions first. Never assume the design, tech stack or feature set.
- **Testing:** Never assume a change works. Run the checks in "Definition of done" after every module and again at the end.
- **Git:** Never commit, push, amend, rebase or rewrite history on your own. When work is ready, summarize what would go into the commit, propose a message, and wait for an explicit yes.
- **Sub-agents (if your tool supports them):** Use them for independent, parallelizable work and for a review of your plan and diff before finishing.
- Do not parallelize steps that depend on each other.
- You own integration and run all checks yourself. Small edits are faster done directly.

## Rules

1. **Type hints everywhere.** All `.py` files, including tests.
2. **Do not over-engineer.** Keep the three modules flat; do not split into a package or extra files unless asked.
3. **Centralized configuration.** All settings come from `.env` via `os.getenv` with working defaults, documented in `.env.example`. Never commit secrets.
4. **Behavior must not change** unless a task says so.
5. **README stays truthful.** Layout, commands, env vars and API behavior in `README.md` must match the code.

## Code style

- Small, obvious functions. Keep modules focused (under about 150 lines).
- Validate only at boundaries: the Ollama call, per-review HTTP calls, JSON parsing, user input.
- Broad `except Exception` is allowed only at those boundaries, each with a comment saying why.
- Write multi-exception handlers as `except (A, B):`.
- Comments explain *why*, never *what*. No numbered lesson markers, no section banners, no stale TODOs.
- Google-style docstrings (Args, Returns, Raises) on public classes and functions.
- No module-level mutable state. Import-time work is limited to reading config in `api.py`/`app.py` and calling `init_db()` in `app.py`; everything else stays inside functions.
- Prefer the standard library. Add a dependency only for substantial value.
- No backwards-compat shims or speculative feature flags.

## Layout

| Path | Purpose |
| --- | --- |
| `api.py` | FastAPI app, prompt, `Analysis` schema, Ollama client |
| `app.py` | Streamlit UI, batch analysis, summary, save button |
| `database.py` | SQLite schema and queries (`feedback.db`) |
| `tests/` | pytest suite; 85% coverage gate lives in `pyproject.toml` |
| `.github/workflows/ci.yml` | CI: ruff, format check, mypy and pytest on push/PR |
| `.env.example` | Every supported env var with its default |

## Definition of done

All of these pass from a clean checkout:

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
uv run uvicorn api:app --port 8000   # starts; /docs responds
uv run streamlit run app.py          # starts; page renders
```

The README's run command, layout and architecture must match the code.

# Feedback Insights

Paste customer reviews into a Streamlit page and get a label, a 1–5 score and a theme for
each one. Analysis runs locally through [Ollama](https://ollama.com); results can be saved
to SQLite and reviewed later.

## How it works

```
Streamlit UI (app.py)
        |  POST /analyze {"text": "..."}
        v
FastAPI service (api.py)  ->  Ollama  ->  qwen3:0.6b
        |  {label, score, theme}
        v
Streamlit UI  ->  feedback.db (database.py, SQLite)
```

`api.py` asks the model for JSON that matches the `Analysis` schema (label, score, theme),
so the response is validated instead of parsed by hand. The UI keeps results in
`st.session_state` until you press **Save to database**.

## Prerequisites

- Python 3.14
- [uv](https://docs.astral.sh/uv/)
- [Ollama](https://ollama.com/download) running locally

```bash
ollama pull qwen3:0.6b
```

## Setup

```bash
uv sync
cp .env.example .env   # optional: the defaults match a stock Ollama install
```

## Run

Two processes are needed. Start the API first:

```bash
uv run uvicorn api:app --reload --port 8000
```

Then the UI in a second terminal:

```bash
uv run streamlit run app.py
```

Open <http://localhost:8501>, paste one review per line, and press **Analyze**.
Press **Load sample reviews** to fill the box with ten short, varied examples.
Interactive API docs are at <http://127.0.0.1:8000/docs>.

## Configuration

Copy `.env.example` to `.env`; every variable is optional.

| Variable | Used by | Default | Purpose |
| --- | --- | --- | --- |
| `OLLAMA_BASE_URL` | `api.py` | `http://localhost:11434/v1` | OpenAI-compatible endpoint of Ollama |
| `OLLAMA_MODEL` | `api.py` | `qwen3:0.6b` | Model tag to analyze with |
| `OLLAMA_API_KEY` | `api.py` | `ollama` | Placeholder key; Ollama ignores it |
| `OLLAMA_KEEP_ALIVE` | `api.py` | `30m` | How long the model stays loaded between requests |
| `OLLAMA_TIMEOUT_SECONDS` | `api.py` | `30` | Timeout for one model call |
| `OLLAMA_TEMPERATURE` | `api.py` | `0` | Sampling temperature; `0` keeps analysis deterministic |
| `OLLAMA_MAX_TOKENS` | `api.py` | `2048` | Token cap for one analysis |
| `API_URL` | `app.py` | `http://127.0.0.1:8000/analyze` | Where the UI sends reviews |
| `API_TIMEOUT_SECONDS` | `app.py` | `60` | Timeout for one UI request |
| `DB_FILE` | `database.py` | `feedback.db` | SQLite file, resolved against the working directory |

`.env` is git-ignored; never commit it.

## API

`POST /analyze`

```json
{"text": "Delivery was fast but the soup arrived cold"}
```

```json
{"label": "negative", "score": 2, "theme": "delivery"}
```

| Status | When |
| --- | --- |
| `200` | Model returned a usable analysis |
| `422` | `text` missing or longer than 2000 characters |
| `502` | Ollama unreachable, or it returned output that did not match the schema |

## Data

`feedback.db` keeps one row per saved analysis:

| Column | Type | Notes |
| --- | --- | --- |
| `id` | INTEGER | Primary key |
| `review` | TEXT | Original review text |
| `label` | TEXT | `positive`, `negative` or `neutral` (`error` if the call failed) |
| `score` | INTEGER | 1–5, or `0` for failed rows |
| `theme` | TEXT | One lowercase word |

Rows are appended on every save, so pressing save twice stores the same results twice.
The database file is git-ignored; delete it to start over.

## Project layout

| Path | Purpose |
| --- | --- |
| `api.py` | FastAPI app, model prompt and Ollama client |
| `app.py` | Streamlit UI, summary and save button |
| `database.py` | SQLite schema and queries |
| `tests/` | pytest suite covering all three modules |
| `.env.example` | Documented configuration template |
| `pyproject.toml` | Dependencies and ruff/mypy/pytest settings |

The three modules are intentionally small and flat; there is no package to import.

## Development

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest          # includes the 85% coverage gate
```

The test suite uses `streamlit.testing.v1.AppTest` and a stubbed `requests.post`, so no
network or Ollama instance is needed.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| UI rows show `error` | API not running, wrong `API_URL`, or Ollama not running (check `http://127.0.0.1:8000/docs`) |
| API returns `502` | Start Ollama and confirm `ollama list` shows the model from `OLLAMA_MODEL` |
| First analysis is slow | The model is loading; startup warms it and `OLLAMA_KEEP_ALIVE` keeps it in memory |
| History stays empty | Results must be analyzed and then saved; the history expander reads the same `feedback.db` |
| Port already in use | Pass another `--port` to uvicorn, or `--server.port` to Streamlit, and update `API_URL` |

## Limitations

- Single user, no authentication, no concurrency control: anything on the network can call the API.
- One review is one model call; long batches are slow on CPU-only machines.
- Saved rows have no timestamp, so history order is storage order.
- The model is asked for one theme word and a fixed label set; it is not validated beyond the
  `Analysis` schema, so unexpected values are shown as-is.

## License

MIT — see [LICENSE](LICENSE).

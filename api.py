"""FastAPI service that turns one customer review into a label, score and theme."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:0.6b")
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "30m")
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "30"))
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0"))
OLLAMA_MAX_TOKENS = int(os.getenv("OLLAMA_MAX_TOKENS", "2048"))

client = AsyncOpenAI(
    base_url=OLLAMA_BASE_URL,
    api_key=os.getenv("OLLAMA_API_KEY", "ollama"),
    timeout=OLLAMA_TIMEOUT_SECONDS,
)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Warm the model on startup and close the HTTP pool on shutdown.

    Args:
        _app: Application instance supplied by FastAPI (unused).

    Yields:
        Control back to FastAPI for the lifetime of the application.
    """
    # Ollama may still be booting; the first real request will surface any problem.
    with suppress(Exception):
        await client.chat.completions.create(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=1,
            extra_body={"keep_alive": OLLAMA_KEEP_ALIVE},
        )
    yield
    await client.close()


app = FastAPI(lifespan=lifespan)


class Review(BaseModel):
    """Incoming review text, capped so one giant review cannot blow up latency."""

    text: str = Field(..., max_length=2000)


class Analysis(BaseModel):
    """Structured verdict the model must return."""

    label: str
    score: int
    theme: str


# Static instructions come before user text so Ollama can reuse its prompt cache.
SYSTEM_PROMPT = (
    "You analyze customer reviews. Reply with JSON only.\n"
    "- label: 'positive' | 'negative' | 'neutral'\n"
    "- score: integer 1 (very bad) to 5 (very good)\n"
    "- theme: ONE lowercase word (delivery, taste, price, service, quality...)\n"
    'Example: {"label":"positive","score":5,"theme":"delivery"}'
)


@app.post("/analyze", response_model=Analysis)
async def analyze(review: Review) -> Analysis:
    """Analyze a single review with the local Ollama model.

    Args:
        review: Review text supplied by the caller.

    Returns:
        The parsed label, score and theme.

    Raises:
        HTTPException: 502 when Ollama is unreachable or returns unusable output.
    """
    try:
        completion = await client.chat.completions.parse(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": review.text.strip()},
            ],
            response_format=Analysis,
            temperature=OLLAMA_TEMPERATURE,
            max_tokens=OLLAMA_MAX_TOKENS,
            extra_body={"keep_alive": OLLAMA_KEEP_ALIVE},
        )
    except Exception as exc:
        # Boundary: any transport or decoding failure from the model becomes a clean 502.
        raise HTTPException(status_code=502, detail=f"Ollama request failed: {exc}") from exc

    analysis = completion.choices[0].message.parsed
    if analysis is None:
        raise HTTPException(status_code=502, detail="Ollama returned no parsable analysis")
    return analysis

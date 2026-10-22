"""Tests for the FastAPI analysis endpoint."""

import asyncio
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

import api


@pytest.fixture
def client() -> Iterator[TestClient]:
    # No context manager: skips the lifespan warm-up, which needs a live Ollama.
    yield TestClient(api.app)


def completion_with(analysis: api.Analysis | None) -> SimpleNamespace:
    message = SimpleNamespace(parsed=analysis)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


@pytest.fixture
def analysis() -> api.Analysis:
    return api.Analysis(label="positive", score=5, theme="delivery")


def test_analyze_returns_parsed_analysis(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    analysis: api.Analysis,
) -> None:
    captured: dict[str, Any] = {}

    async def fake_parse(**kwargs: Any) -> SimpleNamespace:
        captured.update(kwargs)
        return completion_with(analysis)

    monkeypatch.setattr(api.client.chat.completions, "parse", fake_parse)

    response = client.post("/analyze", json={"text": "  Arrived in a day  "})

    assert response.status_code == 200
    assert response.json() == {"label": "positive", "score": 5, "theme": "delivery"}
    assert captured["model"] == api.OLLAMA_MODEL
    assert captured["messages"][0]["role"] == "system"
    assert captured["messages"][0]["content"] == api.SYSTEM_PROMPT
    assert captured["messages"][1] == {"role": "user", "content": "Arrived in a day"}
    assert captured["response_format"] is api.Analysis
    assert captured["temperature"] == api.OLLAMA_TEMPERATURE
    assert captured["max_tokens"] == api.OLLAMA_MAX_TOKENS


def test_analyze_uses_configured_sampling_settings(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    analysis: api.Analysis,
) -> None:
    captured: dict[str, Any] = {}

    async def fake_parse(**kwargs: Any) -> SimpleNamespace:
        captured.update(kwargs)
        return completion_with(analysis)

    monkeypatch.setattr(api.client.chat.completions, "parse", fake_parse)
    monkeypatch.setattr(api, "OLLAMA_TEMPERATURE", 0.7)
    monkeypatch.setattr(api, "OLLAMA_MAX_TOKENS", 128)

    client.post("/analyze", json={"text": "Anything"})

    assert captured["temperature"] == 0.7
    assert captured["max_tokens"] == 128


def test_analyze_returns_502_when_model_returns_no_parsed_output(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_parse(**_: Any) -> SimpleNamespace:
        return completion_with(None)

    monkeypatch.setattr(api.client.chat.completions, "parse", fake_parse)

    response = client.post("/analyze", json={"text": "Anything"})

    assert response.status_code == 502
    assert "no parsable analysis" in response.json()["detail"]


def test_analyze_returns_502_when_model_call_fails(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_parse(**_: Any) -> SimpleNamespace:
        raise RuntimeError("connection refused")

    monkeypatch.setattr(api.client.chat.completions, "parse", fake_parse)

    response = client.post("/analyze", json={"text": "Anything"})

    assert response.status_code == 502
    assert "connection refused" in response.json()["detail"]


def test_analyze_rejects_text_over_the_limit(client: TestClient) -> None:
    response = client.post("/analyze", json={"text": "x" * 2001})

    assert response.status_code == 422


def test_analyze_requires_text(client: TestClient) -> None:
    response = client.post("/analyze", json={})

    assert response.status_code == 422


def test_lifespan_warms_the_model_and_closes_the_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def fake_create(**_: Any) -> SimpleNamespace:
        calls.append("create")
        return completion_with(None)

    async def fake_close() -> None:
        calls.append("close")

    monkeypatch.setattr(api.client.chat.completions, "create", fake_create)
    monkeypatch.setattr(api.client, "close", fake_close)

    async def run_lifespan() -> None:
        async with api.lifespan(api.app):
            pass

    asyncio.run(run_lifespan())

    assert calls == ["create", "close"]


def test_lifespan_survives_a_failing_warm_up(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_create(**_: Any) -> SimpleNamespace:
        raise RuntimeError("ollama not up")

    async def fake_close() -> None:
        return None

    monkeypatch.setattr(api.client.chat.completions, "create", fake_create)
    monkeypatch.setattr(api.client, "close", fake_close)

    async def run_lifespan() -> None:
        async with api.lifespan(api.app):
            pass

    asyncio.run(run_lifespan())

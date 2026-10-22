"""Tests for the Streamlit UI, driven through Streamlit's AppTest harness."""

from pathlib import Path
from typing import Any

import pytest
import requests
from streamlit.testing.v1 import AppTest

import database

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


class FakeResponse:
    """Minimal stand-in for ``requests.Response``."""

    def __init__(self, payload: dict[str, str | int], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict[str, str | int]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} Client Error")


@pytest.fixture
def at(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AppTest:
    monkeypatch.setattr(database, "DB_FILE", str(tmp_path / "feedback.db"))
    instance = AppTest.from_file(str(APP_PATH), default_timeout=30)
    instance.run()
    return instance


def stub_post(monkeypatch: pytest.MonkeyPatch, payload: dict[str, str | int]) -> None:
    def fake_post(url: str, json: dict[str, str], timeout: float) -> FakeResponse:
        return FakeResponse(payload)

    monkeypatch.setattr(requests, "post", fake_post)


def click(at: AppTest, label: str) -> None:
    for button in at.button:
        if button.label == label:
            button.click().run()
            return
    raise AssertionError(f"button {label!r} was not rendered")


def analyze(at: AppTest, text: str) -> None:
    at.text_area[0].input(text)
    click(at, "Analyze")


def test_initial_screen_renders_an_empty_history(at: AppTest) -> None:
    assert at.title[0].value == "📝 Customer Feedback Analyzer"
    assert any("Nothing saved yet" in block.value for block in at.markdown)
    assert not at.exception


def test_load_sample_reviews_fills_the_text_area(at: AppTest) -> None:
    click(at, "Load sample reviews")

    value = at.text_area[0].value
    assert value is not None
    assert len(value.split("\n")) == 10
    assert value.startswith("Food was delicious, but delivery took over an hour.")
    assert "Naan was stale and the curry was bland." in value
    assert "results" not in at.session_state
    assert not at.exception


def test_loaded_samples_can_be_analyzed(
    at: AppTest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub_post(monkeypatch, {"label": "positive", "score": 5, "theme": "delivery"})

    click(at, "Load sample reviews")
    click(at, "Analyze")

    assert len(at.session_state["results"]) == 10


def test_analyze_without_reviews_warns(at: AppTest) -> None:
    click(at, "Analyze")

    assert at.warning[0].value == "Please paste at least one review."
    assert "results" not in at.session_state


def test_analyze_shows_results_and_summary(
    at: AppTest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub_post(monkeypatch, {"label": "positive", "score": 5, "theme": "delivery"})

    analyze(at, "Fast delivery\n\n  Friendly staff  ")

    assert not at.exception
    assert at.session_state["results"] == [
        {"review": "Fast delivery", "label": "positive", "score": 5, "theme": "delivery"},
        {"review": "Friendly staff", "label": "positive", "score": 5, "theme": "delivery"},
    ]
    metrics = {metric.label: metric.value for metric in at.metric}
    assert metrics == {"Reviews": "2", "Average score": "5.0", "% Positive": "100%"}
    assert at.info[0].value == "Customers talk most about: **delivery**"


def test_analyze_marks_unreachable_api_as_error_rows(
    at: AppTest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing_post(url: str, json: dict[str, str], timeout: float) -> FakeResponse:
        raise requests.ConnectionError("API is down")

    monkeypatch.setattr(requests, "post", failing_post)

    analyze(at, "Cold soup")

    assert not at.exception
    assert at.session_state["results"] == [
        {"review": "Cold soup", "label": "error", "score": 0, "theme": "error"}
    ]
    assert [metric.label for metric in at.metric] == ["Reviews"]


def test_analyze_marks_api_rejections_as_error_rows(
    at: AppTest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def rejecting_post(url: str, json: dict[str, str], timeout: float) -> FakeResponse:
        return FakeResponse({"detail": "too long"}, status_code=422)

    monkeypatch.setattr(requests, "post", rejecting_post)

    analyze(at, "A very long review")

    assert at.session_state["results"][0]["label"] == "error"


def test_analyze_passes_a_timeout(
    at: AppTest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[Any] = []

    def recording_post(url: str, json: dict[str, str], timeout: float) -> FakeResponse:
        seen.append(timeout)
        return FakeResponse({"label": "neutral", "score": 3, "theme": "price"})

    monkeypatch.setattr(requests, "post", recording_post)

    analyze(at, "It was okay")

    assert seen == [60.0]


def test_save_persists_results_and_updates_history(
    at: AppTest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub_post(monkeypatch, {"label": "negative", "score": 1, "theme": "taste"})
    analyze(at, "Cold soup")

    click(at, "💾 Save to database")

    assert not at.exception
    assert database.load_history() == [("Cold soup", "negative", 1, "taste")]
    assert any("Total saved so far: 1" in block.value for block in at.markdown)

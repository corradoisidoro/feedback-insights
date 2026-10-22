"""Tests for the SQLite persistence layer."""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

import database


@pytest.fixture
def db_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "feedback.db"
    monkeypatch.setattr(database, "DB_FILE", str(path))
    return path


def test_init_db_creates_table(db_file: Path) -> None:
    database.init_db()

    with closing(sqlite3.connect(db_file)) as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'feedback'"
        ).fetchall()

    assert tables == [("feedback",)]


def test_init_db_is_idempotent(db_file: Path) -> None:
    database.init_db()
    database.init_db()

    assert db_file.exists()


def test_load_history_is_empty_before_any_save(db_file: Path) -> None:
    database.init_db()

    assert database.load_history() == []


def test_save_results_round_trips_rows(db_file: Path) -> None:
    database.init_db()
    rows: list[database.ResultRow] = [
        {"review": "Fast delivery", "label": "positive", "score": 5, "theme": "delivery"},
        {"review": "Cold soup", "label": "negative", "score": 1, "theme": "taste"},
    ]

    database.save_results(rows)

    assert database.load_history() == [
        ("Fast delivery", "positive", 5, "delivery"),
        ("Cold soup", "negative", 1, "taste"),
    ]


def test_save_results_accepts_empty_batch(db_file: Path) -> None:
    database.init_db()

    database.save_results([])

    assert database.load_history() == []


def test_save_results_appends_on_each_call(db_file: Path) -> None:
    database.init_db()
    row: database.ResultRow = {
        "review": "Nice staff",
        "label": "positive",
        "score": 4,
        "theme": "service",
    }

    database.save_results([row])
    database.save_results([row])

    assert len(database.load_history()) == 2

"""SQLite persistence for analyzed reviews."""

import os
import sqlite3
from collections.abc import Sequence
from contextlib import closing
from typing import TypedDict

DB_FILE = os.getenv("DB_FILE", "feedback.db")


class ResultRow(TypedDict):
    """One analyzed review, as displayed in the UI and stored in SQLite."""

    review: str
    label: str
    score: int
    theme: str


HistoryRow = tuple[str, str, int, str]


def init_db() -> None:
    """Create the feedback table the first time we run."""
    with closing(sqlite3.connect(DB_FILE)) as conn, conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY,
                review TEXT,
                label TEXT,
                score INTEGER,
                theme TEXT
            )
            """
        )


def save_results(results: Sequence[ResultRow]) -> None:
    """Write all analyzed reviews into the database in one transaction.

    Args:
        results: Rows shaped like ``{"review", "label", "score", "theme"}``.
    """
    with closing(sqlite3.connect(DB_FILE)) as conn, conn:
        conn.executemany(
            "INSERT INTO feedback (review, label, score, theme) VALUES (?, ?, ?, ?)",
            [(r["review"], r["label"], r["score"], r["theme"]) for r in results],
        )


def load_history() -> list[HistoryRow]:
    """Read every review saved so far.

    Returns:
        One ``(review, label, score, theme)`` tuple per stored row.
    """
    with closing(sqlite3.connect(DB_FILE)) as conn:
        rows = conn.execute("SELECT review, label, score, theme FROM feedback").fetchall()
    return [(row[0], row[1], row[2], row[3]) for row in rows]

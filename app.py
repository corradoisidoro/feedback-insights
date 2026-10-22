"""Streamlit UI: submit reviews, show a summary, and persist results to SQLite."""

import os
from collections import Counter

import requests
import streamlit as st
from dotenv import load_dotenv

from database import DB_FILE, HistoryRow, ResultRow, init_db, load_history, save_results

load_dotenv()

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000/analyze")
API_TIMEOUT_SECONDS = float(os.getenv("API_TIMEOUT_SECONDS", "60"))

SAMPLE_REVIEWS: tuple[str, ...] = (
    "Food was delicious, but delivery took over an hour. Not happy.",
    "Amazing taste, arrived hot and early. Will order again!",
    "Prices went up for the same small portion.",
    "Rude service when I called about my order.",
    "Biryani was perfect, exactly like last time.",
    "Okay food, nothing special.",
    "The delivery guy was polite and on time.",
    "Naan was stale and the curry was bland.",
    "Great value: big portion, very tasty.",
    "The app kept crashing while placing my order.",
)


def analyze_review(review: str) -> ResultRow:
    """Send one review to the API and shape the reply for the results table.

    Args:
        review: One line of customer feedback.

    Returns:
        A row with ``review``, ``label``, ``score`` and ``theme``. Any failure
        becomes an ``error`` row so one bad review cannot abort the batch.
    """
    try:
        response = requests.post(
            API_URL,
            json={"text": review},
            timeout=API_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        return {
            "review": review,
            "label": data["label"],
            "score": data["score"],
            "theme": data["theme"],
        }
    except Exception:
        # Boundary: network and API failures are expected here and are reported per review.
        return {"review": review, "label": "error", "score": 0, "theme": "error"}


init_db()

st.title("📝 Customer Feedback Analyzer")
st.write("Paste your customer reviews below, one review per line.")

if st.button("Load sample reviews"):
    st.session_state.reviews_text = "\n".join(SAMPLE_REVIEWS)

reviews_text = st.text_area("Reviews", height=200, key="reviews_text")

if st.button("Analyze"):
    reviews = [line.strip() for line in reviews_text.split("\n") if line.strip()]

    if not reviews:
        st.warning("Please paste at least one review.")
    else:
        st.session_state.results = [analyze_review(review) for review in reviews]

if "results" in st.session_state:
    results: list[ResultRow] = st.session_state.results

    st.subheader("Results")
    st.dataframe(results)

    scores = [r["score"] for r in results if r["label"] != "error"]
    positive = [r for r in results if r["label"] == "positive"]
    themes = [r["theme"] for r in results if r["theme"] != "error"]

    st.subheader("Summary")
    col1, col2, col3 = st.columns(3)
    col1.metric("Reviews", len(results))
    if scores:
        col2.metric("Average score", round(sum(scores) / len(scores), 1))
        col3.metric("% Positive", f"{round(len(positive) / len(results) * 100)}%")

    if themes:
        top_theme = Counter(themes).most_common(1)[0][0]
        st.info(f"Customers talk most about: **{top_theme}**")

    if st.button("💾 Save to database"):
        save_results(results)
        st.success(f"Saved {len(results)} reviews to {DB_FILE}")

with st.expander("📚 Saved history (all reviews in the database)"):
    history: list[HistoryRow] = load_history()
    if history:
        st.write(f"Total saved so far: {len(history)}")
        st.dataframe(
            [{"review": r[0], "label": r[1], "score": r[2], "theme": r[3]} for r in history]
        )
    else:
        st.write("Nothing saved yet. Analyze some reviews and click Save.")

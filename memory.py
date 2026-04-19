import nest_asyncio
nest_asyncio.apply()
import os
from typing import Optional
from hindsight_client import Hindsight

HINDSIGHT_URL = os.getenv("HINDSIGHT_URL", "http://localhost:8888")
HINDSIGHT_API_KEY = os.getenv("HINDSIGHT_API_KEY")
BANK_ID = os.getenv("HINDSIGHT_BANK_ID", "team-alpha")

_client: Optional[Hindsight] = None


def get_client() -> Hindsight:
    global _client
    if _client is None:
        kwargs = {"base_url": HINDSIGHT_URL}
        if HINDSIGHT_API_KEY:
            kwargs["api_key"] = HINDSIGHT_API_KEY
        _client = Hindsight(**kwargs)
    return _client


def create_bank(bank_id: str = BANK_ID) -> dict:
    client = get_client()
    return client.create_bank(
        bank_id=bank_id,
        name="Team Code Review Memory",
        reflect_mission="Track coding mistakes, feedback history, and team conventions.",
    )


def recall_context(code_snippet: str, developer: str) -> tuple:
    client = get_client()
    code_sample = code_snippet[:400].strip()
    try:
        team_results = client.recall(bank_id=BANK_ID, query=f"code review patterns for: {code_sample}")
        team_patterns = "\n".join(f"- {r.text}" for r in team_results.results) if team_results.results else "No patterns yet."
    except Exception as e:
        team_patterns = f"(recall failed: {e})"
    try:
        dev_results = client.recall(bank_id=BANK_ID, query=f"feedback history for developer: {developer}")
        dev_history = "\n".join(f"- {r.text}" for r in dev_results.results) if dev_results.results else f"No history for {developer}."
    except Exception as e:
        dev_history = f"(recall failed: {e})"
    return team_patterns, dev_history


def store_review(code, review, developer, language, issues_found, outcome="pending"):
    client = get_client()
    issues_str = "\n".join(f"  - {i}" for i in issues_found) if issues_found else "None"
    content = f"Code review session:\nDeveloper: {developer}\nLanguage: {language}\nIssues:\n{issues_str}\nReview: {review[:800]}\nOutcome: {outcome}"
    try:
        client.retain(bank_id=BANK_ID, content=content, context=f"Code review for {developer}")
    except Exception as e:
        print(f"Warning: failed to retain: {e}")


def update_outcome(developer, review_summary, outcome):
    client = get_client()
    try:
        client.retain(bank_id=BANK_ID, content=f"Developer {developer} marked feedback as '{outcome}': {review_summary[:300]}")
    except Exception as e:
        print(f"Warning: {e}")


def weekly_reflect() -> str:
    client = get_client()
    try:
        result = client.reflect(bank_id=BANK_ID, query="Summarize team code review patterns, recurring issues, and recommendations.")
        return result.text
    except Exception as e:
        return f"Reflect unavailable: {e}"


def get_memory_stats() -> dict:
    client = get_client()
    try:
        results = client.recall(bank_id=BANK_ID, query="code review developer")
        return {"bank_id": BANK_ID, "memories_sampled": len(results.results) if results.results else 0, "status": "connected"}
    except Exception as e:
        return {"bank_id": BANK_ID, "memories_sampled": 0, "status": f"error: {e}"}
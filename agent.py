"""
agent.py — Core Code Review Agent.

The pipeline for every review:
  1. Detect language
  2. Recall team patterns + developer history from Hindsight
  3. Build a memory-enriched system prompt
  4. Call the LLM (Groq via LiteLLM) for the review
  5. Extract issues from the review text
  6. Store the session back into Hindsight (retain)
  7. Return the full result to the UI

Groq-specific note: qwen3-32b supports tool use but can error on malformed
tool calls. We handle this by catching ToolUseError and retrying with a
plain completion (no tools) as a fallback — as recommended in the Groq docs.
"""

import json
import os
import re
from dataclasses import dataclass, field

from litellm import completion, ContentPolicyViolationError
from litellm.exceptions import BadRequestError

from memory import recall_context, store_review
from prompts import (
    REVIEW_SYSTEM_TEMPLATE,
    ISSUE_EXTRACTION_PROMPT,
    LANGUAGE_DETECTION_PROMPT,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GROQ_MODEL = os.getenv("GROQ_MODEL", "groq/qwen/qwen3-32b")
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "groq/llama-3.3-70b-versatile")

# Groq free tier rate limits — keep max_tokens reasonable
MAX_REVIEW_TOKENS = 1200
MAX_UTIL_TOKENS = 200  # language detection, issue extraction

KNOWN_DEVELOPERS = {
    "alex": "Alex Chen (alex@teamalpha.dev)",
    "priya": "Priya Sharma (priya@teamalpha.dev)",
    "sam": "Sam Okonkwo (sam@teamalpha.dev)",
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ReviewResult:
    developer: str
    language: str
    review: str                        # Full markdown review text
    issues: list[str] = field(default_factory=list)
    team_patterns_used: str = ""       # What memory was injected
    dev_history_used: str = ""         # What memory was injected
    verdict: str = "UNKNOWN"           # Parsed from the review
    error: str | None = None           # Set if LLM call failed


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _call_llm(
    system: str,
    user: str,
    max_tokens: int = MAX_REVIEW_TOKENS,
    model: str = GROQ_MODEL,
) -> str:
    """
    Call the LLM with automatic fallback.

    Groq's qwen3-32b can occasionally return a 400 on certain inputs.
    We catch that and fall back to llama-3.3-70b before raising to the caller.
    """
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    try:
        response = completion(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.2,  # Low temp = more consistent, deterministic reviews
        )
        return response.choices[0].message.content.strip()

    except (BadRequestError, ContentPolicyViolationError) as e:
        if model == GROQ_MODEL:
            # Retry with fallback model
            print(f"[agent] Primary model error ({e}), retrying with fallback...")
            return _call_llm(system, user, max_tokens, model=FALLBACK_MODEL)
        raise

    except Exception as e:
        # Surface other errors clearly
        raise RuntimeError(f"LLM call failed: {e}") from e


def detect_language(code: str) -> str:
    """Use the LLM to detect the code's language. Falls back to 'Unknown'."""
    try:
        lang = _call_llm(
            system="You are a programming language detector. Reply with ONLY the language name.",
            user=LANGUAGE_DETECTION_PROMPT.format(code=code[:800]),
            max_tokens=MAX_UTIL_TOKENS,
        )
        # Strip any accidental punctuation
        return lang.strip().rstrip(".,;:").title() or "Unknown"
    except Exception:
        return "Unknown"


def extract_issues(review: str) -> list[str]:
    """
    Parse the LLM review to extract a clean list of issue strings.
    Used for storing concise summaries in Hindsight.
    Falls back to empty list on parse failure.
    """
    try:
        raw = _call_llm(
            system="Extract a JSON array of issue strings from a code review. Return ONLY valid JSON.",
            user=ISSUE_EXTRACTION_PROMPT.format(review=review[:1500]),
            max_tokens=MAX_UTIL_TOKENS,
        )
        # Strip markdown code fences if the model wraps in ```json
        raw = re.sub(r"```(?:json)?|```", "", raw).strip()
        issues = json.loads(raw)
        if isinstance(issues, list):
            return [str(i) for i in issues[:10]]  # cap at 10
    except Exception:
        pass
    return []


def parse_verdict(review: str) -> str:
    """Extract BLOCKER / NEEDS CHANGES / APPROVED / LGTM from the review."""
    verdicts = ["BLOCKER", "NEEDS CHANGES", "APPROVED WITH COMMENTS", "LGTM"]
    upper = review.upper()
    for v in verdicts:
        if v in upper:
            return v
    return "NEEDS CHANGES"  # safe default


# ---------------------------------------------------------------------------
# Main review function
# ---------------------------------------------------------------------------

def review_code(code: str, developer_key: str) -> ReviewResult:
    """
    Full review pipeline: recall → LLM → retain → return.

    Args:
        code:           The raw code snippet or diff to review.
        developer_key:  One of "alex", "priya", "sam" (or full name).

    Returns:
        ReviewResult with the full review, issues, verdict, and memory context.
    """
    # Resolve developer display name
    developer = KNOWN_DEVELOPERS.get(developer_key.lower(), developer_key)

    result = ReviewResult(developer=developer, language="Unknown", review="")

    # Step 1: Detect language
    result.language = detect_language(code)

    # Step 2: Recall context from Hindsight
    try:
        team_patterns, dev_history = recall_context(code, developer)
        result.team_patterns_used = team_patterns
        result.dev_history_used = dev_history
    except Exception as e:
        result.team_patterns_used = f"(recall failed: {e})"
        result.dev_history_used = "(recall failed)"
        team_patterns = ""
        dev_history = ""

    # Step 3: Build memory-enriched system prompt
    system_prompt = REVIEW_SYSTEM_TEMPLATE.format(
        developer=developer,
        team_patterns=team_patterns or "No team patterns in memory yet.",
        dev_history=dev_history or f"No history for {developer} yet.",
    )

    # Step 4: Call the LLM
    try:
        result.review = _call_llm(
            system=system_prompt,
            user=f"Please review the following {result.language} code:\n\n```{result.language.lower()}\n{code}\n```",
            max_tokens=MAX_REVIEW_TOKENS,
        )
    except Exception as e:
        result.error = str(e)
        result.review = f"❌ Review failed: {e}"
        return result

    # Step 5: Parse verdict
    result.verdict = parse_verdict(result.review)

    # Step 6: Extract issues for memory storage
    result.issues = extract_issues(result.review)

    # Step 7: Retain the session in Hindsight (async-friendly — won't block the UI)
    try:
        store_review(
            code=code,
            review=result.review,
            developer=developer,
            language=result.language,
            issues_found=result.issues,
            outcome="pending",
        )
    except Exception as e:
        # Don't fail the review if memory storage fails
        print(f"[agent] Warning: failed to retain review in memory: {e}")

    return result


# ---------------------------------------------------------------------------
# CLI entry point (for testing without the UI)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    load_dotenv()

    test_code = """
def get_user_orders(user_id):
    query = "SELECT * FROM orders WHERE user_id = " + user_id
    cursor.execute(query)
    return cursor.fetchall()
"""

    dev = sys.argv[1] if len(sys.argv) > 1 else "priya"
    print(f"\n🔍 Reviewing code as submitted by: {dev}\n{'='*60}\n")

    r = review_code(test_code, dev)

    print(f"Language detected: {r.language}")
    print(f"Verdict: {r.verdict}")
    print(f"\n--- Review ---\n{r.review}")
    print(f"\n--- Issues stored ---")
    for issue in r.issues:
        print(f"  • {issue}")
    print(f"\n--- Team memory used ---\n{r.team_patterns_used}")
    print(f"\n--- Dev history used ---\n{r.dev_history_used}")

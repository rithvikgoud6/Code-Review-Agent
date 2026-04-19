"""
seed_memory.py — Pre-populate Hindsight with 2 weeks of fake team history.

Run this ONCE before your demo. This is what makes the agent feel like
it actually knows the team. The "4th SQL injection for Priya" moment
only works because we've seeded those 3 previous incidents here.

Usage:
    python seed_memory.py
    python seed_memory.py --reset   # wipe and re-seed (useful during dev)
"""

import argparse
import time
from dotenv import load_dotenv

load_dotenv()

from memory import create_bank, get_client, BANK_ID

# ---------------------------------------------------------------------------
# Seed data — realistic 2-week review history for 3 developers
# ---------------------------------------------------------------------------

SEED_MEMORIES = [
    # ── Team conventions ──────────────────────────────────────────────────
    "Team Alpha coding standards: use snake_case for Python identifiers, "
    "camelCase for JavaScript/TypeScript. No exceptions.",

    "Team Alpha standard: all database queries MUST use parameterized statements "
    "or an ORM query builder. Raw string concatenation in SQL is a zero-tolerance violation.",

    "Team Alpha standard: all public API endpoints must implement rate limiting "
    "using the shared RateLimiter middleware. Non-negotiable.",

    "Team Alpha standard: do NOT add type hints to legacy modules (anything in /legacy/*). "
    "They pre-date our type system and adding hints breaks the CI mypy config.",

    "Team Alpha uses pytest with fixtures for all new test files. unittest.TestCase "
    "is only acceptable in legacy modules being patched.",

    "Team Alpha architecture preference: business logic lives in service layer (/services/*), "
    "never directly in route handlers or models.",

    # ── Priya Sharma — recurring SQL injection issues ──────────────────────
    "PR #134 — Developer Priya Sharma (priya@teamalpha.dev): Flagged SQL injection vulnerability. "
    "Query built using f-string: f\"SELECT * FROM users WHERE id = {user_id}\". "
    "Feedback: use cursor.execute(query, (user_id,)) with parameterization. "
    "Outcome: accepted, fixed before merge.",

    "PR #138 — Developer Priya Sharma: SQL injection found again in payment_service.py. "
    "Different function but same pattern — string concatenation in raw SQL. "
    "Second occurrence flagged. Priority elevated to NEEDS CHANGES. "
    "Outcome: accepted after 2 days.",

    "PR #141 — Developer Priya Sharma: Third SQL injection instance, this time in "
    "the reporting module. Feedback escalated to BLOCKER. Team lead notified. "
    "Priya acknowledged in review: 'Will set up a linter rule.' Outcome: fixed.",

    "Developer Priya Sharma has been reminded about parameterized SQL queries 3 times "
    "this month (PRs #134, #138, #141). Pattern confirmed. "
    "Next occurrence should be escalated as a recurring critical issue.",

    # ── Priya Sharma — other feedback history ────────────────────────────
    "PR #129 — Priya Sharma: Missing error handling on external API call in "
    "notifications/sender.py. Silent failure on network timeout. Fixed after review.",

    "PR #136 — Priya Sharma: Hardcoded API key found in config.py "
    "(STRIPE_KEY = 'sk_live_...'). Immediate blocker. Rotated key, moved to env var.",

    "Priya Sharma consistently writes thorough docstrings and good commit messages. "
    "Code structure and naming are generally clean outside the SQL issues.",

    # ── Alex Chen — feedback history ──────────────────────────────────────
    "Developer Alex Chen (alex@teamalpha.dev) code style preferences: "
    "prefers explicit variable names over clever one-liners. "
    "Dislikes list comprehensions that span more than one logical operation.",

    "PR #132 — Alex Chen: Suggested extracting a deeply nested if-block "
    "into a guard clause. Alex marked feedback as 'dismissed — style preference'. "
    "Do not repeat this suggestion for Alex.",

    "PR #137 — Alex Chen: Missing rate limiting on /api/export endpoint. "
    "Blocker — fixed same day. Alex is generally responsive to security feedback.",

    "PR #143 — Alex Chen: Excellent PR. Clean service/handler separation, "
    "full test coverage, good error handling. Approved with one minor suggestion "
    "(variable rename). LGTM overall.",

    "Alex Chen writes consistently well-structured code. Main watch area: "
    "occasionally skips integration tests when under deadline pressure.",

    # ── Sam Okonkwo — feedback history ────────────────────────────────────
    "Developer Sam Okonkwo (sam@teamalpha.dev) is the team's strongest engineer. "
    "PRs are consistently clean, well-tested, and well-documented. "
    "Often used as a reference reviewer for junior developers.",

    "PR #131 — Sam Okonkwo: One suggestion — add explicit timeout to requests.get() call. "
    "Sam accepted immediately and added a team-wide constant DEFAULT_TIMEOUT. "
    "Outcome: improved pattern now used across the codebase.",

    "PR #139 — Sam Okonkwo: LGTM with no changes. Full test suite, proper error handling, "
    "rate limiting in place, clean SQL via ORM. Model PR.",

    "PR #144 — Sam Okonkwo: Added proper circuit breaker pattern to the payment gateway "
    "integration. Proactively addressed resilience without being asked. Excellent.",

    # ── Security patterns ─────────────────────────────────────────────────
    "Security pattern: SQL injection has appeared in 3 of the last 8 PRs. "
    "All 3 from the same developer (Priya Sharma). "
    "Recommend team-wide linter rule: sqlfluff or bandit B608 check.",

    "Security pattern: One hardcoded credential found this month (Priya, PR #136). "
    "Recommend pre-commit hook with detect-secrets.",

    # ── Architecture observations ─────────────────────────────────────────
    "Architecture observation: business logic is occasionally leaking into route handlers "
    "(seen in PRs #133, #135). Reminder: all logic above DB layer goes in /services/*.",

    "Performance note: N+1 query pattern found in PR #140 (Alex). "
    "Fixed by adding select_related(). Keep an eye on ORM usage in list endpoints.",
]


def seed(reset: bool = False) -> None:
    client = get_client()

    if reset:
        print(f"⚠️  Reset requested. Deleting bank '{BANK_ID}'...")
        try:
            client.delete_bank(bank_id=BANK_ID)
            print("   Bank deleted.")
        except Exception as e:
            print(f"   Could not delete bank (may not exist yet): {e}")
        time.sleep(1)

    print(f"🏗️  Creating memory bank '{BANK_ID}'...")
    create_bank(BANK_ID)
    print("   Bank ready.\n")

    print(f"📥  Seeding {len(SEED_MEMORIES)} memories...\n")
    for i, memory in enumerate(SEED_MEMORIES, 1):
        # Determine context tag for this memory
        if "Priya" in memory:
            context = "Developer history: Priya Sharma"
        elif "Alex" in memory:
            context = "Developer history: Alex Chen"
        elif "Sam" in memory:
            context = "Developer history: Sam Okonkwo"
        elif "Team Alpha" in memory or "standard" in memory.lower():
            context = "Team conventions and standards"
        elif "Security" in memory or "SQL injection" in memory:
            context = "Security patterns"
        elif "Architecture" in memory or "Performance" in memory:
            context = "Architecture observations"
        else:
            context = "Team memory"

        try:
            client.retain(bank_id=BANK_ID, content=memory, context=context)
            print(f"   [{i:02d}/{len(SEED_MEMORIES)}] ✓  {memory[:72]}...")
        except Exception as e:
            print(f"   [{i:02d}/{len(SEED_MEMORIES)}] ✗  Failed: {e}")

        # Small delay to avoid overwhelming the API on Hindsight Cloud
        time.sleep(0.3)

    print(f"\n✅  Seeding complete. {len(SEED_MEMORIES)} memories loaded into '{BANK_ID}'.")
    print("\n💡  The agent now knows:")
    print("     • Priya has 3 prior SQL injection incidents (PRs #134, #138, #141)")
    print("     • Alex dismissed the guard-clause suggestion — don't repeat it")
    print("     • Sam is the strongest reviewer on the team")
    print("     • Team bans raw SQL string concatenation, requires rate limiting")
    print("\n🚀  You're ready to demo. Run: streamlit run app.py\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Hindsight with fake team history")
    parser.add_argument("--reset", action="store_true", help="Delete and re-create the bank first")
    args = parser.parse_args()
    seed(reset=args.reset)

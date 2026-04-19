"""
app.py — Streamlit UI for the Code Review Agent.

Run with: streamlit run app.py
"""

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from agent import review_code, KNOWN_DEVELOPERS
from memory import update_outcome, weekly_reflect, get_memory_stats

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="CodeMind — AI Code Review",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS — sharp industrial terminal aesthetic
# ---------------------------------------------------------------------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
    background-color: #0d0d0f;
    color: #e2e2e2;
}

/* Main background */
.stApp { background-color: #0d0d0f; }
section[data-testid="stSidebar"] { background-color: #111115; border-right: 1px solid #2a2a35; }

/* Headers */
h1, h2, h3 { font-family: 'IBM Plex Mono', monospace !important; }

/* Metric cards */
[data-testid="stMetric"] {
    background: #16161c;
    border: 1px solid #2a2a35;
    border-radius: 4px;
    padding: 12px 16px;
}

/* Buttons */
.stButton > button {
    background: #1a1a22;
    color: #e2e2e2;
    border: 1px solid #3a3a4a;
    border-radius: 3px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 13px;
    letter-spacing: 0.02em;
    transition: all 0.15s;
}
.stButton > button:hover {
    background: #22222e;
    border-color: #6366f1;
    color: #a5b4fc;
}

/* Primary button */
.stButton > button[kind="primary"] {
    background: #4f46e5;
    border-color: #4f46e5;
    color: white;
    font-weight: 500;
}
.stButton > button[kind="primary"]:hover {
    background: #4338ca;
    border-color: #4338ca;
}

/* Text area */
.stTextArea textarea {
    background: #111115 !important;
    border: 1px solid #2a2a35 !important;
    border-radius: 4px !important;
    color: #e2e2e2 !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 13px !important;
}
.stTextArea textarea:focus {
    border-color: #6366f1 !important;
    box-shadow: 0 0 0 1px #6366f1 !important;
}

/* Select box */
.stSelectbox > div > div {
    background: #111115 !important;
    border: 1px solid #2a2a35 !important;
    color: #e2e2e2 !important;
    border-radius: 4px !important;
}

/* Expanders */
.streamlit-expanderHeader {
    background: #16161c !important;
    border: 1px solid #2a2a35 !important;
    border-radius: 4px !important;
    color: #a0a0b0 !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 12px !important;
}

/* Code blocks */
code, pre {
    font-family: 'IBM Plex Mono', monospace !important;
    background: #111115 !important;
    border: 1px solid #2a2a35 !important;
    border-radius: 3px !important;
}

/* Divider */
hr { border-color: #2a2a35; }

/* Spinner */
.stSpinner > div { border-top-color: #6366f1 !important; }

/* Success / warning / error */
.stSuccess { background: #0d1f0f !important; border-color: #16a34a !important; }
.stWarning { background: #1c1500 !important; border-color: #ca8a04 !important; }
.stError   { background: #1c0808 !important; border-color: #dc2626 !important; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

if "review_result" not in st.session_state:
    st.session_state.review_result = None
if "outcome_recorded" not in st.session_state:
    st.session_state.outcome_recorded = False

# ---------------------------------------------------------------------------
# Demo code snippets — pre-loaded for the hackathon demo
# ---------------------------------------------------------------------------

DEMO_SNIPPETS = {
    "Select a demo snippet…": "",
    "🔴 SQL injection (Priya's 4th time)": """\
def get_user_orders(user_id):
    query = "SELECT * FROM orders WHERE user_id = " + user_id
    cursor.execute(query)
    return cursor.fetchall()
""",
    "🟡 Missing rate limiting (API endpoint)": """\
@app.route('/api/export', methods=['GET'])
def export_data():
    user_id = request.args.get('user_id')
    data = db.session.query(Order).filter_by(user_id=user_id).all()
    return jsonify([o.to_dict() for o in data])
""",
    "🟡 N+1 query pattern": """\
def get_team_with_members(team_id):
    team = Team.objects.get(id=team_id)
    result = {"team": team.name, "members": []}
    for member_id in team.member_ids:
        member = User.objects.get(id=member_id)  # N+1!
        result["members"].append(member.name)
    return result
""",
    "🟢 Clean code (Sam-style)": """\
DEFAULT_TIMEOUT = 10  # seconds

def fetch_payment_status(order_id: str) -> dict:
    \"\"\"
    Fetch payment status from the payments service.
    Returns the status dict or raises PaymentServiceError on failure.
    \"\"\"
    try:
        response = requests.get(
            f"{PAYMENTS_BASE_URL}/status/{order_id}",
            timeout=DEFAULT_TIMEOUT,
            headers={"Authorization": f"Bearer {settings.PAYMENTS_API_KEY}"},
        )
        response.raise_for_status()
        return response.json()
    except requests.Timeout:
        raise PaymentServiceError(f"Timeout fetching status for order {order_id}")
    except requests.HTTPError as e:
        raise PaymentServiceError(f"HTTP error: {e.response.status_code}") from e
""",
}

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("## ⬡ CodeMind")
    st.markdown(
        "<span style='font-size:11px;color:#666;font-family:IBM Plex Mono'>v0.1 · Hindsight-powered</span>",
        unsafe_allow_html=True,
    )
    st.divider()

    # Memory bank stats
    st.markdown("### Memory Bank")
    stats = get_memory_stats()
    status_color = "#16a34a" if stats["status"] == "connected" else "#dc2626"
    st.markdown(
        f"<span style='color:{status_color};font-family:IBM Plex Mono;font-size:12px'>"
        f"● {stats['status'].upper()}</span>  "
        f"<span style='color:#666;font-size:12px'>{stats['bank_id']}</span>",
        unsafe_allow_html=True,
    )
    st.metric("Memories recalled", stats["memories_sampled"], label_visibility="visible")

    st.divider()

    # Weekly reflect
    st.markdown("### Team Health Report")
    st.markdown(
        "<span style='font-size:12px;color:#666'>Uses Hindsight reflect — synthesizes all reviews into team insights.</span>",
        unsafe_allow_html=True,
    )
    if st.button("⟳ Generate weekly report", use_container_width=True):
        with st.spinner("Reflecting on all reviews..."):
            report = weekly_reflect()
        st.session_state.weekly_report = report

    if "weekly_report" in st.session_state:
        st.markdown(
            f"""<div style='background:#111115;border:1px solid #2a2a35;border-radius:4px;
            padding:12px;font-size:12px;color:#c0c0d0;line-height:1.7;margin-top:8px;
            font-family:IBM Plex Mono'>
            {st.session_state.weekly_report.replace(chr(10), '<br>')}
            </div>""",
            unsafe_allow_html=True,
        )

    st.divider()
    st.markdown(
        "<span style='font-size:11px;color:#444'>Powered by Hindsight · Groq · LiteLLM</span>",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Main layout
# ---------------------------------------------------------------------------

col_header, col_badge = st.columns([3, 1])
with col_header:
    st.markdown("# Code Review Agent")
    st.markdown(
        "<span style='color:#666;font-size:14px;font-family:IBM Plex Mono'>"
        "Memory-powered reviews that know your team's history</span>",
        unsafe_allow_html=True,
    )
with col_badge:
    st.markdown("<br>", unsafe_allow_html=True)

st.divider()

left, right = st.columns([1, 1], gap="large")

# ---------------------------------------------------------------------------
# Left column: inputs
# ---------------------------------------------------------------------------

with left:
    st.markdown("### Submit Code")

    # Developer selector
    dev_options = list(KNOWN_DEVELOPERS.keys())
    dev_display = {k: v.split(" (")[0] for k, v in KNOWN_DEVELOPERS.items()}
    selected_dev_key = st.selectbox(
        "Developer",
        options=dev_options,
        format_func=lambda k: f"{dev_display[k]}  ·  {KNOWN_DEVELOPERS[k].split('(')[1].rstrip(')')}",
    )

    # Demo snippet loader
    selected_snippet = st.selectbox("Load demo snippet", options=list(DEMO_SNIPPETS.keys()))
    if selected_snippet != "Select a demo snippet…" and DEMO_SNIPPETS[selected_snippet]:
        default_code = DEMO_SNIPPETS[selected_snippet]
    else:
        default_code = st.session_state.get("last_code", "")

    # Code input
    code_input = st.text_area(
        "Code to review",
        value=default_code,
        height=280,
        placeholder="Paste your code here…",
    )

    run_review = st.button("▶  Run review", type="primary", use_container_width=True)

    # What memory will be used
    if code_input.strip():
        with st.expander("Preview memory context", expanded=False):
            from memory import recall_context
            with st.spinner("Recalling…"):
                try:
                    patterns, history = recall_context(code_input, KNOWN_DEVELOPERS[selected_dev_key])
                    st.markdown("**Team patterns recalled:**")
                    st.markdown(
                        f"<pre style='font-size:11px;color:#a0a0c0'>{patterns}</pre>",
                        unsafe_allow_html=True,
                    )
                    st.markdown(f"**{dev_display[selected_dev_key]}'s history:**")
                    st.markdown(
                        f"<pre style='font-size:11px;color:#a0a0c0'>{history}</pre>",
                        unsafe_allow_html=True,
                    )
                except Exception as e:
                    st.error(f"Memory recall failed: {e}")

# ---------------------------------------------------------------------------
# Right column: review output
# ---------------------------------------------------------------------------

with right:
    st.markdown("### Review Output")

    if run_review and code_input.strip():
        st.session_state.outcome_recorded = False
        st.session_state.last_code = code_input

        with st.spinner(f"Reviewing {dev_display[selected_dev_key]}'s code…"):
            result = review_code(code_input, selected_dev_key)
            st.session_state.review_result = result

    r = st.session_state.review_result

    if r is None:
        st.markdown(
            """<div style='background:#111115;border:1px dashed #2a2a35;border-radius:4px;
            padding:32px;text-align:center;color:#444;font-family:IBM Plex Mono;font-size:13px'>
            Submit code on the left to see a review here.
            </div>""",
            unsafe_allow_html=True,
        )
    elif r.error:
        st.error(f"Review failed: {r.error}")
    else:
        # Verdict badge
        verdict_colors = {
            "BLOCKER": ("#dc2626", "#1c0808"),
            "NEEDS CHANGES": ("#ca8a04", "#1c1500"),
            "APPROVED WITH COMMENTS": ("#2563eb", "#0a1628"),
            "LGTM": ("#16a34a", "#0d1f0f"),
        }
        vc, vbg = verdict_colors.get(r.verdict, ("#666", "#16161c"))
        st.markdown(
            f"""<div style='background:{vbg};border:1px solid {vc};border-radius:4px;
            padding:10px 16px;display:flex;align-items:center;gap:12px;margin-bottom:16px'>
            <span style='color:{vc};font-family:IBM Plex Mono;font-weight:600;font-size:13px'>
            {r.verdict}</span>
            <span style='color:#666;font-size:12px;font-family:IBM Plex Mono'>
            {r.language} · {r.developer.split(" (")[0]}</span>
            </div>""",
            unsafe_allow_html=True,
        )

        # Review markdown
        st.markdown(r.review)

        st.divider()

        # Issues stored
        if r.issues:
            st.markdown("**Issues stored to memory:**")
            for issue in r.issues:
                st.markdown(
                    f"<span style='font-family:IBM Plex Mono;font-size:12px;color:#a0a0c0'>· {issue}</span>",
                    unsafe_allow_html=True,
                )

        # Memory context used
        with st.expander("Memory context used in this review", expanded=False):
            st.markdown("**Team patterns:**")
            st.markdown(
                f"<pre style='font-size:11px;color:#888'>{r.team_patterns_used}</pre>",
                unsafe_allow_html=True,
            )
            st.markdown(f"**{r.developer.split(' (')[0]}'s history:**")
            st.markdown(
                f"<pre style='font-size:11px;color:#888'>{r.dev_history_used}</pre>",
                unsafe_allow_html=True,
            )

        st.divider()

        # Outcome buttons
        if not st.session_state.outcome_recorded:
            st.markdown(
                "<span style='font-size:12px;color:#666;font-family:IBM Plex Mono'>"
                "Mark developer's response to this review:</span>",
                unsafe_allow_html=True,
            )
            ocol1, ocol2, ocol3 = st.columns(3)
            with ocol1:
                if st.button("✓ Accepted", use_container_width=True):
                    update_outcome(r.developer, r.review[:300], "accepted")
                    st.session_state.outcome_recorded = True
                    st.rerun()
            with ocol2:
                if st.button("✗ Dismissed", use_container_width=True):
                    update_outcome(r.developer, r.review[:300], "dismissed")
                    st.session_state.outcome_recorded = True
                    st.rerun()
            with ocol3:
                if st.button("⧖ Pending", use_container_width=True):
                    st.session_state.outcome_recorded = True
                    st.rerun()
        else:
            st.success("Outcome recorded to memory.")

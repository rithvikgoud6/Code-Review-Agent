# CodeMind — AI Code Review Agent

A memory-powered code review agent built with [Hindsight](https://hindsight.vectorize.io)
and [Groq](https://groq.com). Instead of generic advice, it knows your team's history:
recurring issues, dismissed feedback, and each developer's track record.

---

## Quick start

### 1. Clone and install

```bash
git clone https://github.com/your-username/code-review-agent
cd code-review-agent
pip install -r requirements.txt
```

### 2. Set up environment

```bash
cp .env.example .env
# Edit .env with your Groq API key and Hindsight credentials
```

Get your keys:
- **Groq**: [console.groq.com](https://console.groq.com) (free tier)
- **Hindsight Cloud**: [ui.hindsight.vectorize.io](https://ui.hindsight.vectorize.io)
  — use promo code **MEMHACK409** for $50 free credits

Or run Hindsight locally (no account needed):
```bash
docker run --rm -p 8888:8888 -p 9999:9999 \
  -e HINDSIGHT_API_LLM_API_KEY=$OPENAI_API_KEY \
  ghcr.io/vectorize-io/hindsight:latest
# Then set HINDSIGHT_URL=http://localhost:8888 in .env
```

### 3. Seed team memory (critical — do this first)

```bash
python seed_memory.py
```

This loads 2 weeks of fake team history so the agent knows the developers.
The "4th SQL injection for Priya" demo moment requires this seeded data.

To reset and re-seed:
```bash
python seed_memory.py --reset
```

### 4. Run the app

```bash
streamlit run app.py
```

### 5. Test from the terminal (no UI)

```bash
python agent.py priya     # Review with Priya's history
python agent.py alex      # Review with Alex's history
python agent.py sam       # Review with Sam's history
```

---

## How Hindsight is used

| Operation | When | What's stored |
|-----------|------|---------------|
| `retain`  | After every review | Code reviewed, issues found, developer, outcome |
| `recall`  | Before every review | Team patterns + developer history injected into prompt |
| `reflect` | Weekly report | Synthesizes all reviews into team health insights |

The agent uses three separate recall queries per review:
1. **Team patterns** — conventions, security rules, architectural standards
2. **Developer history** — past feedback, dismissed suggestions, known strengths

---

## Project structure

```
code-review-agent/
├── app.py           # Streamlit UI
├── agent.py         # Core review pipeline (recall → LLM → retain)
├── memory.py        # Hindsight client wrapper
├── seed_memory.py   # One-time demo data loader
├── prompts.py       # Prompt templates
├── requirements.txt
└── .env.example
```

---

## Demo script

1. Open the app: `streamlit run app.py`
2. Select developer: **Priya Sharma**
3. Load snippet: **SQL injection (Priya's 4th time)**
4. Click **Run review**
5. Watch the agent reference PRs #134, #138, #141 and escalate to BLOCKER
6. Click **Generate weekly report** in the sidebar
7. Show Hindsight UI at `localhost:9999` (if running locally)

---

Built for the CascadeFlow × Hindsight Hackathon.
Memory powered by [Hindsight](https://hindsight.vectorize.io).
LLM by [Groq](https://groq.com).

# InsightFlow

A data-to-decision analytics platform that transforms raw operational data into explainable insights, trend narratives, and decision-ready summaries instead of raw dashboards.

## What it does

InsightFlow closes the "interpretation gap" between raw metrics and business decisions:
- Detects meaningful behavioral changes (not just threshold alerts)
- Identifies which segments contributed to the change
- Generates human-readable narratives with evidence
- **Conversational chat agent** — ask questions in natural language ("why did ticket time go up?"), grounded in the actual metric data via tool calls
- Presents insights as a feed of decisions + a chat panel, not a wall of charts

## Architecture

```
Data Sources → Ingestion → Modeling → Analysis Engine → Insight Generator → UI Feed
```

- **Backend**: Python + FastAPI
- **Storage**: PostgreSQL (transactional), DuckDB (analytical)
- **Analysis**: Pandas, NumPy, SciPy (rolling means, z-score, contribution analysis)
- **Narratives**: Jinja2 templates (rule-based) for the feed
- **Chat agent**: Ollama (local Llama 3.1) with tool calling for Q&A
- **Agent tools**: `list_metrics`, `get_metric_overview`, `explain_change`, `list_recent_insights`, `compare_segments`
- **Frontend**: Next.js + React + TypeScript + Tailwind + TanStack Query
- **Infra**: Docker Compose

## Quick start

### 0. Install + start Ollama (for the chat agent)
```bash
brew install ollama          # macOS; or curl https://ollama.com/install.sh | sh
ollama serve                 # leave running in a separate terminal
ollama pull llama3.1:8b      # ~5 GB
```

### 1. Start Postgres
```bash
docker compose up -d postgres
```

### 2. Backend
```bash
cd backend
cp ../.env.example .env            # then adjust if your Postgres differs
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/init_db.py          # create tables
python scripts/seed_data.py        # generate 90 days of synthetic data
python scripts/run_analysis.py     # detect trends, segments, write insights
uvicorn app.main:app --reload
```

API will be on http://localhost:8000 — try `/docs` for the Swagger UI. Routes are
grouped under `/metrics`, `/insights` and `/chat`.

Set `OLLAMA_ENABLED=false` to skip the model entirely; narratives then come purely
from the Jinja templates and the chat endpoint is the only feature that degrades.

### 3. Frontend
```bash
cd frontend
npm install
npm run dev
```

UI on http://localhost:3000.

## Data model

- `metrics(id, name, owner, schema)` — metric definitions
- `metric_values(metric_id, ts, value, dimensions)` — time-series facts
- `metric_changes(metric_id, window, delta, significance)` — detected changes
- `segments(metric_id, dimension, contribution)` — drill-down attribution
- `insights(id, metric_id, summary, evidence_json, created_at)` — final narratives

## Repo layout

```
insightflow/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI entry
│   │   ├── db.py            # SQLAlchemy + DuckDB connections
│   │   ├── models.py        # ORM models
│   │   ├── schemas.py       # Pydantic request/response
│   │   ├── routers/         # /metrics, /insights, /chat endpoints
│   │   ├── agent/
│   │   │   ├── tools.py       # tool implementations the model may call
│   │   │   └── runner.py      # tool-calling loop against Ollama
│   │   └── analysis/
│   │       ├── trends.py      # z-score, rolling stats
│   │       ├── segments.py    # contribution analysis
│   │       └── narratives.py  # Jinja templates + (optional) Ollama
│   ├── tests/               # analysis engine tests
│   └── scripts/             # init_db, seed_data, run_analysis
└── frontend/
    ├── app/                 # Next.js app router
    ├── components/          # InsightCard, InsightFeed
    └── lib/api.ts           # fetch client
```

## Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

87 cases over the analysis engine and the agent tools — the layers where a silent
error would corrupt every insight downstream:

- **Trends** — spike, drop, plateau and volatility classification, the thresholds that
  must *not* fire, significance scaling, and the zero-variance baseline case where
  significance saturates.
- **Segments** — contribution ranking by magnitude, shares summing to one, segments
  missing from the baseline, and that the caller's DataFrame is never mutated.
- **Narratives** — headline and summary wording per pattern, segment attribution, and
  the severity matrix including how metric direction decides what counts as bad.

- **Agent tools** — fuzzy metric lookup including the synonym fallback, metric
  overviews, change explanation with and without dimensions, insight filtering and
  ordering, and that every registered tool has a matching JSON schema.

The narrative tests pin `ollama_enabled` off, so they stay deterministic and never
reach for a model server. Agent-tool tests run against in-memory SQLite through the
real ORM rather than a hand-written fake session, so the queries themselves are
exercised.

## Roadmap

- [ ] dbt Core integration (replace inline transforms)
- [ ] Live ingestion endpoint (webhooks)
- [ ] Suppression / snooze on noisy metrics
- [ ] Feedback loop ("was this insight useful?")

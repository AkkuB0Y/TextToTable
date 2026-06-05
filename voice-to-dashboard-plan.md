# Voice-to-Dashboard: Full Build Plan

> Paste this into Claude Code at the start of each phase. Work phase by phase — get each one working and tested before moving on.

---

## What we're building

A web app where a user speaks a question ("show me revenue by region for last quarter"), and within ~5–8 seconds a clean dashboard appears with the right chart type, a plain-English summary, and the underlying data. Built to be demo-able, extendable into a SaaS product.

---

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Frontend | React + Vite + TypeScript | Fast dev, good Recharts support |
| Styling | Tailwind CSS | Quick, consistent |
| Charts | Recharts | Composable, easy to switch chart types |
| Audio capture | Browser MediaRecorder API | No deps, works everywhere |
| Backend | Python 3.11 + FastAPI | Async, easy to reason about |
| STT | OpenAI Whisper (local `whisper` package, `base` model) | Free, runs locally, good accuracy |
| LLM | Anthropic Claude (`claude-sonnet-4-20250514`) | Tool use, structured output |
| Database | SQLite for dev, Postgres-ready | Zero setup to start |
| Streaming | Server-Sent Events (SSE) | Simple progress without websockets |

---

## Project structure

```
voice-dashboard/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── AudioRecorder.tsx     # Mic button, waveform, recording state
│   │   │   ├── ProgressStepper.tsx   # Shows pipeline stages live
│   │   │   ├── DashboardRenderer.tsx # Picks chart type, renders result
│   │   │   ├── ChartSwitcher.tsx     # Bar / Line / Pie / Table / KPI
│   │   │   └── QueryHistory.tsx      # Sidebar of past queries
│   │   ├── hooks/
│   │   │   ├── useAudioRecorder.ts   # MediaRecorder logic
│   │   │   └── useQueryStream.ts     # SSE consumer
│   │   ├── types/
│   │   │   └── index.ts              # QueryResult, VizSpec, PipelineEvent
│   │   └── App.tsx
│   ├── package.json
│   └── vite.config.ts
│
├── backend/
│   ├── main.py                       # FastAPI app, routes
│   ├── pipeline/
│   │   ├── transcriber.py            # Whisper wrapper
│   │   ├── normalizer.py             # Text cleaning
│   │   ├── agent.py                  # Claude query planner + SQL gen
│   │   ├── executor.py               # Safe SQL execution
│   │   └── viz_selector.py           # Result shape → chart type
│   ├── db/
│   │   ├── schema.sql                # Sample schema
│   │   └── seed.py                   # Sample data (sales, orders, etc.)
│   ├── models.py                     # Pydantic models
│   └── requirements.txt
│
└── README.md
```

---

## Data models (share between frontend and backend)

```typescript
// frontend/src/types/index.ts

type PipelineStage =
  | "recording"
  | "transcribing"
  | "planning"
  | "querying"
  | "rendering";

interface PipelineEvent {
  stage: PipelineStage;
  status: "active" | "done" | "error";
  detail?: string; // e.g. the transcript text, or the SQL
}

type VizType = "bar" | "line" | "pie" | "area" | "kpi" | "table";

interface VizSpec {
  type: VizType;
  x_key?: string;
  y_keys: string[];
  title: string;
  summary: string; // plain-English sentence
}

interface QueryResult {
  rows: Record<string, unknown>[];
  columns: string[];
  viz_spec: VizSpec;
  sql: string;
  transcript: string;
}
```

---

## Phase 1 — Backend skeleton + database

**Goal:** FastAPI server running, sample DB seeded, health check passing.

**Tasks for Claude Code:**

1. Create `backend/requirements.txt`:
   ```
   fastapi
   uvicorn[standard]
   anthropic
   openai-whisper
   python-multipart
   pydantic
   aiofiles
   ```

2. Create `backend/db/schema.sql` with a realistic sample schema:
   - `orders(id, customer_id, product_id, amount, created_at, status, region)`
   - `customers(id, name, plan_type, signup_date, churned_at)`
   - `products(id, name, category, price)`

3. Create `backend/db/seed.py` — generate 2 years of realistic fake data (use Python's `random` + `faker` or hand-crafted). At least 10,000 order rows so aggregations are interesting.

4. Create `backend/main.py` with:
   - `GET /health` → `{"status": "ok"}`
   - `POST /query` stub that returns a hardcoded `QueryResult`

5. Write a test: `python -m pytest backend/tests/test_health.py`

**Done when:** `uvicorn main:app --reload` starts, `/health` returns 200, DB has data.

---

## Phase 2 — Audio capture frontend

**Goal:** User can click record, speak, stop — audio blob is sent to backend.

**Tasks for Claude Code:**

1. Scaffold frontend: `npm create vite@latest frontend -- --template react-ts`, add Tailwind, Recharts.

2. Implement `useAudioRecorder.ts`:
   - Use `MediaRecorder` with `audio/webm;codecs=opus`
   - Expose: `{ isRecording, startRecording, stopRecording, audioBlob }`
   - On stop, collect chunks into a single Blob

3. Implement `AudioRecorder.tsx`:
   - Large circular mic button (idle / recording / processing states)
   - Simple animated waveform while recording (use `analyser` from Web Audio API, draw bars on a canvas)
   - Shows transcript text below once returned

4. On stop, POST the blob to `POST /query` as `multipart/form-data` with field name `audio`.

5. Show a loading spinner while waiting. No dashboard yet — just log the response.

**Done when:** Recording works in Chrome, blob POSTs successfully, response logged to console.

---

## Phase 3 — Transcript pipeline

**Goal:** Backend receives audio, returns cleaned plaintext.

**Tasks for Claude Code:**

1. Implement `backend/pipeline/transcriber.py`:
   ```python
   import whisper
   model = whisper.load_model("base")  # load once at startup

   def transcribe(audio_path: str) -> str:
       result = model.transcribe(audio_path)
       return result["text"]
   ```

2. Implement `backend/pipeline/normalizer.py`:
   ```python
   import re

   FILLERS = ["um", "uh", "like", "you know", "so", "actually", "basically"]

   def normalize(text: str) -> str:
       text = text.lower().strip()
       for f in FILLERS:
           text = re.sub(rf"\b{f}\b", "", text)
       text = re.sub(r"\s+", " ", text).strip()
       return text
   ```

3. Wire into `/query`: save uploaded audio to a temp file, transcribe, normalize, return `{"transcript": cleaned_text}`.

4. Test: record yourself saying "uh show me, like, total revenue by region" — confirm transcript comes back as "show me total revenue by region".

**Done when:** End-to-end audio → transcript works reliably.

---

## Phase 4 — Agent: schema grounding + SQL generation

**Goal:** Cleaned transcript → valid SQL via Claude.

**Tasks for Claude Code:**

1. Create `backend/pipeline/agent.py`. Load the full schema (table names, columns, types, 3 sample rows per table) into a string at startup.

2. Implement `generate_sql(query: str, schema_context: str) -> str`:

   ```python
   import anthropic
   client = anthropic.Anthropic()

   SYSTEM = """You are a SQL generation assistant.
   You have access to a SQLite database with the following schema:
   {schema}

   Rules:
   - Generate SELECT queries only. Never INSERT, UPDATE, DELETE, DROP.
   - Always LIMIT results to 500 rows unless the user asks for a specific count.
   - Use table aliases for clarity.
   - Output ONLY the SQL inside <sql> tags and a one-sentence explanation inside <explanation> tags.
   - If the question cannot be answered with the available data, output <sql>UNANSWERABLE</sql>.
   """

   def generate_sql(query: str, schema_context: str) -> tuple[str, str]:
       resp = client.messages.create(
           model="claude-sonnet-4-20250514",
           max_tokens=1000,
           system=SYSTEM.format(schema=schema_context),
           messages=[{"role": "user", "content": query}]
       )
       text = resp.content[0].text
       sql = extract_tag(text, "sql")
       explanation = extract_tag(text, "explanation")
       return sql, explanation
   ```

3. Implement `extract_tag(text, tag)` utility — simple regex.

4. Implement error recovery in `backend/pipeline/executor.py`:

   ```python
   import sqlite3

   MAX_RETRIES = 3

   def safe_execute(sql: str, db_path: str, history: list) -> dict:
       conn = sqlite3.connect(db_path)
       conn.row_factory = sqlite3.Row
       for attempt in range(MAX_RETRIES):
           try:
               cur = conn.execute(sql)
               rows = [dict(r) for r in cur.fetchall()]
               columns = [d[0] for d in cur.description]
               return {"rows": rows, "columns": columns, "sql": sql}
           except sqlite3.Error as e:
               if attempt == MAX_RETRIES - 1:
                   raise
               # Ask Claude to fix it
               sql = fix_sql(sql, str(e), history)
       conn.close()
   ```

5. Write `fix_sql(sql, error, history)` — single Claude call with the broken SQL + error message, returns corrected SQL.

6. Test with 5 example queries covering: aggregation, filtering, joining, time ranges, top-N.

**Done when:** All 5 test queries return valid SQL and execute successfully.

---

## Phase 5 — Viz type selection

**Goal:** Given query results, pick the right chart type automatically.

**Tasks for Claude Code:**

1. Implement `backend/pipeline/viz_selector.py`:

   ```python
   def select_viz(columns: list[str], rows: list[dict], query: str) -> VizSpec:
       n_rows = len(rows)
       n_cols = len(columns)
       has_date = any(c in ["date", "month", "week", "year", "created_at"] for c in columns)
       has_category = n_cols >= 2 and isinstance(rows[0][columns[0]], str)
       numeric_cols = [c for c in columns if isinstance(rows[0].get(c), (int, float))]

       # Decision logic
       if n_rows == 1 and n_cols <= 3:
           viz_type = "kpi"
       elif has_date and numeric_cols:
           viz_type = "line"
       elif has_category and len(numeric_cols) == 1 and n_rows <= 8:
           viz_type = "pie"
       elif has_category and numeric_cols:
           viz_type = "bar"
       elif n_rows > 50:
           viz_type = "table"
       else:
           viz_type = "bar"

       return VizSpec(
           type=viz_type,
           x_key=columns[0],
           y_keys=numeric_cols[:2],  # max 2 series
           title=infer_title(query),
           summary=""  # filled by agent
       )
   ```

2. Have Claude generate the plain-English summary as a final step: pass the query + first 5 rows + viz_type → 1–2 sentence answer.

3. Return the full `QueryResult` from `/query`.

**Done when:** Different query types (trend, comparison, single KPI, breakdown) each get the right chart type.

---

## Phase 6 — SSE progress streaming

**Goal:** UI shows live pipeline stages as they complete.

**Tasks for Claude Code:**

1. Change `/query` to return an SSE stream using FastAPI's `StreamingResponse`:

   ```python
   from fastapi.responses import StreamingResponse
   import json

   async def event_stream(audio_file):
       yield f"data: {json.dumps({'stage':'transcribing','status':'active'})}\n\n"
       transcript = transcribe(audio_file)
       yield f"data: {json.dumps({'stage':'transcribing','status':'done','detail':transcript})}\n\n"

       yield f"data: {json.dumps({'stage':'planning','status':'active'})}\n\n"
       sql, explanation = generate_sql(transcript, schema_ctx)
       yield f"data: {json.dumps({'stage':'planning','status':'done','detail':sql})}\n\n"

       yield f"data: {json.dumps({'stage':'querying','status':'active'})}\n\n"
       result = safe_execute(sql, DB_PATH, [])
       yield f"data: {json.dumps({'stage':'querying','status':'done'})}\n\n"

       viz_spec = select_viz(result["columns"], result["rows"], transcript)
       final = {**result, "viz_spec": viz_spec.dict(), "transcript": transcript}
       yield f"data: {json.dumps({'stage':'rendering','status':'done','result':final})}\n\n"
   ```

2. Implement `useQueryStream.ts` in the frontend:
   - POST audio → get back a stream URL or use `fetch` with `ReadableStream`
   - Parse each SSE event, update `PipelineEvent[]` state
   - When `stage === 'rendering'`, extract and set the `QueryResult`

3. Implement `ProgressStepper.tsx` — 4 steps with icons (mic, text, database, chart), highlight active/done states.

**Done when:** You can watch each step light up in real-time as the pipeline processes.

---

## Phase 7 — Dashboard renderer

**Goal:** Final QueryResult renders as a clean, appropriate chart.

**Tasks for Claude Code:**

1. Implement `ChartSwitcher.tsx` — receives `VizSpec` + `rows`, renders:
   - `"bar"` → `<BarChart>` from Recharts, x = `x_key`, bars for each `y_key`
   - `"line"` → `<LineChart>` with dots
   - `"pie"` → `<PieChart>` with labels
   - `"area"` → `<AreaChart>`
   - `"kpi"` → large number cards, one per numeric column
   - `"table"` → simple `<table>` with sortable columns

2. Implement `DashboardRenderer.tsx`:
   - Summary sentence at the top (from `viz_spec.summary`)
   - `<ChartSwitcher>` in the centre
   - Small "view SQL" toggle that shows the raw query
   - Export button (download CSV)

3. Add `QueryHistory.tsx` — store last 10 queries in `localStorage`, show transcript + mini chart thumbnail in a sidebar.

4. Polish: empty state, error state, loading skeleton.

**Done when:** A full end-to-end demo works — speak, watch pipeline, see chart.

---

## Phase 8 — Latency hardening

**Goal:** Reliably under 8 seconds end-to-end.

**Optimizations to implement:**

1. Load Whisper model at server startup (not per-request) — wrap in a module-level singleton.
2. Cache schema context string — compute once, reuse on every request.
3. Set `claude-sonnet-4-20250514` `max_tokens=600` — SQL rarely needs more.
4. Add a 10-second `asyncio.timeout` around the full pipeline — fail fast and show a useful error.
5. Measure each stage: add `time.perf_counter()` around transcribe, generate_sql, execute — log timings. Target: transcribe <2s, SQL gen <2s, execute <0.5s.

---

## Phase 9 — Polish + demo readiness

1. Add 3 "example questions" buttons on the home screen (skip recording, pre-fill transcript).
2. Add a data browser page — show the raw tables so users understand what they can ask.
3. Write a `README.md` with setup instructions and a 60-second demo script.
4. Record a Loom of the full flow.

---

## Known hard edges (handle these explicitly)

| Problem | Mitigation |
|---|---|
| Whisper mishears technical terms | Add a domain glossary correction step in normalizer.py |
| SQL references non-existent column | Self-validation step in agent.py before execution |
| Empty result set | Return a KPI card saying "No data found" with the SQL shown |
| Result has 1000+ rows | Cap at 500, tell user "showing top 500 results" |
| Ambiguous time references ("recently", "last time") | Default to last 30 days, note assumption in summary |
| User asks something unanswerable | Return UNANSWERABLE from agent, show friendly message |

---

## Suggested first message to Claude Code

> "Let's build a voice-to-dashboard app. I'll share a build plan document. Start with Phase 1: set up the FastAPI backend, create the SQLite schema with orders/customers/products tables, seed it with realistic fake data, and add a /health endpoint. Use Python 3.11 + FastAPI + uvicorn. When Phase 1 is done, write a test that confirms the server starts, the health endpoint returns 200, and the DB has at least 10,000 order rows."

Then for each subsequent phase:

> "Phase 1 is working. Now implement Phase 2: [paste phase text]."


# 🎤 TextToTable — Voice-to-Dashboard

> Speak a question. Get a dashboard.

TextToTable turns natural language voice queries into instant, interactive data dashboards. Ask _"show me revenue by region for last quarter"_ and watch a clean bar chart appear in seconds — complete with a plain-English summary and the underlying SQL.

---

## ✨ Demo

<!-- TODO: Replace with recorded demo GIF/video -->
> _Coming soon — record a Loom of the full flow in Phase 9._

---

## 🏗️ Architecture

```
🎙️ Voice Input
    │
    ▼
┌───────────────┐
│ MediaRecorder  │  Browser captures audio (WebM/Opus)
└──────┬────────┘
       │  POST /query (multipart)
       ▼
┌───────────────┐
│  Whisper STT   │  Local transcription (base model)
└──────┬────────┘
       │  raw text
       ▼
┌───────────────┐
│  Normalizer    │  Strip fillers, clean up
└──────┬────────┘
       │  cleaned query
       ▼
┌───────────────┐
│  Claude Agent  │  Generate SQL from natural language
└──────┬────────┘
       │  SQL
       ▼
┌───────────────┐
│  SQL Executor  │  Run against SQLite + auto-retry
└──────┬────────┘
       │  rows + columns
       ▼
┌───────────────┐
│  Viz Selector  │  Pick chart type (bar/line/pie/kpi/table)
└──────┬────────┘
       │  VizSpec + data
       ▼
┌───────────────┐
│  Dashboard UI  │  Recharts renders the result
└───────────────┘
```

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Frontend** | React + Vite + TypeScript | Fast dev, type safety |
| **Styling** | Tailwind CSS v4 | Utility-first, rapid UI |
| **Charts** | Recharts | Composable React charts |
| **Audio** | Browser MediaRecorder API | Zero-dependency recording |
| **Backend** | Python 3.11 + FastAPI | Async API server |
| **Speech-to-Text** | OpenAI Whisper (local, `base`) | Free, offline-capable |
| **LLM** | Anthropic Claude Sonnet | SQL generation + summaries |
| **Database** | SQLite | Zero-config, Postgres-ready |
| **Streaming** | Server-Sent Events (SSE) | Real-time pipeline progress |

---

## 📁 Project Structure

```
textoanalytics/
├── backend/
│   ├── db/
│   │   ├── schema.sql          # Table definitions
│   │   └── seed.py             # Generate 10K+ realistic records
│   ├── pipeline/
│   │   ├── transcriber.py      # Whisper STT wrapper
│   │   ├── normalizer.py       # Filler word removal
│   │   ├── agent.py            # Claude SQL generation
│   │   ├── executor.py         # Safe SQL execution + retry
│   │   └── viz_selector.py     # Chart type selection
│   ├── tests/
│   │   └── test_health.py      # Health endpoint tests
│   ├── main.py                 # FastAPI app entry point
│   ├── models.py               # Pydantic schemas
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── AudioRecorder.tsx
│       │   ├── ProgressStepper.tsx
│       │   ├── DashboardRenderer.tsx
│       │   ├── ChartSwitcher.tsx
│       │   └── QueryHistory.tsx
│       ├── hooks/
│       │   ├── useAudioRecorder.ts
│       │   └── useQueryStream.ts
│       ├── App.tsx
│       └── index.css
├── voice-to-dashboard-plan.md
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.11+**
- **Node.js 18+** and npm
- **ffmpeg** (required by Whisper): `brew install ffmpeg`

### Backend Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Start the server (auto-seeds database on first run)
python main.py
```

The API will be live at **http://localhost:8000**. Check health:

```bash
curl http://localhost:8000/health
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The app will be live at **http://localhost:5173**.

---

## 📋 Phase Roadmap

- [x] **Phase 1** — Backend skeleton, SQLite schema, seed data, `/health` endpoint
- [x] **Phase 2** — Audio capture frontend (mic button, waveform, POST to backend)
- [ ] **Phase 3** — Transcript pipeline (Whisper STT + normalizer)
- [ ] **Phase 4** — Claude SQL agent (NL → SQL with error recovery)
- [ ] **Phase 5** — Viz type selection (auto-pick bar/line/pie/kpi/table)
- [ ] **Phase 6** — SSE progress streaming (live pipeline status)
- [ ] **Phase 7** — Dashboard renderer (Recharts + export)
- [ ] **Phase 8** — Latency hardening (< 8s end-to-end)
- [ ] **Phase 9** — Polish + demo readiness

---

## 📄 License

MIT

---

<p align="center">
  Built with 🎙️ + 🤖 by <a href="https://github.com/AkkuB0Y">AkkuB0Y</a>
</p>

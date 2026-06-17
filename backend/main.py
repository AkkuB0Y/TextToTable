"""
Voice-to-Dashboard — FastAPI backend entry point.

Phase 1: Health check, DB setup, query stub.
Phase 3: Whisper transcription + text normalization.
Phase 4: Claude SQL generation + safe execution.
"""

from __future__ import annotations

import sqlite3
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from models import HealthResponse, QueryResult, VizSpec, VizType
from pipeline.transcriber import transcribe, preload_model
from pipeline.normalizer import normalize
from pipeline.agent import generate_sql, get_schema_context
from pipeline.executor import safe_execute

# ─── Database ───────────────────────────────────────────────────────────────────

DB_DIR = Path(__file__).parent / "db"
DB_PATH = DB_DIR / "app.db"


def get_db() -> sqlite3.Connection:
    """Get a database connection with row factory enabled."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def ensure_db() -> None:
    """Ensure the database exists and is seeded. Run at startup."""
    if not DB_PATH.exists():
        print("📦 Database not found — running seed script...")
        from db.seed import seed_database
        seed_database(DB_PATH)
    else:
        # Verify it has data
        conn = get_db()
        count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        conn.close()
        if count == 0:
            print("📦 Database empty — re-seeding...")
            from db.seed import seed_database
            seed_database(DB_PATH)
        else:
            print(f"✅ Database ready — {count} orders found")


# ─── App Lifecycle ──────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    ensure_db()
    preload_model()  # Phase 3: pre-warm Whisper so first query is fast
    # Phase 4: pre-cache schema context for Claude
    get_schema_context(DB_PATH)
    print("🧠 Schema context loaded for Claude agent")
    yield


# ─── FastAPI App ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Voice-to-Dashboard API",
    description="Speak a question, get a dashboard back.",
    version="0.4.0",
    lifespan=lifespan,
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint with database statistics."""
    conn = get_db()
    try:
        orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        customers = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        products = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    finally:
        conn.close()

    return HealthResponse(
        status="ok",
        db_orders_count=orders,
        db_customers_count=customers,
        db_products_count=products,
    )


@app.post("/query", response_model=QueryResult)
async def query_dashboard(audio: UploadFile = File(...)):
    """
    Process a voice query and return dashboard data.

    Phase 4 pipeline:
    1. Save audio → temp file
    2. Transcribe with Whisper
    3. Normalize transcript (remove fillers)
    4. Generate SQL via Claude
    5. Execute SQL safely
    6. Return results with basic viz spec
    """
    # ── Step 1: Save uploaded audio to a temp file ──────────────────────────
    suffix = Path(audio.filename or "query.webm").suffix or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        contents = await audio.read()
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        # ── Step 2: Transcribe with Whisper ─────────────────────────────────
        raw_transcript = transcribe(tmp_path)
        print(f"📝 Raw transcript: {raw_transcript}")

        # ── Step 3: Normalize (remove fillers, lowercase, clean up) ─────────
        cleaned_transcript = normalize(raw_transcript)
        print(f"✨ Cleaned transcript: {cleaned_transcript}")

    finally:
        # Clean up temp audio file
        Path(tmp_path).unlink(missing_ok=True)

    # ── Step 4: Generate SQL via Claude ─────────────────────────────────────
    schema_ctx = get_schema_context(DB_PATH)
    try:
        sql, explanation = generate_sql(cleaned_transcript, schema_ctx)
    except RuntimeError as e:
        # API key not set or other agent error — return graceful error
        print(f"⚠️  Agent error: {e}")
        return QueryResult(
            rows=[],
            columns=[],
            viz_spec=VizSpec(
                type=VizType.KPI,
                title="Configuration Error",
                summary=str(e),
            ),
            sql="",
            transcript=cleaned_transcript,
        )
    print(f"🔍 Generated SQL: {sql}")
    print(f"💡 Explanation: {explanation}")

    # Handle unanswerable queries
    if sql.strip().upper() == "UNANSWERABLE":
        return QueryResult(
            rows=[],
            columns=[],
            viz_spec=VizSpec(
                type=VizType.KPI,
                title="Unable to Answer",
                summary=explanation or "This question cannot be answered with the available data.",
            ),
            sql="UNANSWERABLE",
            transcript=cleaned_transcript,
        )

    # ── Step 5: Execute SQL safely ──────────────────────────────────────────
    try:
        result = safe_execute(sql, DB_PATH)
    except Exception as e:
        print(f"❌ SQL execution failed: {e}")
        return QueryResult(
            rows=[],
            columns=[],
            viz_spec=VizSpec(
                type=VizType.KPI,
                title="Query Error",
                summary=f"The generated SQL could not be executed: {str(e)[:200]}",
            ),
            sql=sql,
            transcript=cleaned_transcript,
        )

    # ── Step 6: Build response ──────────────────────────────────────────────
    rows = result["rows"]
    columns = result["columns"]
    actual_sql = result["sql"]  # might be fixed SQL from retry

    # Basic viz type selection (Phase 5 will make this smarter)
    viz_type = _pick_basic_viz_type(columns, rows)

    # Identify numeric columns for y_keys
    numeric_cols = []
    if rows:
        for col in columns:
            val = rows[0].get(col)
            if isinstance(val, (int, float)):
                numeric_cols.append(col)

    truncation_note = ""
    if result.get("truncated"):
        truncation_note = f" (showing top {result['row_count']} of more results)"

    return QueryResult(
        rows=rows,
        columns=columns,
        viz_spec=VizSpec(
            type=viz_type,
            x_key=columns[0] if columns else None,
            y_keys=numeric_cols[:2],
            title=explanation or cleaned_transcript,
            summary=f"{explanation}{truncation_note}" if explanation else cleaned_transcript,
        ),
        sql=actual_sql,
        transcript=cleaned_transcript,
    )


def _pick_basic_viz_type(columns: list[str], rows: list[dict]) -> VizType:
    """
    Simple heuristic for chart type selection.
    Phase 5 will replace this with the full viz_selector.py logic.
    """
    n_rows = len(rows)
    n_cols = len(columns)

    if n_rows == 0:
        return VizType.KPI

    # Single aggregate result → KPI card
    if n_rows == 1 and n_cols <= 3:
        return VizType.KPI

    # Check for date-like columns
    date_keywords = {"date", "month", "week", "year", "created_at", "signup_date", "day"}
    has_date = any(c.lower() in date_keywords for c in columns)

    # Check for category-like first column
    has_category = n_cols >= 2 and isinstance(rows[0].get(columns[0]), str)

    # Check for numeric columns
    numeric_cols = [
        c for c in columns
        if rows and isinstance(rows[0].get(c), (int, float))
    ]

    if has_date and numeric_cols:
        return VizType.LINE
    elif has_category and len(numeric_cols) == 1 and n_rows <= 8:
        return VizType.PIE
    elif has_category and numeric_cols:
        return VizType.BAR
    elif n_rows > 50:
        return VizType.TABLE
    else:
        return VizType.BAR


# ─── Run directly ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

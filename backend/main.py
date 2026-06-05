"""
Voice-to-Dashboard — FastAPI backend entry point.

Phase 1: Health check, DB setup, query stub.
"""

from __future__ import annotations

import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from models import HealthResponse, QueryResult, VizSpec, VizType

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
    yield


# ─── FastAPI App ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Voice-to-Dashboard API",
    description="Speak a question, get a dashboard back.",
    version="0.1.0",
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
    
    Phase 1 stub: returns hardcoded sample data.
    Later phases will add: transcription → SQL generation → execution → viz selection.
    """
    # Phase 1: return hardcoded sample result
    sample_rows = [
        {"region": "North America", "total_revenue": 125430.50, "order_count": 5200},
        {"region": "Europe", "total_revenue": 98210.75, "order_count": 4100},
        {"region": "Asia Pacific", "total_revenue": 67890.25, "order_count": 2800},
        {"region": "Latin America", "total_revenue": 34560.00, "order_count": 1400},
        {"region": "Middle East & Africa", "total_revenue": 12340.80, "order_count": 500},
    ]

    return QueryResult(
        rows=sample_rows,
        columns=["region", "total_revenue", "order_count"],
        viz_spec=VizSpec(
            type=VizType.BAR,
            x_key="region",
            y_keys=["total_revenue"],
            title="Revenue by Region",
            summary="North America leads with $125K in total revenue, followed by Europe at $98K.",
        ),
        sql="SELECT region, SUM(amount) as total_revenue, COUNT(*) as order_count FROM orders GROUP BY region",
        transcript="show me revenue by region",
    )


# ─── Run directly ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

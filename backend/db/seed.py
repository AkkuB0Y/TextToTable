"""
Seed script for voice-to-dashboard demo database.

Generates 500 customers, 50 products, and 15,000+ orders spanning 2 years
with realistic seasonal patterns, regional distribution, and business metrics.
"""
from __future__ import annotations

import sqlite3
import random
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Union

# ─── Configuration ──────────────────────────────────────────────────────────────

NUM_CUSTOMERS = 500
NUM_PRODUCTS = 50
NUM_ORDERS = 15_000
DB_PATH = Path(__file__).parent / "app.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

REGIONS = ["North America", "Europe", "Asia Pacific", "Latin America", "Middle East & Africa"]
REGION_WEIGHTS = [0.35, 0.30, 0.20, 0.10, 0.05]

PLAN_TYPES = ["free", "starter", "pro", "enterprise"]
PLAN_WEIGHTS = [0.40, 0.30, 0.20, 0.10]

ORDER_STATUSES = ["completed", "pending", "refunded", "cancelled"]
STATUS_WEIGHTS = [0.75, 0.10, 0.10, 0.05]

# Realistic product catalog
PRODUCT_CATALOG = {
    "Analytics": [
        ("Dashboard Pro", 49.99), ("Report Builder", 29.99), ("Data Explorer", 39.99),
        ("Metrics Suite", 59.99), ("Insight Engine", 79.99), ("Chart Studio", 24.99),
        ("KPI Tracker", 19.99), ("Forecast Module", 89.99), ("Trend Analyzer", 44.99),
        ("Real-Time Monitor", 69.99),
    ],
    "Security": [
        ("Firewall Plus", 99.99), ("Auth Shield", 59.99), ("Vault Manager", 149.99),
        ("Threat Scanner", 79.99), ("Compliance Kit", 119.99), ("Access Control", 44.99),
        ("Encryption Suite", 89.99), ("Audit Logger", 34.99), ("Pen Test Tools", 199.99),
        ("Zero Trust Gateway", 159.99),
    ],
    "Communication": [
        ("Chat Connect", 14.99), ("Video Bridge", 29.99), ("Email Automator", 24.99),
        ("Notification Hub", 19.99), ("Team Messenger", 34.99), ("Broadcast Pro", 49.99),
        ("Support Desk", 39.99), ("Survey Builder", 22.99), ("Feedback Loop", 17.99),
        ("Webinar Host", 59.99),
    ],
    "Infrastructure": [
        ("Cloud Deploy", 199.99), ("Container Manager", 149.99), ("Load Balancer", 79.99),
        ("CDN Accelerator", 99.99), ("Backup Vault", 59.99), ("DNS Manager", 29.99),
        ("CI/CD Pipeline", 89.99), ("Log Aggregator", 49.99), ("Uptime Monitor", 24.99),
        ("Config Manager", 39.99),
    ],
    "AI & ML": [
        ("Model Trainer", 299.99), ("NLP Toolkit", 199.99), ("Image Classifier", 149.99),
        ("Recommendation Engine", 249.99), ("Anomaly Detector", 129.99),
    ],
}

# Realistic names
FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda",
    "David", "Elizabeth", "William", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Christopher", "Karen", "Charles", "Lisa", "Daniel", "Nancy",
    "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra", "Donald", "Ashley",
    "Steven", "Kimberly", "Paul", "Emily", "Andrew", "Donna", "Joshua", "Michelle",
    "Aisha", "Wei", "Raj", "Yuki", "Sofia", "Carlos", "Fatima", "Hans",
    "Priya", "Omar", "Sakura", "Diego", "Amara", "Chen", "Leila", "Erik",
    "Ines", "Kai", "Nadia", "Ravi", "Yuna", "Marco", "Zara", "Akira",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson",
    "Patel", "Nakamura", "Kim", "Chen", "Singh", "Mueller", "Johansson", "Tanaka",
    "AlRashid", "OBrien", "Kowalski", "Nguyen", "Sato", "Ferrari", "Berg",
    "Costa", "Sharma", "Wu", "Park", "Ivanova", "Fischer", "Santos", "Yamamoto",
]


# ─── Helpers ────────────────────────────────────────────────────────────────────

def random_date(start, end):
    """Generate a random datetime between start and end."""
    delta = end - start
    total_seconds = int(delta.total_seconds())
    if total_seconds <= 0:
        return start
    random_seconds = random.randint(0, total_seconds)
    return start + timedelta(seconds=random_seconds)


def seasonal_multiplier(month):
    """Simulate seasonal buying patterns (Q4 spike, Q1 dip)."""
    seasonal = {
        1: 0.7, 2: 0.75, 3: 0.85, 4: 0.90, 5: 0.95, 6: 1.0,
        7: 0.90, 8: 0.95, 9: 1.05, 10: 1.15, 11: 1.35, 12: 1.50,
    }
    return seasonal.get(month, 1.0)


# ─── Seeding Functions ──────────────────────────────────────────────────────────

def seed_customers(conn):
    """Seed customers table and return list of customer IDs."""
    start_date = datetime(2023, 1, 1)
    end_date = datetime(2025, 6, 1)
    customer_ids = []
    used_emails = set()

    for i in range(NUM_CUSTOMERS):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        name = "{} {}".format(first, last)

        # Generate unique email
        base_email = "{}.{}".format(first.lower(), last.lower())
        email = "{}@example.com".format(base_email)
        counter = 1
        while email in used_emails:
            email = "{}{}@example.com".format(base_email, counter)
            counter += 1
        used_emails.add(email)

        plan_type = random.choices(PLAN_TYPES, weights=PLAN_WEIGHTS, k=1)[0]
        region = random.choices(REGIONS, weights=REGION_WEIGHTS, k=1)[0]
        signup_date = random_date(start_date, end_date).strftime("%Y-%m-%d")

        # ~15% churn rate, biased toward free/starter plans
        churned_at = None
        churn_chance = {"free": 0.25, "starter": 0.15, "pro": 0.08, "enterprise": 0.03}
        if random.random() < churn_chance.get(plan_type, 0.10):
            signup_dt = datetime.strptime(signup_date, "%Y-%m-%d")
            churn_start = signup_dt + timedelta(days=30)
            if churn_start < end_date:
                churn_date = random_date(churn_start, end_date)
                churned_at = churn_date.strftime("%Y-%m-%d")

        conn.execute(
            "INSERT INTO customers (name, email, plan_type, region, signup_date, churned_at) VALUES (?, ?, ?, ?, ?, ?)",
            (name, email, plan_type, region, signup_date, churned_at),
        )
        customer_ids.append(i + 1)

    conn.commit()
    print("  > Seeded {} customers".format(NUM_CUSTOMERS))
    return customer_ids


def seed_products(conn):
    """Seed products table and return list of product IDs."""
    product_ids = []
    idx = 0
    for category, products in PRODUCT_CATALOG.items():
        for name, price in products:
            launched = datetime(2023, 1, 1) + timedelta(days=random.randint(0, 365))
            conn.execute(
                "INSERT INTO products (name, category, price, launched_at) VALUES (?, ?, ?, ?)",
                (name, category, price, launched.strftime("%Y-%m-%d")),
            )
            idx += 1
            product_ids.append(idx)
    conn.commit()
    print("  > Seeded {} products".format(idx))
    return product_ids


def seed_orders(conn, customer_ids, product_ids):
    """Seed orders table with realistic patterns. Returns count of orders created."""
    start_date = datetime(2023, 6, 1)
    end_date = datetime(2025, 5, 31)

    # Pre-fetch product prices
    products = {}
    for row in conn.execute("SELECT id, price, category FROM products"):
        products[row[0]] = {"price": row[1], "category": row[2]}

    # Pre-fetch customer regions
    customer_regions = {}
    for row in conn.execute("SELECT id, region FROM customers"):
        customer_regions[row[0]] = row[1]

    orders_data = []
    for _ in range(NUM_ORDERS):
        order_date = random_date(start_date, end_date)

        # Apply seasonal weighting — more orders in Q4
        if random.random() > seasonal_multiplier(order_date.month) * 0.67:
            q4_start = datetime(order_date.year, 10, 1)
            q4_end = datetime(order_date.year, 12, 31)
            if q4_start < end_date:
                order_date = random_date(q4_start, min(q4_end, end_date))

        customer_id = random.choice(customer_ids)
        product_id = random.choice(product_ids)
        product = products[product_id]

        quantity = random.choices(
            [1, 2, 3, 5, 10],
            weights=[0.50, 0.25, 0.15, 0.07, 0.03],
            k=1
        )[0]

        base_amount = product["price"] * quantity
        variance = random.uniform(0.90, 1.10)
        amount = round(base_amount * variance, 2)

        status = random.choices(ORDER_STATUSES, weights=STATUS_WEIGHTS, k=1)[0]
        region = customer_regions[customer_id]

        orders_data.append((
            customer_id, product_id, quantity, amount,
            order_date.strftime("%Y-%m-%dT%H:%M:%S"),
            status, region,
        ))

    conn.executemany(
        "INSERT INTO orders (customer_id, product_id, quantity, amount, created_at, status, region) VALUES (?, ?, ?, ?, ?, ?, ?)",
        orders_data,
    )
    conn.commit()
    print("  > Seeded {} orders".format(len(orders_data)))
    return len(orders_data)


# ─── Main ───────────────────────────────────────────────────────────────────────

def seed_database(db_path=None):
    """Create and seed the database. Returns the path to the created DB."""
    db_path = Path(db_path) if db_path else DB_PATH

    if db_path.exists():
        db_path.unlink()
        print("  Removed existing database at {}".format(db_path))

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    schema_sql = SCHEMA_PATH.read_text()
    conn.executescript(schema_sql)
    print("  > Schema applied from {}".format(SCHEMA_PATH))

    random.seed(42)  # Reproducible data
    customer_ids = seed_customers(conn)
    product_ids = seed_products(conn)
    order_count = seed_orders(conn, customer_ids, product_ids)

    counts = {}
    for table in ["customers", "products", "orders"]:
        count = conn.execute("SELECT COUNT(*) FROM {}".format(table)).fetchone()[0]
        counts[table] = count

    conn.close()

    print("")
    print("  Database seeded at: {}".format(db_path))
    print("  Customers: {}".format(counts['customers']))
    print("  Products:  {}".format(counts['products']))
    print("  Orders:    {}".format(counts['orders']))
    print("  DB size:   {:.0f} KB".format(db_path.stat().st_size / 1024))

    return db_path


if __name__ == "__main__":
    print("Seeding voice-to-dashboard database...\n")
    seed_database()
    print("\nDone!")

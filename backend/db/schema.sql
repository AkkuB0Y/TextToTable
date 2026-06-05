-- Voice-to-Dashboard: Database Schema
-- Realistic e-commerce dataset for natural language querying

CREATE TABLE IF NOT EXISTS customers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    email       TEXT UNIQUE NOT NULL,
    plan_type   TEXT NOT NULL CHECK (plan_type IN ('free', 'starter', 'pro', 'enterprise')),
    region      TEXT NOT NULL CHECK (region IN ('North America', 'Europe', 'Asia Pacific', 'Latin America', 'Middle East & Africa')),
    signup_date TEXT NOT NULL,  -- ISO 8601 date
    churned_at  TEXT            -- NULL if still active
);

CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL,
    price       REAL NOT NULL CHECK (price > 0),
    launched_at TEXT NOT NULL   -- ISO 8601 date
);

CREATE TABLE IF NOT EXISTS orders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    product_id  INTEGER NOT NULL REFERENCES products(id),
    quantity    INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
    amount      REAL NOT NULL CHECK (amount >= 0),
    created_at  TEXT NOT NULL,  -- ISO 8601 datetime
    status      TEXT NOT NULL CHECK (status IN ('completed', 'pending', 'refunded', 'cancelled')),
    region      TEXT NOT NULL CHECK (region IN ('North America', 'Europe', 'Asia Pacific', 'Latin America', 'Middle East & Africa'))
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);
CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_product_id ON orders(product_id);
CREATE INDEX IF NOT EXISTS idx_orders_region ON orders(region);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_customers_plan_type ON customers(plan_type);
CREATE INDEX IF NOT EXISTS idx_customers_region ON customers(region);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);

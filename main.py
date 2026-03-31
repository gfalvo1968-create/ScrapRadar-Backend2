from fastapi import FastAPI
from pydantic import BaseModel
import yfinance as yf
import numpy as np
import sqlite3
from contextlib import closing

print("Backend file loaded successfully")

app = FastAPI()

DB_NAME = "scrapradar.db"


class PriceEntry(BaseModel):
    metal: str
    price: float
    yard: str

init_db()

def init_db():
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS prices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metal TEXT NOT NULL,
                    price REAL NOT NULL,
                    yard TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)


init_db()

yards = [
    {"name": "Langley Recycling", "lat": 34.5, "lng": -78.8, "base_price": 2.50},
    {"name": "Metro Scrap", "lat": 34.3, "lng": -78.7, "base_price": 2.30},
]


def get_copper_series():
    copper = yf.Ticker("HG=F")
    data = copper.history(period="7d")["Close"]
    return [float(x) for x in data.tolist()]


def predict_prices(prices):
    if not prices:
        return [], 0.0

    if len(prices) == 1:
        return [prices[0], prices[0], prices[0]], 0.0

    x = np.arange(len(prices))
    y = np.array(prices, dtype=float)

    coeffs = np.polyfit(x, y, 1)
    trend = float(coeffs[0])

    future = []
    last_price = float(y[-1])

    for i in range(1, 4):
        future.append(last_price + trend * i)

    return future, trend


@app.get("/")
def home():
    return {"status": "ScrapRadar is live"}


@app.get("/market")
def market():
    copper_prices = get_copper_series()
    future, trend = predict_prices(copper_prices)

    with closing(sqlite3.connect(DB_NAME)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT metal, price, yard, created_at
            FROM prices
            ORDER BY created_at DESC
        """).fetchall()

        manual_entries = [dict(row) for row in rows]

    current_price = copper_prices[-1] if copper_prices else None

    return {
        "current": current_price,
        "forecast": future,
        "trend": trend,
        "manual_entries": manual_entries
    }


@app.post("/add-price")
def add_price(entry: PriceEntry):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute(
                """
                INSERT INTO prices (metal, price, yard)
                VALUES (?, ?, ?)
                """,
                (entry.metal, entry.price, entry.yard)
            )

    return {"status": "saved"}


@app.get("/history")
def get_history():
    with closing(sqlite3.connect(DB_NAME)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT id, metal, price, yard, created_at
            FROM prices
            ORDER BY created_at DESC
        """).fetchall()

    return [dict(row) for row in rows]


@app.get("/history/{metal}")
def get_history_by_metal(metal: str):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT id, metal, price, yard, created_at
            FROM prices
            WHERE LOWER(metal) = LOWER(?)
            ORDER BY created_at DESC
        """, (metal,)).fetchall()

    return [dict(row) for row in rows]


@app.get("/yards")
def get_yards():
    return yards


@app.get("/decision")
def decision():
    with closing(sqlite3.connect(DB_NAME)) as conn:
        conn.row_factory = sqlite3.Row
        latest = conn.execute("""
            SELECT metal, price, yard, created_at
            FROM prices
            ORDER BY created_at DESC
            LIMIT 1
        """).fetchone()

    if latest is None:
        return {"decision": "No data yet"}

    latest_price = float(latest["price"])

    if latest_price >= 4.0:
        return {"decision": "SELL NOW"}
    elif latest_price >= 3.0:
        return {"decision": "WATCH CLOSELY"}
    else:
        return {"decision": "HOLD"}

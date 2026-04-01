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


class PriceEntry(BaseModel):
    metal: str
    price: float
    yard: str




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
        rows = conn.execute("""
            SELECT price, created_at
            FROM prices
            ORDER BY created_at DESC
            LIMIT 3
        """).fetchall()

    if not rows:
        return {"decision": "No data yet"}

    prices = [float(row["price"]) for row in rows]

    if len(prices) == 1:
        latest = prices[0]
        if latest >= 4.0:
            return {"decision": "SELL NOW", "latest_price": latest, "change": 0.0}
        elif latest >= 3.0:
            return {"decision": "WATCH CLOSELY", "latest_price": latest, "change": 0.0}
        else:
            return {"decision": "HOLD", "latest_price": latest, "change": 0.0}

    newest = prices[0]
    oldest = prices[-1]
    change = newest - oldest

    if change <= -0.10:
        result = "SELL NOW"
    elif change >= 0.10:
        result = "HOLD"
    else:
        result = "WATCH CLOSELY"

    return {
        "decision": result,
        "latest_price": newest,
        "change": round(change, 2)
    }

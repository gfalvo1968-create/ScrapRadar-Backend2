from fastapi import FastAPI
import yfinance as yf
import numpy as np
import sqlite3
from contextlib import closing

print("Backend file loaded successfully")

# ------------------------
# APP SETUP
# ------------------------
app = FastAPI()

# ------------------------
# DATA STORAGE (Stage 1)
# ------------------------
DB_NAME = "scrapradar.db"

def init_db():
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS prices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metal TEXT NOT NULL,
                    price REAL NOT NULL,
                    yard TEXT NOT NULL
                )
            """)

init_db()

manual_prrice=[]

# ------------------------
# STATIC DATA
# ------------------------
yards = [
    {"name": "Langley Recycling", "lat": 34.5, "lng": -78.8, "base_price": 2.50},
    {"name": "Metro Scrap", "lat": 34.3, "lng": -78.7, "base_price": 2.30},
]

from pydantic import BaseModel
class PriceEntry(BaseModel):
    metal: str
    price: float
    yard: str
    
# ------------------------
# LIVE DATA FUNCTION
# ------------------------
def get_copper_series():
    copper = yf.Ticker("HG=F")
    data = copper.history(period="7d")["Close"]
    return list(data)

# ------------------------
# SIMPLE TREND LOGIC
# ------------------------
def predict_prices(prices):
    x = np.arange(len(prices))
    y = np.array(prices)

    coeffs = np.polyfit(x, y, 1)
    trend = coeffs[0]

    future = []
    for i in range(1, 4):
        future.append(float(y[-1] + trend * i))

    return future, trend

# ------------------------
# ROUTES
# ------------------------

# Home
@app.get("/")
def home():
    return {"status": "scrapradar is live 🚀"}

# Add manual price (Stage 1 core)
@app.post("/add-price")
def add_price(data: dict):
    metal = data.get("metal")
    price = data.get("price")
    yard = data.get("yard")

    if not metal or price is None or not yard:
        return {"error": "metal, price, and yard are required"}

    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute(
                "INSERT INTO prices (metal, price, yard) VALUES (?, ?, ?)",
                (metal, price, yard)
            )

    return {"status": "saved"}

# Market data (combined)
@app.get("/market")
def market():
    copper_prices = get_copper_series()
    future, trend = predict_prices(copper_prices)

    with closing(sqlite3.connect(DB_NAME)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT metal, price, yard FROM prices").fetchall()
        manual_entries = [dict(row) for row in rows]
        return {"status": "saved"}
     
    

# Yards
@app.get("/yards")
def get_yards():
    return yards

# Decision logic
@app.get("/decision")
def decision():
    with closing(sqlite3.connect(DB_NAME)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT metal, price, yard FROM prices ORDER BY id DESC LIMIT 1"
        ).fetchone()

    if not row:
        return {"decision": "No data yet"}

    latest = dict(row)

    if latest["price"] > 4:
        return {"decision": "SELL NOW"}
    else:
        return {"decision": "HOLD"}

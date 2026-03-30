from fastapi import FastAPI
import yfinance as yf
import numpy as np
import sqlite3
from contextlib import closing
from pydantic import BaseModel

class PriceEntry(BaseModel):
    metal: str
    price: float
    yard: str

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
                    yard TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
     
@app.post("/add-price")
def add_price(data: PriceEntry):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute(
                "INSERT INTO prices (metal, price, yard) VALUES (?, ?, ?)",
                (data.metal, data.price, data.yard)
            
@app.get("/history/{metal}")
def history_by_metal(metal: str):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        cursor = conn.execute("""
            SELECT price, yard, created_at
            FROM prices
            WHERE LOWER(metal) = LOWER(?)
            ORDER BY created_at ASC
        """, (metal,))
        rows = cursor.fetchall()

    return [
        {
            "price": row[0],
            "yard": row[1],
            "created_at": row[2]
        }
        for row in rows
    ]
                
                
# Yards
@app.get("/yards")
def get_yards():
    return yards

# Decision logic
@app.get("/decision")
def decision():
    with closing(sqlite3.connect(DB_NAME)) as conn:
        cursor = conn.execute("""
            SELECT metal, price, yard, created_at
            FROM prices
            ORDER BY created_at DESC
            LIMIT 3
        """)
        rows = cursor.fetchall()

    if not rows:
        return {"decision": "No data yet"}

    latest_price = rows[0][1]

    if latest_price >= 4.0:
        return {"decision": "SELL NOW"}

    if len(rows) >= 2 and rows[0][1] > rows[1][1]:
        return {"decision": "TRENDING UP, WATCH CLOSELY"}

    return {"decision": "HOLD"}

from fastapi import FastAPI
from pydantic import BaseModel
import yfinance as yf
import numpy as np
import sqlite3
from contextlib import closing
from fastapi.responses import HTMLResponse

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


@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>ScrapRadar</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 20px;
                background: #f4f6f8;
                color: #222;
            }
            h1 {
                margin-bottom: 10px;
            }
            .card {
                background: white;
                padding: 16px;
                margin-bottom: 16px;
                border-radius: 12px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            }
            input, button {
                padding: 10px;
                margin: 6px 0;
                width: 100%;
                max-width: 300px;
                display: block;
            }
            button {
                background: #1f6feb;
                color: white;
                border: none;
                border-radius: 8px;
                cursor: pointer;
            }
            button:hover {
                opacity: 0.92;
            }
            pre {
                background: #111;
                color: #0f0;
                padding: 12px;
                border-radius: 8px;
                overflow-x: auto;
            }
        </style>
    </head>
    <body>
        <h1>ScrapRadar Dashboard</h1>

        <div class="card">
            <h2>Current Market</h2>
            <button onclick="loadMarket()">Load Market</button>
            <pre id="marketBox">Press button to load market data...</pre>
        </div>

        <div class="card">
            <h2>Decision</h2>
            <button onclick="loadDecision()">Get Decision</button>
            <pre id="decisionBox">Press button to load decision...</pre>
        </div>

        <div class="card">
            <h2>Add Price</h2>
            <input id="metal" placeholder="Metal (example: copper)" />
            <input id="price" placeholder="Price (example: 4.25)" type="number" step="0.01" />
            <input id="yard" placeholder="Yard (example: Metro Scrap)" />
            <button onclick="addPrice()">Save Price</button>
            <pre id="addBox">Waiting for input...</pre>
        </div>

        <div class="card">
            <h2>History</h2>
            <button onclick="loadHistory()">Load History</button>
            <pre id="historyBox">Press button to load history...</pre>
        </div>

            <div class="card">
            <h2>Price Chart</h2>
            <button onclick="loadChart()">Load Chart</button>
            <canvas id="priceChart" height="120"></canvas>
         </div>

        <script>
            async function loadMarket() {
                const res = await fetch('/market');
                const data = await res.json();
                document.getElementById('marketBox').textContent = JSON.stringify(data, null, 2);
            }

            async function loadDecision() {
                const res = await fetch('/decision');
                const data = await res.json();
                document.getElementById('decisionBox').textContent = JSON.stringify(data, null, 2);
            }

            async function loadHistory() {
                const res = await fetch('/history');
                const data = await res.json();
                document.getElementById('historyBox').textContent = JSON.stringify(data, null, 2);
            }

            async function addPrice() {
                const metal = document.getElementById('metal').value;
                const price = parseFloat(document.getElementById('price').value);
                const yard = document.getElementById('yard').value;

                const res = await fetch('/add-price', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ metal, price, yard })
                });

                const data = await res.json();
                document.getElementById('addBox').textContent = JSON.stringify(data, null, 2);
            }
        </script>
    </body>
    </html>
    """


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

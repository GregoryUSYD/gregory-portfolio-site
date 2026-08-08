"""
generate_market_data.py

Fetches watchlist quotes and writes market_data.json for the website's
homepage dashboard.

This reuses the watchlist structure and fetch logic from macro_terminal.py
(the desktop terminal), reorganized into the six categories shown on the
site: indices / bonds / commodities / Forex / equity / other. Instead of
updating a Tkinter UI, it writes a JSON file with each symbol's last price,
change, % change, and a rounded one-month daily price history used to draw
sparklines on the site.

Run manually:
    pip install yfinance
    python generate_market_data.py

Run on a schedule via GitHub Actions — see
.github/workflows/update-market-data.yml
"""

import json
from datetime import datetime, timezone

import yfinance as yf

# Each entry is [symbol, display_name, decimals, unit]. `unit` is an
# optional suffix appended to the displayed price (e.g. "%" for bond
# yields) — leave as "" for plain index points / prices / FX rates.
WATCHLISTS = {
    "indices": [
        ["^GSPC", "S&P 500", 2, ""],
        ["^IXIC", "NASDAQ", 2, ""],
        ["^DJI", "DOW", 2, ""],
        ["^FTSE", "FTSE 100", 2, ""],
        ["^GDAXI", "DAX", 2, ""],
        ["^STI", "STI", 2, ""],
        ["000001.SS", "SHANGHAI", 2, ""],
        ["^HSI", "HANG SENG", 2, ""],
        ["^N225", "NIKKEI 225", 2, ""],
        ["^AXJO", "ASX 200", 2, ""],
    ],
    "bonds": [
        # 2Y has no CBOE treasury-yield index ticker on Yahoo; the CME
        # 2-Year Treasury Yield future (2YY=F) is used as a live proxy.
        ["2YY=F", "US 2Y", 2, "%"],
        ["^FVX", "US 5Y", 2, "%"],
        ["^TNX", "US 10Y", 2, "%"],
        ["^TYX", "US 30Y", 2, "%"],
    ],
    "commodities": [
        ["GC=F", "GOLD", 2, ""],
        ["SI=F", "SILVER", 2, ""],
        ["HG=F", "COPPER", 3, ""],
        ["CL=F", "WTI", 2, ""],
        ["BZ=F", "BRENT", 2, ""],
    ],
    "Forex": [
        ["EURUSD=X", "EUR/USD", 4, ""],
        ["GBPUSD=X", "GBP/USD", 4, ""],
        ["USDJPY=X", "USD/JPY", 2, ""],
        ["USDCHF=X", "USD/CHF", 4, ""],
        ["USDCAD=X", "USD/CAD", 4, ""],
        ["AUDUSD=X", "AUD/USD", 4, ""],
        ["NZDUSD=X", "NZD/USD", 4, ""],
        ["USDCNH=X", "USD/CNH", 4, ""],
        ["AUDCNY=X", "AUD/CNY", 4, ""],
        ["EURAUD=X", "EUR/AUD", 4, ""],
    ],
    # display "name" is always the real Yahoo Finance ticker symbol here —
    # no friendly nicknames (e.g. "QANTAS") — so it's directly usable to
    # look the instrument up on Yahoo. Australian names keep the .AX suffix.
    "equity": [
        ["AAPL", "AAPL", 2, ""],
        ["MSFT", "MSFT", 2, ""],
        ["GOOGL", "GOOGL", 2, ""],
        ["AMZN", "AMZN", 2, ""],
        ["META", "META", 2, ""],
        ["NVDA", "NVDA", 2, ""],
        ["AMD", "AMD", 2, ""],
        ["MU", "MU", 2, ""],
        ["AVGO", "AVGO", 2, ""],
        ["TSLA", "TSLA", 2, ""],
        ["PLTR", "PLTR", 2, ""],
        ["NFLX", "NFLX", 2, ""],
        ["GS", "GS", 2, ""],
        ["JPM", "JPM", 2, ""],
        ["MS", "MS", 2, ""],
        ["KO", "KO", 2, ""],
        ["MCD", "MCD", 2, ""],
        ["BRK-B", "BRK-B", 2, ""],
        ["V", "V", 2, ""],
        ["WMT", "WMT", 2, ""],
        # --- Australian (ASX) names below ---
        ["QAN.AX", "QAN.AX", 2, ""],
        ["CBA.AX", "CBA.AX", 2, ""],
        ["BHP.AX", "BHP.AX", 2, ""],
        ["CSL.AX", "CSL.AX", 2, ""],
        ["NAB.AX", "NAB.AX", 2, ""],
        ["WES.AX", "WES.AX", 2, ""],
    ],
    "other": [
        ["^VIX", "VIX", 2, ""],
        ["DX-Y.NYB", "DXY", 2, ""],
        ["^MOVE", "MOVE", 2, ""],
        ["^SKEW", "SKEW", 2, ""],
        ["BTC-USD", "BTC-USD", 2, ""],
    ],
}

# Geographic extent the world map SVG (assets/world-map.svg) was rendered
# at — must match the LON_MIN/MAX/LAT_MIN/MAX used in the map-generation
# script so the frontend's lat/lon -> percentage placement lines up with
# the image. Shipped in market_data.json so both sides read one source.
MAP_EXTENT = {"lon_min": -180, "lon_max": 180, "lat_min": -58, "lat_max": 83}

# Lat/lon of the exchange city behind each index symbol, used to place
# markers on the homepage's world map. Keep in sync with WATCHLISTS
# ["indices"] — an index not listed here just won't get a map marker.
# label_pos steers which side of the dot the text label is drawn on —
# Shanghai/Hong Kong/Tokyo (and London/Frankfurt) sit close together on
# the rendered map, so their labels are fanned out to avoid overlapping.
INDEX_LOCATIONS = {
    "^GSPC": {"city": "New York", "lat": 40.71, "lon": -74.01, "label_pos": "bottom"},
    "^IXIC": {"city": "New York", "lat": 40.71, "lon": -74.01, "label_pos": "bottom"},
    "^DJI": {"city": "New York", "lat": 40.71, "lon": -74.01, "label_pos": "bottom"},
    "^FTSE": {"city": "London", "lat": 51.51, "lon": -0.13, "label_pos": "bottom"},
    "^GDAXI": {"city": "Frankfurt", "lat": 50.11, "lon": 8.68, "label_pos": "right"},
    "^STI": {"city": "Singapore", "lat": 1.35, "lon": 103.82, "label_pos": "bottom"},
    "000001.SS": {"city": "Shanghai", "lat": 31.23, "lon": 121.47, "label_pos": "top"},
    "^HSI": {"city": "Hong Kong", "lat": 22.32, "lon": 114.17, "label_pos": "left"},
    "^N225": {"city": "Tokyo", "lat": 35.68, "lon": 139.65, "label_pos": "right"},
    "^AXJO": {"city": "Sydney", "lat": -33.87, "lon": 151.21, "label_pos": "bottom"},
}

# One month of daily closes is enough for a readable sparkline and works
# uniformly across indices, FX, futures, and equities — no need to handle
# intraday market-hours/timezone gaps.
HISTORY_PERIOD = "1mo"
HISTORY_INTERVAL = "1d"


def fetch_symbol(symbol, name, decimals, unit):
    """Same core calculation as macro_terminal.py's _fetch_worker
    (last close vs. previous close), extended with a price-history array."""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(
            period=HISTORY_PERIOD, interval=HISTORY_INTERVAL, auto_adjust=False
        )

        if hist is None or hist.empty or "Close" not in hist.columns:
            return {"symbol": symbol, "name": name, "ok": False}

        closes = hist["Close"].dropna()
        if len(closes) == 0:
            return {"symbol": symbol, "name": name, "ok": False}

        last_price = float(closes.iloc[-1])
        prev_close = float(closes.iloc[-2]) if len(closes) >= 2 else last_price
        chg = last_price - prev_close
        pct = (chg / prev_close) * 100 if prev_close else 0.0

        return {
            "symbol": symbol,
            "name": name,
            "decimals": decimals,
            "unit": unit,
            "ok": True,
            "last": round(last_price, decimals),
            "chg": round(chg, decimals),
            "pct": round(pct, 2),
            "history": [round(c, decimals) for c in closes.tolist()],
        }
    except Exception:
        return {"symbol": symbol, "name": name, "ok": False}


def main():
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "categories": {},
        "map_markers": [],
        "map_extent": MAP_EXTENT,
    }

    for category, symbols in WATCHLISTS.items():
        output["categories"][category] = [
            fetch_symbol(symbol, name, decimals, unit)
            for symbol, name, decimals, unit in symbols
        ]

    # Build map marker payload: one entry per exchange city, listing the
    # indices fetched above that trade there.
    by_symbol = {item["symbol"]: item for item in output["categories"]["indices"]}
    cities = {}
    for symbol, loc in INDEX_LOCATIONS.items():
        item = by_symbol.get(symbol)
        if item is None:
            continue
        key = loc["city"]
        if key not in cities:
            cities[key] = {
                "city": loc["city"],
                "lat": loc["lat"],
                "lon": loc["lon"],
                "label_pos": loc.get("label_pos", "bottom"),
                "indices": [],
            }
        cities[key]["indices"].append(
            {
                "name": item["name"],
                "ok": item["ok"],
                "pct": item.get("pct") if item["ok"] else None,
                "chg": item.get("chg") if item["ok"] else None,
                "last": item.get("last") if item["ok"] else None,
            }
        )
    output["map_markers"] = list(cities.values())

    with open("market_data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote market_data.json at {output['generated_at']}")


if __name__ == "__main__":
    main()

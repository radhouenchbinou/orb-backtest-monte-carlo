"""Scanner quotidien : classe une liste d'actions US liquides selon leur aptitude au day trading ORB.

Critères (sur données journalières) :
  - ATR 14 j en % du prix : il faut que l'action bouge assez pour couvrir les frais.
  - Volume relatif (dernier jour / moyenne 20 j) : l'intérêt du marché aujourd'hui.
  - Gap d'ouverture du dernier jour en %.
  - Tendance : cours au-dessus de la moyenne mobile 20 j et 50 j.
  - Filtres : prix >= 10 $, volume moyen >= 2 M actions.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from data import load

WATCHLIST = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "AMD", "NFLX", "AVGO",
    "PLTR", "COIN", "MSTR", "SMCI", "UBER", "SHOP", "CRWD", "SNOW", "BA", "JPM",
    "BAC", "XOM", "COST", "DIS", "INTC", "MU", "SOFI", "RIVN", "HOOD", "ARM",
    "SPY", "QQQ",
]


def score_ticker(df: pd.DataFrame) -> dict | None:
    if len(df) < 60:
        return None
    c, h, l, o, v = df["close"], df["high"], df["low"], df["open"], df["volume"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr_pct = tr.rolling(14).mean().iloc[-1] / c.iloc[-1] * 100
    avg_vol = v.rolling(20).mean().iloc[-2]
    rvol = v.iloc[-1] / avg_vol if avg_vol else np.nan
    gap = (o.iloc[-1] / c.iloc[-2] - 1) * 100
    sma20, sma50 = c.rolling(20).mean().iloc[-1], c.rolling(50).mean().iloc[-1]
    price = c.iloc[-1]
    if price < 10 or avg_vol < 2_000_000:
        return None
    trend = int(price > sma20) + int(price > sma50)
    score = min(atr_pct, 6) * 1.0 + min(rvol, 4) * 1.5 + min(abs(gap), 5) * 0.8 + trend * 0.5
    return {
        "date": str(df.index[-1].date()), "prix": round(float(price), 2), "ATR %": round(float(atr_pct), 2),
        "vol. relatif": round(float(rvol), 2), "gap %": round(float(gap), 2),
        "tendance (0-2)": trend, "score": round(float(score), 2),
    }


def scan(tickers=WATCHLIST, refresh=True, top=10) -> pd.DataFrame:
    rows = []
    for t in tickers:
        try:
            df = load(t, interval="1d", period="1y", refresh=refresh)
        except Exception as e:  # une action indisponible ne bloque pas le scan
            print(f"  ! {t}: {e}")
            continue
        s = score_ticker(df)
        if s:
            rows.append({"ticker": t, **s})
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values("score", ascending=False).head(top).reset_index(drop=True)

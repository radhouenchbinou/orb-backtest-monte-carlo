"""Génère des bougies 5 min SYNTHÉTIQUES (marche aléatoire) pour tester l'outil hors ligne.
Aucune valeur prédictive : une marche aléatoire n'a, par construction, aucun avantage exploitable."""
import numpy as np
import pandas as pd


def synthetic_intraday(days=60, start_price=360.0, seed=1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows, price = [], start_price
    for d in pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=days):
        price *= np.exp(rng.normal(0, 0.015))  # gap overnight
        ts = pd.date_range(d + pd.Timedelta(hours=9, minutes=30), periods=78, freq="5min",
                           tz="America/New_York")
        vol = 0.004 * np.r_[np.linspace(2, 1, 12), np.ones(54), np.linspace(1, 1.5, 12)]
        for t, s in zip(ts, vol):
            o = price
            c = o * np.exp(rng.normal(0, s))
            h = max(o, c) * (1 + abs(rng.normal(0, s / 2)))
            l = min(o, c) * (1 - abs(rng.normal(0, s / 2)))
            rows.append((t, o, h, l, c, int(rng.integers(2e5, 1e6))))
            price = c
    return pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"]).set_index("ts")

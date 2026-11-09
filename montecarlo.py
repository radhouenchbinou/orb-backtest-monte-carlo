"""Deux simulations Monte Carlo.

1. robustness() : rééchantillonne les trades du backtest pour voir la dispersion
   possible des résultats sur les N prochains trades (est-ce de la chance ?).
2. time_machine() : version honnête du « Time Machine » de la vidéo. À partir d'un
   plan (entrée/stop/objectif), rejoue des milliers de fins de séance en tirant
   au hasard des rendements 5 min HISTORIQUES de l'action, et compte combien
   touchent l'objectif avant le stop.  Ce n'est pas une prédiction : c'est la
   fréquence qu'on obtiendrait si le futur ressemblait au passé récent.
"""
import numpy as np
import pandas as pd

from data import regular_session


def robustness(r_values: np.ndarray, n_trades: int = 100, n_sims: int = 10000,
               risk_per_trade: float = 100.0, seed: int = 7) -> dict:
    rng = np.random.default_rng(seed)
    draws = rng.choice(r_values, size=(n_sims, n_trades), replace=True) * risk_per_trade
    equity = draws.cumsum(axis=1)
    final = equity[:, -1]
    dd = (equity - np.maximum.accumulate(equity, axis=1)).min(axis=1)
    return {
        "final": final,
        "summary": {
            f"P&L médian après {n_trades} trades ($)": round(np.median(final), 0),
            "scénario pessimiste 5 % ($)": round(np.percentile(final, 5), 0),
            "scénario optimiste 95 % ($)": round(np.percentile(final, 95), 0),
            "probabilité de finir en perte": f"{(final < 0).mean():.1%}",
            "drawdown médian ($)": round(np.median(dd), 0),
            "drawdown pire 5 % ($)": round(np.percentile(dd, 5), 0),
        },
    }


def time_machine(df: pd.DataFrame, entry: float, stop: float, target: float,
                 bars_left: int, n_sims: int = 10000, seed: int = 7) -> dict:
    """Simule `bars_left` bougies de 5 min après l'entrée (long si target > entry)."""
    s = regular_session(df)["close"]
    rets = np.log(s).diff()
    # on retire les sauts entre deux séances (overnight)
    same_day = pd.Series(s.index.date, index=s.index)
    rets = rets[same_day.eq(same_day.shift())].dropna().values
    rng = np.random.default_rng(seed)
    paths = entry * np.exp(rng.choice(rets, size=(n_sims, bars_left)).cumsum(axis=1))
    long = target > entry
    hit_t = (paths >= target) if long else (paths <= target)
    hit_s = (paths <= stop) if long else (paths >= stop)
    first_t = np.where(hit_t.any(1), hit_t.argmax(1), bars_left + 1)
    first_s = np.where(hit_s.any(1), hit_s.argmax(1), bars_left + 1)
    tgt_first = (first_t < first_s).mean()
    stop_first = (first_s < first_t).mean()
    return {
        "paths": paths,
        "closes": paths[:, -1],
        "summary": {
            "simulations": n_sims,
            "objectif touché en premier": f"{tgt_first:.1%}",
            "stop touché en premier": f"{stop_first:.1%}",
            "ni l'un ni l'autre avant la clôture": f"{1 - tgt_first - stop_first:.1%}",
            "clôture médiane simulée": round(float(np.median(paths[:, -1])), 2),
        },
    }

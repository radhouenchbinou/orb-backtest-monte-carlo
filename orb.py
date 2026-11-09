"""Stratégie Opening-Range Breakout (cassure de la fourchette d'ouverture) + backtest.

Règles (identiques au plan TSLA de la vidéo) :
  1. Fourchette d'ouverture = plus haut / plus bas des N premières minutes (15 par défaut).
  2. Entrée long  : première bougie 5 min qui CLÔTURE au-dessus du plus haut de la fourchette.
     Entrée short : première bougie qui clôture sous le plus bas (si --shorts).
  3. Stop = autre borne de la fourchette (ou milieu si stop_mode="mid").
  4. Objectif = entrée + R x risque (R = 1 par défaut).
  5. Pas d'entrée après `last_entry`. Sortie forcée à `flat_time` si ni stop ni objectif.
  6. Si stop et objectif sont touchés dans la même bougie, on compte le stop (prudent).
"""
from dataclasses import dataclass, asdict
from datetime import time

import numpy as np
import pandas as pd

from data import regular_session


@dataclass
class OrbParams:
    range_minutes: int = 15
    reward_r: float = 1.0
    stop_mode: str = "range"      # "range" (autre borne) | "mid" (milieu de la fourchette)
    last_entry: str = "11:30"
    flat_time: str = "15:55"
    allow_shorts: bool = False
    slippage: float = 0.02        # $ par action, appliqué à l'entrée ET à la sortie
    max_range_pct: float = 3.0    # ignore les jours où la fourchette dépasse X % du prix
    risk_per_trade: float = 100.0 # $ risqués par trade (sert au calcul de la taille)


@dataclass
class Trade:
    date: str
    side: str
    or_high: float
    or_low: float
    entry_time: str
    entry: float
    stop: float
    target: float
    exit_time: str
    exit: float
    reason: str
    r: float
    shares: int
    pnl: float


def _t(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def plan_day(day: pd.DataFrame, p: OrbParams):
    """Retourne (or_high, or_low) ou None si la journée est incomplète/inexploitable."""
    start = day.index[0].normalize() + pd.Timedelta(hours=9, minutes=30)
    end = start + pd.Timedelta(minutes=p.range_minutes)
    opening = day[(day.index >= start) & (day.index < end)]
    if len(opening) == 0 or day.index[0] > start + pd.Timedelta(minutes=5):
        return None
    hi, lo = opening["high"].max(), opening["low"].min()
    if (hi - lo) / lo * 100 > p.max_range_pct or hi <= lo:
        return None
    return hi, lo, end


def simulate_day(day: pd.DataFrame, p: OrbParams):
    plan = plan_day(day, p)
    if plan is None:
        return None
    hi, lo, end = plan
    after = day[day.index >= end]
    last_entry, flat = _t(p.last_entry), _t(p.flat_time)

    entry_i, side = None, None
    for i, (ts, bar) in enumerate(after.iterrows()):
        if ts.time() > last_entry:
            break
        if bar["close"] > hi:
            entry_i, side = i, "long"
            break
        if p.allow_shorts and bar["close"] < lo:
            entry_i, side = i, "short"
            break
    if entry_i is None:
        return None

    ts_in = after.index[entry_i]
    raw_entry = after.iloc[entry_i]["close"]
    mid = (hi + lo) / 2
    if side == "long":
        entry = raw_entry + p.slippage
        stop = lo if p.stop_mode == "range" else mid
        risk = entry - stop
        target = entry + p.reward_r * risk
    else:
        entry = raw_entry - p.slippage
        stop = hi if p.stop_mode == "range" else mid
        risk = stop - entry
        target = entry - p.reward_r * risk
    if risk <= 0:
        return None

    exit_px, reason, ts_out = None, None, None
    for ts, bar in after.iloc[entry_i + 1:].iterrows():
        if side == "long":
            hit_stop, hit_tgt = bar["low"] <= stop, bar["high"] >= target
        else:
            hit_stop, hit_tgt = bar["high"] >= stop, bar["low"] <= target
        if hit_stop:
            exit_px, reason, ts_out = stop, "stop", ts
            break
        if hit_tgt:
            exit_px, reason, ts_out = target, "target", ts
            break
        if ts.time() >= flat:
            exit_px, reason, ts_out = bar["close"], "close", ts
            break
    if exit_px is None:  # fin des données du jour
        ts_out, exit_px, reason = after.index[-1], after.iloc[-1]["close"], "close"

    exit_px = exit_px - p.slippage if side == "long" else exit_px + p.slippage
    move = exit_px - entry if side == "long" else entry - exit_px
    shares = max(int(p.risk_per_trade // risk), 1)
    return Trade(
        date=str(ts_in.date()), side=side, or_high=round(hi, 2), or_low=round(lo, 2),
        entry_time=ts_in.strftime("%H:%M"), entry=round(entry, 2), stop=round(stop, 2),
        target=round(target, 2), exit_time=ts_out.strftime("%H:%M"), exit=round(exit_px, 2),
        reason=reason, r=round(move / risk, 3), shares=shares, pnl=round(move * shares, 2),
    )


def backtest(df: pd.DataFrame, p: OrbParams) -> pd.DataFrame:
    df = regular_session(df)
    trades = []
    for _, day in df.groupby(df.index.date):
        t = simulate_day(day, p)
        if t:
            trades.append(asdict(t))
    return pd.DataFrame(trades)


def stats(trades: pd.DataFrame, n_days: int) -> dict:
    if trades.empty:
        return {"jours analysés": n_days, "trades": 0}
    r = trades["r"]
    wins, losses = r[r > 0], r[r <= 0]
    equity = trades["pnl"].cumsum()
    dd = (equity - equity.cummax()).min()
    pf = wins.sum() / -losses.sum() if losses.sum() < 0 else np.inf
    return {
        "jours analysés": n_days,
        "trades": len(trades),
        "taux de réussite": f"{len(wins) / len(r):.1%}",
        "gain moyen (R)": round(wins.mean(), 2) if len(wins) else 0,
        "perte moyenne (R)": round(losses.mean(), 2) if len(losses) else 0,
        "espérance par trade (R)": round(r.mean(), 3),
        "profit factor": round(pf, 2) if np.isfinite(pf) else "∞",
        "P&L total ($)": round(trades["pnl"].sum(), 2),
        "drawdown max ($)": round(dd, 2),
        "sorties stop / objectif / clôture": "{} / {} / {}".format(
            (trades.reason == "stop").sum(), (trades.reason == "target").sum(),
            (trades.reason == "close").sum()),
    }

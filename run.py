#!/usr/bin/env python3
"""Point d'entrée.

  python run.py                       # backtest TSLA (60 derniers jours) + Monte Carlo + Time Machine + scanner
  python run.py --ticker NVDA --shorts
  python run.py --no-scan --r 2 --stop mid
  python run.py --sample              # données synthétiques (test hors ligne)
"""
import argparse
import webbrowser
from pathlib import Path

import pandas as pd

import montecarlo
import report
from data import load, regular_session
from orb import OrbParams, backtest, stats


def verdict_text(st, mc, r=None) -> str:
    n = st.get("trades", 0)
    if n < 30:
        return (f"<b>Pas assez de trades ({n}) pour conclure.</b> Il en faut au moins "
                "30, idéalement 100+. Relancez chaque semaine : le cache accumule l'historique.")
    exp = st["espérance par trade (R)"]
    ploss = float(mc["summary"]["probabilité de finir en perte"].rstrip("%")) / 100
    t = exp / (r.std(ddof=1) / n ** 0.5) if r is not None and r.std() > 0 else 0
    if exp > 0 and (n < 100 or t < 2):
        return (f"<b>Non concluant</b> : espérance {exp:+.2f} R/trade sur {n} trades (t-stat {t:.1f}). "
                "Un tel résultat apparaît aussi sur des données purement aléatoires : il faut "
                "100+ trades et une t-stat ≥ 2 avant d'y croire. Pas d'argent réel.")
    if exp > 0.1 and ploss < 0.1:
        return (f"<b>Signal encourageant</b> : espérance {exp:+.2f} R/trade, {ploss:.0%} de scénarios "
                "perdants. Prochaine étape : paper trading pendant 4 à 8 semaines avant tout argent réel.")
    if exp > 0:
        return (f"<b>Légèrement positif mais fragile</b> : espérance {exp:+.2f} R/trade et "
                f"{ploss:.0%} de scénarios perdants. Pas d'argent réel ; testez d'autres réglages "
                "(--r, --stop, --range) et d'autres actions.")
    return (f"<b>Stratégie perdante sur cette période</b> : espérance {exp:+.2f} R/trade. "
            "À ne pas trader telle quelle.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", default="TSLA")
    ap.add_argument("--range", type=int, default=15, help="minutes de la fourchette d'ouverture")
    ap.add_argument("--r", type=float, default=1.0, help="objectif en multiple du risque")
    ap.add_argument("--stop", choices=["range", "mid"], default="range")
    ap.add_argument("--shorts", action="store_true")
    ap.add_argument("--risk", type=float, default=100.0, help="$ risqués par trade")
    ap.add_argument("--no-scan", action="store_true")
    ap.add_argument("--offline", action="store_true", help="n'utiliser que le cache local")
    ap.add_argument("--sample", action="store_true", help="données synthétiques de test")
    ap.add_argument("--no-open", action="store_true")
    a = ap.parse_args()

    p = OrbParams(range_minutes=a.range, reward_r=a.r, stop_mode=a.stop,
                  allow_shorts=a.shorts, risk_per_trade=a.risk)

    if a.sample:
        from make_sample import synthetic_intraday
        df = synthetic_intraday()
    else:
        print(f"Téléchargement {a.ticker} 5 min…")
        df = load(a.ticker, "5m", "60d", refresh=not a.offline)
    n_days = len(set(regular_session(df).index.date))

    trades = backtest(df, p)
    st = stats(trades, n_days)
    print(pd.Series(st).to_string())

    mc = None
    if len(trades) >= 5:
        mc = montecarlo.robustness(trades["r"].values, n_trades=100, risk_per_trade=a.risk)
        mc["n"] = 100

    tm, plan = None, None
    if not trades.empty:
        last = trades.iloc[-1]
        plan = last[["date", "entry", "stop", "target"]].to_dict()
        h, m = map(int, last["entry_time"].split(":"))
        bars_left = max(int(((15 * 60 + 55) - (h * 60 + m)) / 5), 1)
        tm = montecarlo.time_machine(df, last["entry"], last["stop"], last["target"], bars_left)

    scan_df = None
    if not a.no_scan and not a.sample:
        import scanner
        print("Scanner…")
        scan_df = scanner.scan(refresh=not a.offline)

    out = Path(__file__).parent / "reports"
    out.mkdir(exist_ok=True)
    tag = "SAMPLE" if a.sample else a.ticker.upper()
    path = out / f"orb_{tag}.html"
    path.write_text(report.build(tag, p, st, trades, mc, tm, plan, scan_df,
                                 verdict_text(st, mc, trades["r"]) if mc else verdict_text(st, {"summary": {"probabilité de finir en perte": "100%"}}),
                                 sample=a.sample), encoding="utf-8")
    if not trades.empty:
        trades.to_csv(out / f"trades_{tag}.csv", index=False)
    print(f"\nRapport : {path}")
    if not a.no_open:
        webbrowser.open(path.resolve().as_uri())


if __name__ == "__main__":
    main()

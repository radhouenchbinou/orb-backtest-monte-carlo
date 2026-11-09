"""Rapport HTML autonome (graphiques intégrés en base64)."""
import base64
import html
import io
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BLUE, RED, GREEN, GREY = "#2f6fdb", "#d1495b", "#2a9d8f", "#8a8f98"


def _img(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    return f'<img src="data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}">'


def _style(ax, title):
    ax.set_title(title, loc="left", fontsize=11, fontweight="bold")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="y", alpha=0.25)


def equity_chart(trades):
    fig, ax = plt.subplots(figsize=(8, 3))
    eq = trades["pnl"].cumsum()
    ax.plot(range(1, len(eq) + 1), eq.values, color=BLUE, lw=2)
    ax.fill_between(range(1, len(eq) + 1), eq.values, 0, color=BLUE, alpha=0.08)
    ax.axhline(0, color=GREY, lw=0.8)
    ax.set_xlabel("n° de trade"); ax.set_ylabel("$")
    _style(ax, "Courbe de capital (P&L cumulé)")
    return _img(fig)


def r_hist(trades):
    fig, ax = plt.subplots(figsize=(8, 2.6))
    r = trades["r"]
    bins = np.linspace(min(-1.5, r.min()), max(1.5, r.max()), 25)
    ax.hist(r[r <= 0], bins=bins, color=RED, alpha=0.85, label="pertes")
    ax.hist(r[r > 0], bins=bins, color=GREEN, alpha=0.85, label="gains")
    ax.set_xlabel("résultat en R (1 R = montant risqué)")
    ax.legend(frameon=False)
    _style(ax, "Distribution des résultats par trade")
    return _img(fig)


def mc_hist(final, n):
    fig, ax = plt.subplots(figsize=(8, 2.6))
    ax.hist(final, bins=60, color=BLUE, alpha=0.85)
    ax.axvline(0, color=RED, lw=1.2)
    ax.set_xlabel(f"P&L après {n} trades ($)")
    _style(ax, "Monte Carlo : 10 000 futurs possibles avec les mêmes statistiques")
    return _img(fig)


def tm_chart(tm, plan):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9, 3), gridspec_kw={"width_ratios": [1.4, 1]})
    for p in tm["paths"][:150]:
        a1.plot(p, color=BLUE, alpha=0.08, lw=0.8)
    for lvl, c, lab in ((plan["target"], GREEN, "objectif"), (plan["entry"], GREY, "entrée"),
                        (plan["stop"], RED, "stop")):
        a1.axhline(lvl, color=c, lw=1.2, ls="--", label=f"{lab} {lvl:.2f}")
        a2.axvline(lvl, color=c, lw=1.2, ls="--")
    a1.legend(frameon=False, fontsize=8); a1.set_xlabel("bougies de 5 min après l'entrée")
    _style(a1, "Time Machine : 150 trajectoires")
    a2.hist(tm["closes"], bins=40, color=RED, alpha=0.8)
    _style(a2, "Clôtures simulées")
    return _img(fig)


def table(d: dict) -> str:
    rows = "".join(f"<tr><th>{html.escape(str(k))}</th><td>{html.escape(str(v))}</td></tr>"
                   for k, v in d.items())
    return f'<table class="kv">{rows}</table>'


def df_table(df: pd.DataFrame) -> str:
    return df.to_html(index=False, classes="grid", border=0)


CSS = """
body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:900px;margin:32px auto;padding:0 16px;color:#1d2230;background:#fbfbfd}
h1{font-size:24px;margin-bottom:4px} h2{font-size:17px;margin-top:36px;border-bottom:1px solid #e3e5ea;padding-bottom:6px}
.sub{color:#6b7180;font-size:13px} img{max-width:100%;margin:8px 0}
.warn{background:#fff6e5;border:1px solid #f1d39a;padding:10px 14px;border-radius:8px;font-size:13px}
.verdict{background:#eef4ff;border:1px solid #c9dafb;padding:12px 16px;border-radius:8px}
table{border-collapse:collapse;font-size:13px;margin:8px 0} .kv th{text-align:left;color:#6b7180;font-weight:500;padding:4px 18px 4px 0}
.kv td{font-weight:600} .grid th,.grid td{padding:4px 8px;border-bottom:1px solid #eceef2;text-align:right}
.grid th{background:#f2f3f6} .scroll{max-height:340px;overflow:auto}
"""


def build(ticker, params, st, trades, mc, tm, plan, scan_df, verdict, sample=False) -> str:
    parts = [f"<!doctype html><html lang='fr'><meta charset='utf-8'><title>Trader {ticker}</title>"
             f"<style>{CSS}</style><body>",
             f"<h1>Backtest ORB — {html.escape(ticker)}</h1>",
             f"<div class='sub'>Généré le {datetime.now():%d/%m/%Y %H:%M} · bougies 5 min · "
             f"fourchette {params.range_minutes} min · objectif {params.reward_r} R · stop {params.stop_mode}</div>"]
    if sample:
        parts.append("<p class='warn'><b>DONNÉES DE TEST SYNTHÉTIQUES.</b> Ces chiffres ne disent "
                     "rien du vrai marché : ils servent uniquement à vérifier que l'outil fonctionne.</p>")
    parts.append(f"<div class='verdict'>{verdict}</div>")
    parts.append("<h2>1. Résultats du backtest</h2>" + table(st))
    if not trades.empty:
        parts += [equity_chart(trades), r_hist(trades)]
    if mc:
        parts.append("<h2>2. Robustesse (Monte Carlo sur les trades)</h2>" + table(mc["summary"])
                     + mc_hist(mc["final"], mc["n"]))
    if tm:
        parts.append("<h2>3. Time Machine sur le dernier plan</h2>"
                     f"<p class='sub'>Plan du {plan['date']} : entrée {plan['entry']} · stop {plan['stop']} · "
                     f"objectif {plan['target']}. Trajectoires tirées des rendements 5 min historiques.</p>"
                     + table(tm["summary"]) + tm_chart(tm, plan))
    if scan_df is not None and not scan_df.empty:
        parts.append("<h2>4. Scanner — meilleurs candidats ORB</h2>" + df_table(scan_df))
    if not trades.empty:
        parts.append("<h2>5. Journal des trades</h2><div class='scroll'>" + df_table(trades) + "</div>")
    parts.append("<p class='warn'>Backtest sur données passées, glissement estimé, sans commissions "
                 "ni impact de marché. Les performances passées ne préjugent pas des performances "
                 "futures. Ceci n'est pas un conseil en investissement.</p></body></html>")
    return "\n".join(parts)

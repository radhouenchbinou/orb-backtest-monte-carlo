# Trader — ORB backtest, Monte Carlo, Time Machine, scanner

## Installation (une fois, dans le Terminal du Mac)
```bash
cd orb-backtest-monte-carlo
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Utilisation
```bash
source .venv/bin/activate
python run.py                          # TSLA, réglages de la vidéo (fourchette 15 min, 1 R, stop = bas de fourchette)
python run.py --ticker NVDA --shorts   # autre action, long + short
python run.py --r 2 --stop mid         # objectif 2 R, stop au milieu de la fourchette
python run.py --range 30 --no-scan     # fourchette 30 min, sans scanner
python run.py --sample                 # test hors ligne sur données synthétiques
```
Le rapport HTML s'ouvre tout seul (`reports/orb_TSLA.html`) et le journal des trades est dans `reports/trades_TSLA.csv`.

## À savoir
- Yahoo ne fournit que **60 jours** de bougies 5 min. Le cache `data/` fusionne chaque téléchargement :
  relancez une fois par semaine pour accumuler un historique plus long.
- Le verdict n'est « encourageant » qu'avec 100+ trades et une t-stat ≥ 2. En dessous, un résultat
  positif peut être pure chance (vérifié : une marche aléatoire produit parfois +0,17 R sur 50 trades).
- Glissement de 0,02 $/action à l'entrée et à la sortie ; commissions non incluses.
- Stop et objectif touchés dans la même bougie → compté comme stop (hypothèse prudente).

## Fichiers
| fichier | rôle |
|---|---|
| `data.py` | téléchargement yfinance + cache CSV, heure de New York |
| `orb.py` | règles de la stratégie et backtest jour par jour |
| `montecarlo.py` | robustesse (rééchantillonnage des trades) et Time Machine (trajectoires intraday) |
| `scanner.py` | classement d'une watchlist par ATR %, volume relatif, gap, tendance |
| `report.py` | rapport HTML avec graphiques |
| `make_sample.py` | données synthétiques pour tester sans internet |

Backtest sur données passées : ce n'est pas un conseil en investissement.

## Licence

MIT

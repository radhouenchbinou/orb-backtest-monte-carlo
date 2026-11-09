"""Chargement des données de marché (Yahoo Finance via yfinance) avec cache CSV local."""
from pathlib import Path

import pandas as pd

CACHE = Path(__file__).parent / "data"
NY = "America/New_York"


def _cache_path(ticker: str, interval: str) -> Path:
    return CACHE / f"{ticker.upper()}_{interval}.csv"


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
    df = df.dropna()
    idx = pd.to_datetime(df.index, utc=True)
    df.index = idx.tz_convert(NY)
    return df.sort_index()


def load(ticker: str, interval: str = "5m", period: str = "60d", refresh: bool = False) -> pd.DataFrame:
    """Retourne les bougies OHLCV en heure de New York.

    Les nouvelles données sont fusionnées avec le cache : relancer chaque semaine
    permet d'accumuler un historique intraday au-delà des 60 jours de Yahoo.
    """
    CACHE.mkdir(exist_ok=True)
    path = _cache_path(ticker, interval)
    cached = None
    if path.exists():
        cached = pd.read_csv(path, index_col=0)
        cached.index = pd.to_datetime(cached.index, utc=True).tz_convert(NY)
        if not refresh:
            return cached

    import yfinance as yf  # import tardif : inutile si on lit le cache

    fresh = yf.download(ticker, period=period, interval=interval, progress=False,
                        auto_adjust=False, prepost=False)
    if fresh.empty:
        if cached is not None:
            return cached
        raise RuntimeError(f"Aucune donnée pour {ticker} ({interval}, {period}). Connexion internet ?")
    fresh = _normalize(fresh)
    df = fresh if cached is None else pd.concat([cached, fresh])
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df.to_csv(path)
    return df


def regular_session(df: pd.DataFrame) -> pd.DataFrame:
    """Garde uniquement la séance régulière 9:30-16:00 ET."""
    return df.between_time("09:30", "15:59")

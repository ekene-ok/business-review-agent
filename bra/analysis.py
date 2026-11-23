"""Turn the weekly table into facts: headline KPIs, anomalies and the drivers behind them."""
from dataclasses import dataclass
import numpy as np
import pandas as pd
from .data import METRICS

LABEL = {"new_arr": "New ARR", "pipeline_created": "Pipeline created",
         "churned_arr": "Churned ARR", "active_accounts": "Active accounts"}
MONEY = {"new_arr", "pipeline_created", "churned_arr"}
# Direction that is bad news for each metric (used to word findings and set priority).
BAD_DIRECTION = {"new_arr": -1, "pipeline_created": -1, "churned_arr": +1, "active_accounts": -1}
Z_FLAG, Z_HIGH_CONFIDENCE, LOOKBACK = 3.5, 5.0, 12


@dataclass
class Anomaly:
    segment: str
    region: str
    metric: str
    value: float
    baseline: float        # expected value from the 12-week trend
    change: float          # fractional change vs expected
    z: float               # robust z-score
    share_of_total_change: float
    is_bad_news: bool
    confidence: str        # "high" or "review"


def headline(df: pd.DataFrame) -> pd.DataFrame:
    """Company totals for the latest week vs last week and vs the 4-week average."""
    tot = df.groupby("week")[METRICS].sum().sort_index()
    last, prev = tot.iloc[-1], tot.iloc[-2]
    avg4 = tot.iloc[-5:-1].mean()
    return pd.DataFrame({"metric": METRICS, "latest": last.values, "previous": prev.values,
                         "vs_last_week": (last / prev - 1).values, "vs_4wk_avg": (last / avg4 - 1).values})


def detect(df: pd.DataFrame) -> list[Anomaly]:
    """Flag cells whose latest week is far from expected.

    Expected value: a linear trend fitted to the previous 12 weeks of that cell, so steady
    growth is not mistaken for a spike. Normal variation: the median absolute deviation (MAD)
    of trend residuals, scaled to standard-deviation units. Twelve points give a noisy MAD,
    so each cell's scale is floored at the typical relative scale for that metric across all
    cells (cells share the same reporting noise). Score = robust z of the latest week.
    """
    weeks = sorted(df["week"].unique())
    last = weeks[-1]
    hist_weeks = weeks[-1 - LOOKBACK:-1]
    hist = df[df["week"].isin(hist_weeks)]
    cur = df[df["week"] == last]
    t = np.arange(len(hist_weeks))

    fits = {}
    for (seg, reg), h in hist.groupby(["segment", "region"]):
        h = h.set_index("week").reindex(hist_weeks)
        for m in METRICS:
            y = h[m].to_numpy(float)
            ok = ~np.isnan(y)
            if ok.sum() < 6:
                continue
            slope, icpt = np.polyfit(t[ok], y[ok], 1)
            resid = y[ok] - (slope * t[ok] + icpt)
            expected = slope * len(hist_weeks) + icpt
            mad = float(np.median(np.abs(resid - np.median(resid)))) * 1.4826
            fits[(seg, reg, m)] = (expected, mad, float(np.nanmedian(y)))
    pooled = {m: np.median([f[1] / f[2] for k, f in fits.items() if k[2] == m and f[2] > 0]) for m in METRICS}

    totals_prev = df[df["week"] == weeks[-2]][METRICS].sum()
    totals_last = cur[METRICS].sum()
    found = []
    for (seg, reg, m), (expected, mad, level) in fits.items():
        c = cur[(cur["segment"] == seg) & (cur["region"] == reg)]
        if c.empty:
            continue
        x = float(c[m].iloc[0])
        # Prediction-interval correction: projecting a fitted trend one week ahead adds
        # uncertainty on top of week-to-week noise (standard regression result).
        n = len(t)
        pi_factor = np.sqrt(1 + 1 / n + (n - t.mean()) ** 2 / ((t - t.mean()) ** 2).sum())
        scale = max(mad, pooled[m] * level) * pi_factor
        if scale <= 0:
            continue
        z = (x - expected) / scale
        if abs(z) < Z_FLAG:
            continue
        total_change = float(totals_last[m] - totals_prev[m])
        prev_cell = df[(df["week"] == weeks[-2]) & (df["segment"] == seg) & (df["region"] == reg)][m]
        cell_change = x - float(prev_cell.iloc[0]) if len(prev_cell) else np.nan
        share = cell_change / total_change if total_change else np.nan
        found.append(Anomaly(seg, reg, m, x, expected, x / expected - 1, z, share,
                             np.sign(z) == BAD_DIRECTION[m],
                             "high" if abs(z) >= Z_HIGH_CONFIDENCE else "review"))
    return sorted(found, key=lambda a: -abs(a.z))

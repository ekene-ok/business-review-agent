"""Synthetic weekly metrics for a B2B SaaS company, plus scenario injection for evaluation.

Each row is one week x segment x region. Scenarios inject a known problem into the latest
week (a metric drop, a churn spike, missing rows, duplicate rows) or leave it clean, so the
agent's output can be scored against ground truth.
"""
from dataclasses import dataclass, field
import numpy as np
import pandas as pd

SEGMENTS = ["SMB", "Mid-Market", "Enterprise"]
REGIONS = ["North America", "EMEA"]
METRICS = ["new_arr", "pipeline_created", "churned_arr", "active_accounts"]
BASE = {  # weekly baseline per segment (North America); EMEA is 60% of NA
    "SMB":        {"new_arr": 42_000, "pipeline_created": 160_000, "churned_arr": 9_000,  "active_accounts": 4_200},
    "Mid-Market": {"new_arr": 65_000, "pipeline_created": 260_000, "churned_arr": 8_000,  "active_accounts": 950},
    "Enterprise": {"new_arr": 90_000, "pipeline_created": 420_000, "churned_arr": 6_000,  "active_accounts": 140},
}
NOISE = {"new_arr": 0.06, "pipeline_created": 0.06, "churned_arr": 0.08, "active_accounts": 0.005}


@dataclass
class Scenario:
    kind: str                      # "drop", "spike", "missing_rows", "duplicate_rows", "clean"
    segment: str | None = None
    region: str | None = None
    metric: str | None = None
    magnitude: float = 0.0         # fractional change applied, e.g. -0.35
    notes: dict = field(default_factory=dict)


def generate(weeks: int = 26, seed: int = 0, end: str = "2026-11-16") -> pd.DataFrame:
    """Clean weekly history with mild growth and noise."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range(end=end, periods=weeks, freq="W-MON")
    rows = []
    for t, d in enumerate(dates):
        growth = 1 + 0.004 * t
        for seg in SEGMENTS:
            for reg in REGIONS:
                scale = 1.0 if reg == "North America" else 0.6
                row = {"week": d, "segment": seg, "region": reg}
                for m in METRICS:
                    g = growth if m != "churned_arr" else 1.0
                    v = BASE[seg][m] * scale * g * (1 + rng.normal(0, NOISE[m]))
                    row[m] = round(v) if m != "active_accounts" else int(round(v))
                rows.append(row)
    return pd.DataFrame(rows)


def inject(df: pd.DataFrame, sc: Scenario) -> pd.DataFrame:
    """Apply a scenario to the latest week. Returns a new frame."""
    df = df.copy()
    last = df["week"].max()
    cell = (df["week"] == last) & (df["segment"] == sc.segment) & (df["region"] == sc.region)
    if sc.kind in ("drop", "spike"):
        df.loc[cell, sc.metric] = (df.loc[cell, sc.metric] * (1 + sc.magnitude)).round()
    elif sc.kind == "missing_rows":
        df = df[~cell]
    elif sc.kind == "duplicate_rows":
        df = pd.concat([df, df[cell]], ignore_index=True)
    return df


def random_scenarios(n: int, seed: int = 123) -> list[Scenario]:
    """A balanced evaluation set: drops, churn spikes, data problems and clean weeks."""
    rng = np.random.default_rng(seed)
    kinds = ["drop"] * 4 + ["spike"] * 2 + ["missing_rows", "duplicate_rows"] + ["clean"] * 2
    out = []
    for i in range(n):
        kind = kinds[i % len(kinds)]
        seg, reg = rng.choice(SEGMENTS), rng.choice(REGIONS)
        if kind == "drop":
            m = rng.choice(["new_arr", "pipeline_created"])
            out.append(Scenario(kind, seg, reg, m, -float(rng.uniform(0.10, 0.50))))
        elif kind == "spike":
            out.append(Scenario(kind, seg, reg, "churned_arr", float(rng.uniform(0.20, 1.50))))
        elif kind in ("missing_rows", "duplicate_rows"):
            out.append(Scenario(kind, seg, reg))
        else:
            out.append(Scenario("clean"))
    return out

"""Data quality checks. A review is only as trustworthy as its inputs, so these run first.

Blocking issues stop the numbers from being presented as final; warnings are shown to the
reader alongside the draft.
"""
import pandas as pd
from .data import METRICS


def run_checks(df: pd.DataFrame) -> list[dict]:
    issues = []
    last = df["week"].max()
    expected = df[df["week"] < last].groupby(["segment", "region"]).size().index
    latest = df[df["week"] == last]

    # 1. Missing cells in the latest week (a segment x region that reported before but not now).
    have = set(map(tuple, latest[["segment", "region"]].drop_duplicates().to_numpy()))
    for seg, reg in expected:
        if (seg, reg) not in have:
            issues.append({"severity": "blocking", "check": "missing_rows", "segment": seg, "region": reg,
                           "message": f"No data for {seg} / {reg} in the week of {last:%d %b %Y}."})

    # 2. Duplicate rows (double-counted cells inflate every total).
    dup = latest[latest.duplicated(["week", "segment", "region"], keep=False)]
    for (seg, reg), _ in dup.groupby(["segment", "region"]):
        issues.append({"severity": "blocking", "check": "duplicate_rows", "segment": seg, "region": reg,
                       "message": f"Duplicate rows for {seg} / {reg} in the week of {last:%d %b %Y}."})

    # 3. Impossible values.
    for m in METRICS:
        bad = latest[latest[m] < 0]
        for _, r in bad.iterrows():
            issues.append({"severity": "blocking", "check": "negative_value", "segment": r["segment"],
                           "region": r["region"], "message": f"Negative {m} for {r['segment']} / {r['region']}."})

    # 4. Stale data: the latest week should follow the previous one by 7 days.
    weeks = sorted(df["week"].unique())
    if len(weeks) >= 2 and (pd.Timestamp(weeks[-1]) - pd.Timestamp(weeks[-2])).days != 7:
        issues.append({"severity": "warning", "check": "week_gap", "segment": None, "region": None,
                       "message": "Gap between the last two reporting weeks; history may be incomplete."})
    return issues

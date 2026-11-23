"""Evaluation harness: run the agent on 60 scenarios with known injected problems.

Each scenario uses fresh random history (its own seed) and injects one of:
metric drop (10% to 50%), churn spike (+20% to +150%), missing rows, duplicate rows,
or nothing (clean week). The agent's output is scored against what was injected.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from bra.data import generate, inject, random_scenarios
from bra.agent import run

ROOT = Path(__file__).resolve().parents[1]
N = 60
rows = []
for i, sc in enumerate(random_scenarios(N)):
    review = run(inject(generate(seed=1000 + i), sc))
    flags = [(a.segment, a.region, a.metric) for a in review.context.anomalies]
    issues = [(x["check"], x["segment"], x["region"]) for x in review.context.issues]
    if sc.kind in ("drop", "spike"):
        caught = (sc.segment, sc.region, sc.metric) in flags
        false_flags = len([f for f in flags if f != (sc.segment, sc.region, sc.metric)]) + len(issues)
    elif sc.kind in ("missing_rows", "duplicate_rows"):
        caught = (sc.kind, sc.segment, sc.region) in issues and review.provisional
        false_flags = len(flags) + len([x for x in issues if x != (sc.kind, sc.segment, sc.region)])
    else:
        caught = None
        false_flags = len(flags) + len(issues)
    rows.append({"scenario": i, "kind": sc.kind, "segment": sc.segment, "region": sc.region,
                 "metric": sc.metric, "magnitude": round(sc.magnitude, 3), "caught": caught,
                 "false_flags": false_flags, "verified": review.verified, "provisional": review.provisional})

res = pd.DataFrame(rows)
res.to_csv(ROOT / "results" / "evaluation_scenarios.csv", index=False)

problems = res[res["kind"] != "clean"]
size_band = pd.cut(problems["magnitude"].abs(), [0, 0.2, 0.3, 0.5, 2.0],
                   labels=["10% to 20%", "20% to 30%", "30% to 50%", "Over 50%"])
by_kind = (problems.groupby("kind")["caught"].agg(["sum", "count"])
           .rename(columns={"sum": "caught", "count": "scenarios"}).reset_index())
by_kind["detection_rate"] = (by_kind["caught"] / by_kind["scenarios"]).round(3)
by_kind.to_csv(ROOT / "results" / "detection_by_type.csv", index=False)
metric_problems = problems[problems["kind"].isin(["drop", "spike"])].copy()
metric_problems["size"] = size_band[metric_problems.index]
by_size = (metric_problems.groupby("size", observed=True)["caught"].agg(["sum", "count"])
           .rename(columns={"sum": "caught", "count": "scenarios"}).reset_index())
by_size["detection_rate"] = (by_size["caught"] / by_size["scenarios"]).round(3)
by_size.to_csv(ROOT / "results" / "detection_by_size.csv", index=False)

total_true = int(problems["caught"].sum())
total_flags = total_true + int(res["false_flags"].sum())
summary = pd.DataFrame([
    {"measure": "Scenarios", "value": N},
    {"measure": "Problems injected", "value": len(problems)},
    {"measure": "Problems caught", "value": total_true},
    {"measure": "Detection rate (recall)", "value": round(total_true / len(problems), 3)},
    {"measure": "Precision (correct flags / all flags)", "value": round(total_true / total_flags, 3)},
    {"measure": "False flags on clean weeks", "value": int(res.loc[res["kind"] == "clean", "false_flags"].sum())},
    {"measure": "Drafts passing number verification", "value": f"{int(res['verified'].sum())} of {N}"},
    {"measure": "Data problems marked provisional", "value": f"{int(res.loc[res['kind'].isin(['missing_rows','duplicate_rows']), 'provisional'].sum())} of {int(res['kind'].isin(['missing_rows','duplicate_rows']).sum())}"},
])
summary.to_csv(ROOT / "results" / "evaluation_summary.csv", index=False)
print(summary.to_string(index=False))
print(by_kind.to_string(index=False))
print(by_size.to_string(index=False))
print(res[(res["caught"] == False)].to_string(index=False))
print("false flags:", res[res.false_flags > 0][["scenario","kind","false_flags"]].to_string(index=False))

# Threshold sweep: the alert threshold trades missed problems against false alarms.
import bra.analysis as an
sweep = []
for zt in [2.5, 3.0, 3.5, 4.0, 5.0]:
    an.Z_FLAG = zt
    tp = fp = 0
    for i, sc in enumerate(random_scenarios(N)):
        if sc.kind not in ("drop", "spike", "clean"):
            continue
        flags = [(a.segment, a.region, a.metric) for a in an.detect(inject(generate(seed=1000 + i), sc))]
        hit = sc.kind != "clean" and (sc.segment, sc.region, sc.metric) in flags
        tp += hit
        fp += len(flags) - hit
    n_metric = sum(sc.kind in ("drop", "spike") for sc in random_scenarios(N))
    sweep.append({"z_threshold": zt, "recall": round(tp / n_metric, 3),
                  "precision": round(tp / (tp + fp), 3) if tp + fp else None, "false_alarms": fp})
an.Z_FLAG = 3.5
pd.DataFrame(sweep).to_csv(ROOT / "results" / "threshold_sweep.csv", index=False)
print(pd.DataFrame(sweep).to_string(index=False))

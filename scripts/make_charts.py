"""README chart: one message, one highlight colour, direct labels."""
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent))
import brand_style as b

ROOT = Path(__file__).resolve().parents[1]
RES, OUT = ROOT / "results", ROOT / "charts"
OUT.mkdir(exist_ok=True)
SURFACE, INK, INK2 = "#ffffff", b.INK, b.MUTED
HIGHLIGHT, CONTEXT = b.PROJECT["business-review-agent"], b.CONTEXT
plt.rcParams.update({"font.family": "sans-serif", "font.size": 11, "text.color": INK,
                     "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})

d = pd.read_csv(RES / "detection_by_size.csv")
hi = d["size"].isin(["30% to 50%", "Over 50%"])
fig, ax = plt.subplots(figsize=(9, 5.0))
ax.bar(d["size"], d["detection_rate"] * 100, width=0.6, color=[HIGHLIGHT if h else CONTEXT for h in hi])
for x, (rate, c, n, h) in enumerate(zip(d["detection_rate"], d["caught"], d["scenarios"], hi)):
    ax.text(x, rate * 100 + 2.5, f"{c} of {n}", ha="center", fontsize=12 if h else 11, color=INK if h else INK2)
for s in ax.spines.values():
    s.set_visible(False)
ax.set_yticks([])
ax.set_ylim(0, 115)
ax.tick_params(axis="x", length=0, pad=6, labelsize=11)
ax.set_xlabel("Size of the injected change", color=INK2, labelpad=8)
fig.text(0.03, 0.97, "The agent catches every problem of 30% or more", fontsize=15, va="top")
fig.text(0.03, 0.89, "Share of injected metric drops and churn spikes the agent flagged, across 36 test\n"
         "scenarios. Smaller changes sit inside normal weekly noise and are not alerted.",
         fontsize=10.5, color=INK2, va="top")
fig.subplots_adjust(left=0.03, right=0.97, top=0.73, bottom=0.2)
b.source(fig, "Evaluation harness, 60 generated scenarios")
fig.savefig(OUT / "01_detection_by_size.png", dpi=200)
plt.close(fig)
print("Chart saved to charts/")

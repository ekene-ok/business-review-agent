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
HL = b.PROJECT["business-review-agent"]
d = pd.read_csv(RES / "detection_by_size.csv")
fig, ax = b.chart(height=4.3, label_in=0.0, xaxis=True, right_in=0.3)
b.vbar(ax, d["size"].tolist(), (d.detection_rate * 100).tolist(),
       {i for i, s_ in enumerate(d["size"]) if s_ in ("30% to 50%", "Over 50%")},
       [f"{c} of {n}" for c, n in zip(d.caught, d.scenarios)], HL, ymax=100)
ax.set_xlabel("Size of the injected change", color=b.MUTED, fontsize=9.5)
b.titles(fig, "The agent catches every problem of 30% or more",
         "Injected metric drops and churn spikes flagged. Smaller changes sit inside weekly noise")
b.credit(fig, "Evaluation harness, 60 generated scenarios")
b.save(fig, OUT / "01_detection_by_size.png")
print("Chart saved to charts/")

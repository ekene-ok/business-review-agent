"""Generate a demo dataset with one injected problem and write a sample review."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bra.data import generate, inject, Scenario
from bra.agent import run

ROOT = Path(__file__).resolve().parents[1]
df = inject(generate(seed=7), Scenario("drop", "Enterprise", "EMEA", "pipeline_created", -0.38))
df = inject(df, Scenario("spike", "SMB", "North America", "churned_arr", 0.9))
review = run(df)
(ROOT / "sample_output").mkdir(exist_ok=True)
(ROOT / "sample_output" / "weekly_review_example.md").write_text(review.draft)
df.to_csv(ROOT / "sample_output" / "example_input_metrics.csv", index=False)
print(review.draft)
print("\n".join(review.log))

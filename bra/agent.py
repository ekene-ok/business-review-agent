"""The agent: check data, analyse, draft, verify, and decide what needs a human.

Steps run in a fixed order so every review is reproducible and auditable:
  1. run_checks   data quality (blocking issues make the review provisional)
  2. headline     company totals vs last week and the 4-week average
  3. detect       anomalies by segment and region, with drivers and confidence
  4. writer       draft the review (template, or optional language model)
  5. verify       reject any draft containing a number the analysis did not produce
"""
from dataclasses import dataclass, field
import pandas as pd
from .checks import run_checks
from .analysis import headline, detect, Anomaly
from .formatting import Registry
from .verify import verify
from .writer import TemplateWriter


@dataclass
class Context:
    week: pd.Timestamp
    issues: list
    headline: pd.DataFrame
    anomalies: list[Anomaly]
    registry: Registry = field(default_factory=Registry)


@dataclass
class Review:
    draft: str
    writer_used: str
    verified: bool
    unknown_numbers: list
    provisional: bool
    context: Context
    log: list


def run(df: pd.DataFrame, writer=None) -> Review:
    log = []
    issues = run_checks(df)
    log.append(f"checks: {len(issues)} issue(s)")
    clean = df.drop_duplicates(["week", "segment", "region"])
    ctx = Context(week=clean["week"].max(), issues=issues, headline=headline(clean), anomalies=detect(clean))
    log.append(f"anomalies: {len(ctx.anomalies)}")

    writer = writer or TemplateWriter()
    try:
        draft = writer.write(ctx)
    except Exception as exc:  # a failing external service must not block the review
        log.append(f"writer '{writer.name}' failed ({exc}); using template")
        writer, draft = TemplateWriter(), TemplateWriter().write(ctx)
    ok, unknown = verify(draft, ctx.registry.allowed)
    if not ok and writer.name != "template":
        log.append(f"verification failed for '{writer.name}' (unknown numbers: {unknown}); using template")
        writer = TemplateWriter()
        draft = writer.write(ctx)
        ok, unknown = verify(draft, ctx.registry.allowed)
    log.append(f"verified: {ok}")
    provisional = any(i["severity"] == "blocking" for i in issues)
    return Review(draft, writer.name, ok, unknown, provisional, ctx, log)

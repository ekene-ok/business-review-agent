"""Draft writers.

TemplateWriter (default) builds the review only from registered facts, so it needs no
external service. LLMWriter optionally asks any OpenAI-compatible chat model to improve the
wording; its output is still verified, and the agent falls back to the template if it fails.
"""
import json
import os
import urllib.request
from .analysis import LABEL, MONEY, LOOKBACK

LOWER = {"new_arr": "new ARR", "pipeline_created": "pipeline created",
         "churned_arr": "churned ARR", "active_accounts": "active accounts"}

FOLLOW_UP = {
    "new_arr": "Ask {seg} {reg} sales leadership whether deals slipped to next week or were lost, and review the forecast.",
    "pipeline_created": "Check {seg} {reg} top-of-funnel activity (campaigns, SDR capacity, events) and whether lead routing changed.",
    "churned_arr": "Pull the {seg} {reg} accounts that churned this week and confirm whether one large account or a pattern drove it.",
    "active_accounts": "Check {seg} {reg} for an account cleanup or data change before treating this as real attrition.",
}


def fmt(reg, metric, v):
    return reg.money(v) if metric in MONEY else reg.count(v)


class TemplateWriter:
    name = "template"

    def write(self, ctx) -> str:
        r = ctx.registry
        week = r.date(ctx.week)
        lines = [f"# Weekly business review: week of {week}", ""]
        blocking = [i for i in ctx.issues if i["severity"] == "blocking"]
        if blocking:
            lines += [f"**Status: provisional.** Data checks found {r.count(len(blocking))} blocking "
                      "issue(s). Totals below may be wrong until they are fixed.", ""]
        else:
            lines += ["**Status: data checks passed.**", ""]

        lines += ["## Headline numbers", "", "| Metric | This week | vs last week | vs 4-week average |",
                  "|---|---|---|---|"]
        r.add("4")
        for _, h in ctx.headline.iterrows():
            lines.append(f"| {LABEL[h.metric]} | {fmt(r, h.metric, h.latest)} | {r.pct(h.vs_last_week)} | {r.pct(h.vs_4wk_avg)} |")
        lines.append("")

        lines += ["## What changed and why", ""]
        if not ctx.anomalies:
            r.add(str(LOOKBACK))
            lines += [f"No segment or region moved outside its normal range compared with the previous {LOOKBACK} weeks.", ""]
        r.add(str(LOOKBACK))
        for a in ctx.anomalies:
            direction = "rose" if a.change > 0 else "fell"
            tone = "Bad news" if a.is_bad_news else "Good news"
            sh = a.share_of_total_change
            if sh != sh or sh <= 0:
                share = ""
            elif sh > 1:
                share = " It more than explains the company-wide change; other segments moved the other way."
            else:
                share = f" It explains {r.add(f'{sh:.0%}')} of the company-wide change."
            lines.append(f"- **{tone}: {a.segment} / {a.region} {LOWER[a.metric]} {direction} to "
                         f"{fmt(r, a.metric, a.value)}**, {r.pct(a.change)} against an expected "
                         f"{fmt(r, a.metric, a.baseline)} from its {LOOKBACK}-week trend (robust z-score {r.num(a.z)}).{share}")
        lines.append("")

        follow = [FOLLOW_UP[a.metric].format(seg=a.segment, reg=a.region) for a in ctx.anomalies if a.is_bad_news]
        lines += ["## Decisions and follow-ups", ""]
        lines += [f"- {f}" for f in follow] or ["- No follow-ups required this week."]
        lines.append("")

        review = [i["message"] for i in ctx.issues]
        review += [f"{a.segment} / {a.region} {LOWER[a.metric]} is a moderate signal "
                   f"(z-score {r.num(a.z)}); confirm before acting." for a in ctx.anomalies if a.confidence == "review"]
        lines += ["## Needs human review", ""]
        lines += [f"- {x}" for x in review] or ["- Nothing flagged."]
        return "\n".join(lines) + "\n"


class LLMWriter:
    """Optional polish step using an OpenAI-compatible chat API.
    Set LLM_API_BASE, LLM_API_KEY and LLM_MODEL. Never trusted without verification."""
    name = "llm"

    def __init__(self, base=None, key=None, model=None, transport=None):
        self.base = base or os.getenv("LLM_API_BASE", "")
        self.key = key or os.getenv("LLM_API_KEY", "")
        self.model = model or os.getenv("LLM_MODEL", "")
        self.transport = transport or self._post

    def _post(self, payload: dict) -> dict:
        req = urllib.request.Request(f"{self.base.rstrip('/')}/chat/completions", data=json.dumps(payload).encode(),
                                     headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())

    def write(self, ctx) -> str:
        draft = TemplateWriter().write(ctx)
        prompt = ("Rewrite this weekly business review so it reads clearly for executives. Keep every section and "
                  "table. Do not add, remove, round or change any number, and do not add new claims.\n\n" + draft)
        out = self.transport({"model": self.model, "temperature": 0,
                              "messages": [{"role": "user", "content": prompt}]})
        return out["choices"][0]["message"]["content"]

"""Number formatting. Every number in a draft is produced here and registered, which is
what lets the verifier trace each figure back to the data."""


class Registry:
    """Collects every formatted number the analysis produced (the only numbers a draft may use)."""

    def __init__(self):
        self.allowed: set[str] = set()

    def add(self, text: str) -> str:
        self.allowed.add(text)
        return text

    def money(self, v: float) -> str:
        a = abs(v)
        s = f"${a / 1e6:.2f}M" if a >= 1e6 else f"${a / 1e3:.0f}K" if a >= 1e3 else f"${a:.0f}"
        return self.add(("-" if v < 0 else "") + s)

    def pct(self, v: float) -> str:
        return self.add(f"{v:+.1%}")

    def count(self, v: float) -> str:
        return self.add(f"{v:,.0f}")

    def num(self, v: float, d: int = 1) -> str:
        return self.add(f"{v:.{d}f}")

    def date(self, ts) -> str:
        return self.add(f"{ts:%d %b %Y}")

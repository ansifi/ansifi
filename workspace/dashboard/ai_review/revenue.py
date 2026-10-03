"""Booked firm revenue totals. No invoice lines, staff payroll, or nested names."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

BOOKED = Path(__file__).with_name("booked_revenue.json")


def format_inr(amount: int) -> str:
    n = int(amount or 0)
    if abs(n) >= 100_000:
        lakhs = n / 100_000
        text = f"{lakhs:.2f}".rstrip("0").rstrip(".")
        return f"₹{text}L"
    return f"₹{n:,}"


def format_eur(amount: float | int) -> str:
    n = float(amount or 0)
    if n == int(n):
        return f"€{int(n):,}"
    return f"€{n:,.2f}"


def format_billed(inr: int, eur: float) -> str:
    parts = []
    if int(inr or 0):
        parts.append(format_inr(int(inr)))
    if float(eur or 0):
        parts.append(format_eur(eur))
    return " + ".join(parts) if parts else "₹0"


def pct_change(current: int, previous: int | None) -> int | None:
    """Month-on-month percent. None when there is no prior month to compare."""
    if previous is None:
        return None
    cur = int(current or 0)
    prev = int(previous or 0)
    if prev == 0:
        return None if cur == 0 else 100
    return int(round((cur - prev) * 100 / prev))


def format_pct(n: int | None) -> str:
    if n is None:
        return "—"
    n = int(n)
    return f"+{n}%" if n > 0 else f"{n}%"


def load_booked() -> dict:
    if not BOOKED.is_file():
        return {}
    data = json.loads(BOOKED.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def seed_store(store) -> None:
    for tid, rows in load_booked().items():
        if not isinstance(rows, list):
            continue
        for row in rows:
            month = str(row.get("month") or "")
            if len(month) != 7:
                continue
            store.record_revenue(tid, month, int(row.get("amount_inr") or 0))


def _end_month(rows: list[dict]) -> date:
    months = [str(row.get("month") or "") for row in rows if row.get("month")]
    if months:
        last = max(months)
        year, month = last.split("-")
        return date(int(year), int(month), 1)
    today = date.today()
    return date(today.year, today.month, 1)


def pad_series(rows: list[dict], count: int = 6) -> list[dict]:
    by_month = {str(row.get("month")): int(row.get("amount_inr") or 0) for row in rows if row.get("month")}
    end = _end_month(rows)
    year, month = end.year, end.month
    keys: list[str] = []
    for _ in range(count):
        keys.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    keys.reverse()
    return [{"month": key, "amount_inr": by_month.get(key, 0)} for key in keys]


def _direction(series: list[int]) -> tuple[str, str]:
    current = int(series[-1] if series else 0)
    prev = int(series[-2] if len(series) > 1 else current)
    if current > prev:
        return "up", "growing"
    if current < prev:
        return "down", "falling"
    return "flat", "steady"


def revenue_from_months(months: list[dict]) -> dict:
    amounts = [int(row.get("amount_inr") or 0) for row in months]
    direction, label = _direction(amounts)
    current = amounts[-1] if amounts else 0
    prev = amounts[-2] if len(amounts) > 1 else current
    enriched = []
    for i, row in enumerate(months or []):
        item = dict(row)
        prior = int(months[i - 1].get("amount_inr") or 0) if i else None
        item["pct_change"] = pct_change(item.get("amount_inr") or 0, prior)
        item["pct_label"] = format_pct(item["pct_change"])
        enriched.append(item)
    pct = enriched[-1]["pct_change"] if enriched else None
    return {
        "amount_inr": current,
        "amount_label": format_inr(current),
        "direction": direction,
        "label": label,
        "series": amounts,
        "months": enriched,
        "from_inr": prev,
        "to_inr": current,
        "from_label": format_inr(prev),
        "to_label": format_inr(current),
        "pct_change": pct,
        "pct_label": format_pct(pct),
        "amount_eur": 0,
        "eur_series": [],
        "source": "booked",
    }


def revenue_view(store, tenant_id: str, *, sqlite_path=None) -> dict:
    if sqlite_path is False:
        seed_store(store)
        return revenue_from_months(pad_series(store.revenue_trend(tenant_id)))
    from ai_review.operates_accounts import accounts_for

    acc = accounts_for(tenant_id, sqlite_path=sqlite_path)
    if acc and acc.get("revenue"):
        for row in acc.get("months") or []:
            store.record_revenue(tenant_id, row["month"], int(row.get("amount_inr") or 0))
        return acc["revenue"]
    seed_store(store)
    return revenue_from_months(pad_series(store.revenue_trend(tenant_id)))


def combined_revenue(views: list[dict]) -> dict:
    totals: dict[str, int] = {}
    eur_totals: dict[str, float] = {}
    for view in views:
        months = view.get("months") or []
        eur_series = view.get("eur_series") or []
        for i, row in enumerate(months):
            month = str(row.get("month") or "")
            if not month:
                continue
            totals[month] = totals.get(month, 0) + int(row.get("amount_inr") or 0)
            if i < len(eur_series):
                eur_totals[month] = eur_totals.get(month, 0) + float(eur_series[i] or 0)
    months = pad_series([{"month": month, "amount_inr": amount} for month, amount in totals.items()])
    out = revenue_from_months(months)
    eur_series = [float(eur_totals.get(row["month"], 0)) for row in months]
    out["amount_eur"] = eur_series[-1] if eur_series else 0
    out["eur_series"] = eur_series
    out["amount_label"] = format_inr(out["amount_inr"])
    out["from_label"] = format_inr(out["from_inr"])
    out["to_label"] = out["amount_label"]
    return out

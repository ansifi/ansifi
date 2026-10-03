"""Read-only Operates invoice totals for super-admin accounts overview.

Sums portal_invoice by month and nested desk. Never returns descriptions,
staff names, line items, payouts, or bank ledgers. Metrics always fold
foreign currencies into INR so the bars stay in rupees.
"""
from __future__ import annotations

import sqlite3
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from ai_review.revenue import format_inr, pad_series, revenue_from_months
from ai_review.scope import saas_tenant_id
from tenants import get as get_tenant, nested_employers

ROOT = Path(__file__).resolve().parents[2]
PAYROLLS = ROOT / "payroll-hrms" / "tools" / "payrolls"
FY_START = "2026-04"
# Booked desk rate: €660 / month = ₹73,000. Other codes so every bar is rupees.
INR_PER = {
    "INR": Decimal("1"),
    "EUR": Decimal("73000") / Decimal("660"),
    "USD": Decimal("88"),
    "GBP": Decimal("118"),
    "AED": Decimal("24"),
}
DB_FILES = {
    "sevendyne": "db.sqlite3",
    "dummy_client": "db_dummy_client.sqlite3",
}


def amount_to_inr(amount, currency: str | None) -> int:
    """Convert any invoice amount to whole rupees."""
    code = str(currency or "INR").upper().strip()
    if code in {"€", "EURO", "EUROS"}:
        code = "EUR"
    elif code in {"₹", "RS", "INR.", "RUPEE", "RUPEES"}:
        code = "INR"
    elif code in {"$", "US$", "USD$"}:
        code = "USD"
    elif code in {"£", "GBP£"}:
        code = "GBP"
    qty = Decimal(str(amount or 0))
    rate = INR_PER.get(code, Decimal("1"))
    return int((qty * rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _archived_client_rows(path: Path) -> list[dict]:
    con = sqlite3.connect(str(path))
    try:
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "portal_client" not in tables:
            return []
        cols = {r[1] for r in con.execute("PRAGMA table_info(portal_client)")}
        if "is_archived" not in cols:
            return []
        name_col = "name" if "name" in cols else "''"
        return [
            {"company": r[0] or "", "name": r[1] or ""}
            for r in con.execute(
                f"SELECT company_name, {name_col} FROM portal_client WHERE COALESCE(is_archived, 0) = 1"
            )
        ]
    finally:
        con.close()


def archived_employer_ids(tenant_id: str, *, sqlite_path: Path | str | None = None) -> set[str]:
    """Nested desk ids whose Operates client row is archived."""
    sid = saas_tenant_id(tenant_id)
    path = Path(sqlite_path) if sqlite_path else payroll_db(sid)
    if not path or not Path(path).is_file():
        return set()
    nested = nested_employers(sid)
    ids: set[str] = set()
    for row in _archived_client_rows(Path(path)):
        desk = _match_desk(str(row.get("company") or ""), nested) or _match_desk(
            str(row.get("name") or ""), nested
        )
        if desk:
            ids.add(desk["id"])
    return ids


def active_nested_employers(parent_id: str, *, sqlite_path: Path | str | None = None) -> list[dict]:
    archived = archived_employer_ids(parent_id, sqlite_path=sqlite_path)
    return [row for row in nested_employers(parent_id) if row["id"] not in archived]


def payroll_db(tenant_id: str) -> Path | None:
    sid = saas_tenant_id(tenant_id)
    row = get_tenant(sid) or {}
    name = DB_FILES.get(sid) or DB_FILES.get(str(row.get("payroll_db") or ""))
    if not name:
        name = "db.sqlite3" if sid == "sevendyne" else f"db_{sid}.sqlite3"
    path = PAYROLLS / name
    return path if path.is_file() else None


def _match_desk(company: str, nested: list[dict]) -> dict | None:
    hay = (company or "").lower()
    folded = hay.replace(".", "").replace(" ", "")
    for desk in nested:
        needles = [desk.get("id"), desk.get("name"), desk.get("company_hint")]
        for needle in needles:
            val = str(needle or "").strip().lower()
            if not val:
                continue
            if val in hay or val.replace(".", "").replace(" ", "") in folded:
                return desk
    return None


def _rows(path: Path, since: str) -> list[dict]:
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    try:
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "portal_invoice" not in tables or "portal_client" not in tables:
            return []
        return [
            dict(r)
            for r in con.execute(
                """
                SELECT c.company_name AS company, substr(i.issue_date, 1, 7) AS month,
                       i.amount AS amount, i.currency AS currency
                FROM portal_invoice i
                JOIN portal_client c ON c.id = i.client_id
                WHERE i.issue_date >= ?
                ORDER BY i.issue_date
                """,
                (since + "-01",),
            )
        ]
    finally:
        con.close()


def _direction_from(series: list[int]) -> tuple[str, str]:
    current = int(series[-1] if series else 0)
    prev = int(series[-2] if len(series) > 1 else current)
    if current > prev:
        return "up", "growing"
    if current < prev:
        return "down", "falling"
    return "flat", "steady"


def accounts_for(tenant_id: str, *, sqlite_path: Path | str | None | bool = None) -> dict | None:
    """Firm + nested desk billed totals from Operates invoices, April FY onward."""
    if sqlite_path is False:
        return None
    sid = saas_tenant_id(tenant_id)
    path = Path(sqlite_path) if sqlite_path else payroll_db(sid)
    if not path or not Path(path).is_file():
        return None
    nested = nested_employers(sid)
    raw = _rows(Path(path), FY_START)
    if not raw:
        return {
            "source": "operates_invoices",
            "from_month": FY_START,
            "invoice_count": 0,
            "nested": [],
            "months": [],
            "revenue": None,
        }

    firm_inr: dict[str, int] = {}
    firm_eur: dict[str, float] = {}
    desks: dict[str, dict] = {}
    invoice_count = 0
    for row in raw:
        invoice_count += 1
        month = str(row.get("month") or "")
        if len(month) != 7:
            continue
        currency = str(row.get("currency") or "INR").upper()
        amount = float(row.get("amount") or 0)
        inr = amount_to_inr(amount, currency)
        firm_inr[month] = firm_inr.get(month, 0) + inr
        if currency == "EUR":
            firm_eur[month] = firm_eur.get(month, 0) + amount
        desk = _match_desk(str(row.get("company") or ""), nested)
        key = desk["id"] if desk else "other"
        slot = desks.setdefault(
            key,
            {
                "id": key,
                "name": (desk or {}).get("name") or str(row.get("company") or "Other"),
                "invoice_count": 0,
                "inr": {},
                "eur": {},
            },
        )
        slot["invoice_count"] += 1
        slot["inr"][month] = slot["inr"].get(month, 0) + inr
        if currency == "EUR":
            slot["eur"][month] = slot["eur"].get(month, 0) + amount

    month_rows = [{"month": month, "amount_inr": amount} for month, amount in firm_inr.items()]
    months = pad_series(month_rows, count=6)
    eur_series = [float(firm_eur.get(row["month"], 0)) for row in months]
    inr_series = [int(row["amount_inr"]) for row in months]
    revenue = revenue_from_months(months)
    revenue["amount_eur"] = eur_series[-1] if eur_series else 0
    revenue["amount_label"] = format_inr(revenue["amount_inr"])
    revenue["from_label"] = format_inr(revenue["from_inr"])
    revenue["to_label"] = revenue["amount_label"]
    revenue["eur_series"] = eur_series
    revenue["source"] = "operates_invoices"

    nested_out = []
    firm_months = [row["month"] for row in months]
    for slot in desks.values():
        series = [int(slot["inr"].get(month, 0)) for month in firm_months]
        eur_hist = [float(slot["eur"].get(month, 0)) for month in firm_months]
        inr_now = series[-1] if series else 0
        eur_now = eur_hist[-1] if eur_hist else 0
        prior = any(series[:-1]) or any(eur_hist[:-1])
        if inr_now == 0 and eur_now == 0 and prior:
            direction, label = "down", "falling"
        elif any(series):
            direction, label = _direction_from(series)
        elif any(eur_hist):
            direction, label = _direction_from([int(round(n * 100)) for n in eur_hist])
        else:
            direction, label = "flat", "steady"
        nested_out.append(
            {
                "id": slot["id"],
                "name": slot["name"],
                "invoice_count": slot["invoice_count"],
                "amount_inr": inr_now,
                "amount_eur": eur_now,
                "amount_label": format_inr(inr_now),
                "direction": direction,
                "label": label,
                "series": series,
            }
        )
    nested_out.sort(key=lambda row: (-row["amount_inr"], row["name"]))
    return {
        "source": "operates_invoices",
        "from_month": FY_START,
        "invoice_count": invoice_count,
        "nested": nested_out,
        "months": months,
        "eur_series": eur_series,
        "inr_series": inr_series,
        "revenue": revenue,
    }

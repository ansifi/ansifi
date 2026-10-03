"""Ansif personal books: SIB PDF statements, categories, year totals for tax working papers."""
from __future__ import annotations

import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sib_statement import _row_fingerprint, parse_statement_bytes

ANSIF = Path("/home/ansif/works/04_Operate/Ansif")
FINANCE = ANSIF / "finance" / "Savings-Tax"
BOOKS = FINANCE / "accounts" / "books.json"
STATEMENTS = FINANCE / "statements"
REFERS = FINANCE / "refers"

CATEGORIES = (
    ("income_salary", "Salary / payroll"),
    ("income_freelance", "Freelance / client receipt"),
    ("income_interest", "Interest received"),
    ("income_other", "Other credit"),
    ("debit_tax", "Tax / TDS / GST"),
    ("debit_expense", "Expense"),
    ("debit_transfer", "Transfer / internal"),
    ("bank_charges", "Bank charges"),
    ("unset", "Unset (review)"),
)

COMPLIANCE_DEFAULT = [
    {
        "key": "ITR",
        "title": "ITR (personal)",
        "tier": "Now",
        "status": "Use the ledger year totals",
        "mode": "Worksheet from this desk, file on the portal by hand",
        "what": "Salary (Sevendyne), interest, other income, deductions. Nothing auto-files.",
    },
    {
        "key": "TDS",
        "title": "TDS (26Q / salary)",
        "tier": "Now",
        "status": "Match Form 16 / 26AS to credits",
        "mode": "Read statements + Form 16",
        "what": "Jan salary under Sevendyne payroll. Confirm TDS in 26AS before ITR.",
    },
    {
        "key": "GST",
        "title": "GST",
        "tier": "If registered",
        "status": "Skeleton",
        "mode": "Manual",
        "what": "Only if Ansif / a billed entity has GSTIN. Do not mix tenant GSTIN here.",
    },
    {
        "key": "EPFO",
        "title": "EPFO (PF)",
        "tier": "If applicable",
        "status": "Skeleton",
        "mode": "Manual",
        "what": "Personal PF if any. Sevendyne staff PF stays in payrolls.",
    },
    {
        "key": "ESIC",
        "title": "ESIC",
        "tier": "If applicable",
        "status": "Skeleton",
        "mode": "Manual",
        "what": "Not typical for this freelance desk.",
    },
    {
        "key": "MCA",
        "title": "MCA / LLP",
        "tier": "Sevendyne LLP",
        "status": "Partner records",
        "mode": "Checklist",
        "what": "LLP filings stay with Sevendyne admin. Note due dates here only.",
    },
]


def _dec(v) -> Decimal:
    try:
        return Decimal(str(v or "0"))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _dumps(obj) -> str:
    def conv(o):
        if isinstance(o, Decimal):
            return str(o)
        if isinstance(o, date):
            return o.isoformat()
        raise TypeError(type(o))

    return json.dumps(obj, indent=2, default=conv) + "\n"


def load_books() -> dict:
    if not BOOKS.is_file():
        return {"accounts": [], "entries": [], "imports": []}
    try:
        data = json.loads(BOOKS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"accounts": [], "entries": [], "imports": []}
    data.setdefault("accounts", [])
    data.setdefault("entries", [])
    data.setdefault("imports", [])
    return data


def save_books(data: dict) -> None:
    BOOKS.parent.mkdir(parents=True, exist_ok=True)
    BOOKS.write_text(_dumps(data), encoding="utf-8")


def categorize(particulars: str, deposit: Decimal, withdrawal: Decimal) -> tuple[str, str]:
    t = (particulars or "").upper()
    if "INTEREST" in t or "INT.PD" in t or "INT PD" in t or "INT/PD" in t:
        return "income_interest", "Interest received"
    if "IMPS CHARGES" in t or "NEFT CHARGES" in t or ("CHARGES:" in t and "IMPS" in t):
        return "bank_charges", "Bank charges"
    if "TDS" in t or "INCOME TAX" in t or "CENTRAL BOARD OF DIRECT" in t or "CBDT" in t or "DIRECT TAX" in t:
        return "debit_tax", "Tax / TDS / GST"
    if "WISE" in t:
        return ("income_freelance", "Client receipt (Wise)") if deposit > 0 else ("debit_transfer", "Wise payment")
    if "SALARY" in t:
        return ("income_salary", "Salary") if deposit > 0 else ("debit_expense", "Salary payment")
    if "SEVENDYNE" in t and deposit > 0:
        return "income_salary", "Sevendyne / payroll credit"
    if deposit > 0 and withdrawal == 0:
        if "NEFT" in t or "IMPS" in t or "RTGS" in t:
            return "income_freelance", "Bank transfer receipt"
        return "income_other", "Credit"
    if "UPI" in t:
        return ("income_other", "UPI in") if deposit > 0 else ("debit_expense", "UPI out")
    if withdrawal > 0:
        return "debit_expense", "Debit"
    return "unset", ""


def _fy_end(d: date) -> int:
    return d.year + 1 if d.month >= 4 else d.year


def _fy_bounds(end_year: int) -> tuple[date, date]:
    return date(end_year - 1, 4, 1), date(end_year, 3, 31)


def _account(data: dict, acct_num: str, owner: str, label: str) -> dict:
    digits = re.sub(r"\D", "", acct_num or "")
    digits = digits.lstrip("0") or digits
    if digits in {"", "unknown"}:
        same = [row for row in data["accounts"] if row.get("owner") == owner]
        if len(same) == 1:
            return same[0]
        digits = "unknown"
    mask = digits[-4:] if len(digits) >= 4 else (digits or "xxxx")
    for row in data["accounts"]:
        if row.get("account_number") == digits and row.get("owner") == owner:
            return row
    bank = "SIB current" if digits.startswith("1011") or owner.startswith("Sevendyne") else "SBI savings"
    row = {
        "id": f"a{len(data['accounts']) + 1}",
        "account_number": digits,
        "mask": mask,
        "label": label or f"{bank} …{mask} ({owner})",
        "owner": owner,
        "currency": "INR",
    }
    data["accounts"].append(row)
    return row


def import_pdf_bytes(raw: bytes, name: str, owner: str = "Ansif") -> dict:
    parsed = parse_statement_bytes(raw, name)
    data = load_books()
    acct_num = re.sub(r"\D", "", (parsed.get("account_number") or "").strip())
    acc = _account(data, acct_num, owner, "")
    hashes = {e.get("dedupe_hash") for e in data["entries"]}
    created = 0
    for row in parsed.get("rows") or []:
        dep = _dec(row["deposit"])
        wdr = _dec(row["withdrawal"])
        txn = row["txn_date"]
        if not hasattr(txn, "isoformat"):
            txn = date.fromisoformat(str(txn)[:10])
        h = _row_fingerprint(txn, row["particulars"], wdr, dep, _dec(row["balance_after"]), acc["account_number"])
        if h in hashes:
            continue
        cat, memo = categorize(row["particulars"], dep, wdr)
        data["entries"].append(
            {
                "dedupe_hash": h,
                "account_id": acc["id"],
                "owner": owner,
                "source": name,
                "txn_date": txn.isoformat(),
                "particulars": row["particulars"],
                "friendly_memo": memo,
                "withdrawal": str(wdr),
                "deposit": str(dep),
                "balance_after": str(row["balance_after"]),
                "balance_dr_cr": row.get("balance_dr_cr") or "",
                "category": cat,
            }
        )
        hashes.add(h)
        created += 1
    data["imports"].append(
        {
            "name": name,
            "owner": owner,
            "account_id": acc["id"],
            "rows_in_file": parsed.get("row_count") or 0,
            "new_rows": created,
            "statement_from": parsed["statement_from"].isoformat() if parsed.get("statement_from") else "",
            "statement_to": parsed["statement_to"].isoformat() if parsed.get("statement_to") else "",
        }
    )
    save_books(data)
    return {"ok": True, "new_rows": created, "rows_in_file": parsed.get("row_count") or 0, "account": acc["label"]}


def ingest_refers() -> dict:
    """Load PDFs and bank Excel/TSV already under finance/Savings-Tax/refers/."""
    STATEMENTS.mkdir(parents=True, exist_ok=True)
    data = load_books()
    seen = {i.get("name") for i in data["imports"] if (i.get("rows_in_file") or 0) > 0}
    added = 0
    files = []
    folders = (
        ("Ansif", REFERS / "ansif"),
        ("Ansif", REFERS / "tax_2025"),
        ("Sevendyne LLP", REFERS / "sevendyne"),
    )
    for owner, folder in folders:
        if not folder.is_dir():
            continue
        for path in sorted(folder.iterdir()):
            if path.suffix.lower() not in {".pdf", ".xls", ".xlsx", ".txt", ".csv"}:
                continue
            key = f"refers/{folder.name}/{path.name}"
            if key in seen:
                continue
            files.append((owner, path, key))
    for owner, path, key in files:
        data = load_books()
        data["imports"] = [i for i in data["imports"] if i.get("name") != key]
        save_books(data)
        raw = path.read_bytes()
        dest = STATEMENTS / path.name
        if not dest.exists():
            dest.write_bytes(raw)
        import_pdf_bytes(raw, key, owner=owner)
        added += 1
    return {"ok": True, "ingested": added}


def _entry_date(row: dict) -> date | None:
    try:
        return date.fromisoformat(str(row.get("txn_date") or "")[:10])
    except ValueError:
        return None


def year_summary(year: int | None = None) -> dict:
    ingest_refers()
    data = load_books()
    fy_years: set[int] = set()
    dated: list[tuple[date, dict]] = []
    for row in data["entries"]:
        dt = _entry_date(row)
        if not dt:
            continue
        dated.append((dt, row))
        fy_years.add(_fy_end(dt))
    year = year or (max(fy_years) if fy_years else _fy_end(date.today()))
    start, end = _fy_bounds(year)
    entries = [row for dt, row in dated if start <= dt <= end]
    totals = {k: Decimal("0") for k, _ in CATEGORIES}
    credits = Decimal("0")
    debits = Decimal("0")
    for row in entries:
        dep = _dec(row.get("deposit"))
        wdr = _dec(row.get("withdrawal"))
        credits += dep
        debits += wdr
        cat = row.get("category") or "unset"
        if cat not in totals:
            cat = "unset"
        totals[cat] += dep if dep else wdr
    by_cat = [
        {"id": k, "label": lab, "amount": str(totals[k])}
        for k, lab in CATEGORIES
        if totals[k] != 0 or k in {"income_interest", "income_salary", "debit_tax"}
    ]
    return {
        "ok": True,
        "year": year,
        "fy_label": f"FY {year - 1}–{str(year)[2:]}",
        "from": start.isoformat(),
        "to": end.isoformat(),
        "years": sorted(fy_years or {year}),
        "credits": str(credits),
        "debits": str(debits),
        "net": str(credits - debits),
        "interest": str(totals["income_interest"]),
        "salary": str(totals["income_salary"]),
        "tax": str(totals["debit_tax"]),
        "categories": by_cat,
        "accounts": data["accounts"],
        "imports": data["imports"][-16:],
        "entries": sorted(entries, key=lambda r: r.get("txn_date") or "", reverse=True)[:800],
        "entry_count": len(entries),
        "category_labels": [{"id": k, "label": lab} for k, lab in CATEGORIES],
        "how": (
            "Ansif personal books (SBI savings + Sevendyne LLP SIB current). "
            "Upload PDF or Excel statements. Tenant GEO.XYZ invoices stay in Sevendyne payrolls."
        ),
    }


def update_row(dedupe_hash: str, category: str = "", purpose: str = "") -> dict:
    data = load_books()
    ids = {k for k, _ in CATEGORIES}
    found = False
    for row in data["entries"]:
        if row.get("dedupe_hash") != dedupe_hash:
            continue
        if category and category in ids:
            row["category"] = category
        if purpose is not None:
            row["friendly_memo"] = str(purpose)[:500]
        found = True
        break
    if not found:
        return {"ok": False, "error": "not_found"}
    save_books(data)
    return {"ok": True}


def save_upload(name: str, raw: bytes, owner: str = "Ansif") -> dict:
    STATEMENTS.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "-", (name or "statement.pdf"))[:80]
    if not any(safe.lower().endswith(ext) for ext in (".pdf", ".xls", ".xlsx", ".txt", ".csv")):
        return {"ok": False, "error": "pdf_or_xls"}
    dest = STATEMENTS / safe
    n = 2
    while dest.exists():
        dest = STATEMENTS / f"{Path(safe).stem}-{n}.pdf"
        n += 1
    dest.write_bytes(raw)
    return import_pdf_bytes(raw, dest.name, owner=owner)


def load_compliance() -> dict:
    path = FINANCE / "compliance.json"
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("modules"):
                return data
        except (OSError, json.JSONDecodeError):
            pass
    return {"ok": True, "modules": COMPLIANCE_DEFAULT}


def save_compliance(modules: list) -> dict:
    path = FINANCE / "compliance.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    out = {"ok": True, "modules": modules}
    path.write_text(_dumps(out), encoding="utf-8")
    return out

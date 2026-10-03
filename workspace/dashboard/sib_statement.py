"""
Parse South Indian Bank (SIB) statement-of-account PDF exports into structured rows.

Heuristic: text-based layout with lines starting DD-MM-YY, amounts and balance ending in Cr/Dr.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from io import BytesIO
from typing import BinaryIO

try:
    import pdfplumber
except ImportError:  # pragma: no cover
    pdfplumber = None

DATE_LINE = re.compile(r"^(\d{2}-\d{2}-\d{2})\s+(.+)$")
BALANCE_TAIL = re.compile(r"([\d,]+\.\d{2})\s*(Cr|Dr)\s*$", re.IGNORECASE)
AMOUNT_TOKEN = re.compile(r"[\d,]+\.\d{2}")
ACCOUNT_RE = re.compile(r"A/C\s*NO\s*:\s*(\d+)", re.IGNORECASE)
PERIOD_RE = re.compile(
    r"STATEMENT\s+OF\s+ACCOUNT\s+FOR\s+THE\s+PERIOD\s+FROM\s+(\d{2}-\d{2}-\d{4})\s+TO\s+(\d{2}-\d{2}-\d{4})",
    re.IGNORECASE,
)


def _parse_indian_decimal(s: str) -> Decimal:
    return Decimal(s.replace(",", ""))


def _parse_stmt_date(d: str) -> date:
    """DD-MM-YY -> date (20YY)."""
    day, month, yy = d.split("-")
    year = 2000 + int(yy)
    return date(year, int(month), int(day))


def _parse_period_date(d: str) -> date:
    """DD-MM-YYYY -> date."""
    day, month, year = d.split("-")
    return date(int(year), int(month), int(day))


def _norm_line(s: str) -> str:
    return " ".join(s.replace("\t", " ").split()).strip()


@dataclass
class ParsedLedgerRow:
    txn_date: date
    particulars: str
    withdrawal: Decimal
    deposit: Decimal
    balance_after: Decimal
    balance_dr_cr: str


def _row_fingerprint(
    txn_date: date,
    particulars: str,
    withdrawal: Decimal,
    deposit: Decimal,
    balance_after: Decimal,
    account: str = "",
) -> str:
    raw = f"{account}|{txn_date.isoformat()}|{withdrawal}|{deposit}|{balance_after}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]


def extract_pdf_text(fileobj: BinaryIO) -> str:
    if pdfplumber is None:
        raise RuntimeError("pdfplumber is not installed.")
    parts: list[str] = []
    with pdfplumber.open(fileobj) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            parts.append(t)
    return "\n".join(parts)


def parse_sib_statement_text(text: str) -> tuple[str, date | None, date | None, list[ParsedLedgerRow]]:
    """
    Returns (account_number_or_empty, period_from, period_to, rows).
    """
    acct = ""
    m_ac = ACCOUNT_RE.search(text)
    if m_ac:
        acct = m_ac.group(1).strip()

    p_from = p_to = None
    m_per = PERIOD_RE.search(text)
    if m_per:
        p_from = _parse_period_date(m_per.group(1))
        p_to = _parse_period_date(m_per.group(2))

    lines = [_norm_line(ln) for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]

    rows: list[ParsedLedgerRow] = []
    buf: list[str] = []
    prev_balance: Decimal | None = None

    def flush_block(block_lines: list[str]) -> None:
        nonlocal prev_balance
        if not block_lines:
            return
        merged = " ".join(block_lines)
        merged = _norm_line(merged)
        dm = DATE_LINE.match(merged)
        if not dm:
            return
        d_raw, rest = dm.group(1), dm.group(2).strip()
        if rest.startswith("PAGE:") or "PARTICULARS DATE" in merged.upper():
            return
        low = merged.lower()
        if "page total" in low or "visit us at www.southindianbank.com" in low:
            return

        bal_m = BALANCE_TAIL.search(rest)
        if not bal_m:
            return
        balance = _parse_indian_decimal(bal_m.group(1))
        dr_cr = bal_m.group(2).title()[:2]  # Cr / Dr
        prefix = rest[: bal_m.start()].strip()
        amounts = [_parse_indian_decimal(m.group(0)) for m in AMOUNT_TOKEN.finditer(prefix)]
        if not amounts:
            return
        particulars = AMOUNT_TOKEN.sub("", prefix).strip()
        particulars = re.sub(r"\s+", " ", particulars).strip()
        if not particulars:
            particulars = "(no description)"

        withdrawal = Decimal("0")
        deposit = Decimal("0")
        eps = Decimal("0.02")

        def fits(w: Decimal, d: Decimal) -> bool:
            if prev_balance is None:
                return True
            return abs(prev_balance - w + d - balance) < eps

        if len(amounts) == 1:
            a = amounts[0]
            if prev_balance is None:
                withdrawal, deposit = (Decimal("0"), a) if balance > a else (a, Decimal("0"))
            elif fits(Decimal("0"), a):
                deposit = a
            elif fits(a, Decimal("0")):
                withdrawal = a
            else:
                withdrawal, deposit = (Decimal("0"), a) if balance > prev_balance else (a, Decimal("0"))
        else:
            x, y = amounts[-2], amounts[-1]
            if prev_balance is not None:
                if abs(prev_balance - x + y - balance) < eps:
                    withdrawal, deposit = x, y
                elif abs(prev_balance - y + x - balance) < eps:
                    withdrawal, deposit = y, x
                elif abs(prev_balance + x + y - balance) < eps:
                    deposit = x + y
                elif abs(prev_balance - x - y - balance) < eps:
                    withdrawal = x + y
                else:
                    withdrawal, deposit = (x, Decimal("0")) if balance < prev_balance else (Decimal("0"), y)
            else:
                withdrawal, deposit = x, y

        txn_date = _parse_stmt_date(d_raw)
        rows.append(
            ParsedLedgerRow(
                txn_date=txn_date,
                particulars=particulars,
                withdrawal=withdrawal,
                deposit=deposit,
                balance_after=balance,
                balance_dr_cr=dr_cr,
            )
        )
        prev_balance = balance

    for ln in lines:
        skip_prefix = (
            ln.startswith("SIBL")
            or ln.startswith("DOOR NO")
            or "IFSC:" in ln
            or ln.startswith("Ph:")
            or ln.startswith("KERALA")
            or ln.startswith("ERNAKULAM")
            or ln.startswith("India")
            or re.match(r"^\d{5}$", ln)
            or ln.startswith("MODE OF OPR")
            or ln.startswith("CUSTOMER ID")
            or ln.startswith("DATE:") and "PAGE:" in ln
            or "STATEMENT OF ACCOUNT FOR THE PERIOD" in ln.upper()
            or ln.startswith("TYPE :")
            or "CURRENCY CODE" in ln
            or ln.startswith("PIN:")
            or ln.startswith("MAYUR BUSINESS")
            or ln.startswith("SEVENDYNE CONSULTANCY")
            or ln.startswith("ANSIF.")
            or ln == "PARTICULARS DATE CHQ.NO. WITHDRAWALS DEPOSITS BALANCE"
        )
        if skip_prefix:
            continue
        if re.match(r"^--\s*\d+\s+of\s+\d+\s*--$", ln):
            continue
        if re.match(r"^\d+\s+Page\s+\d+\s+of", ln, re.I):
            continue

        if DATE_LINE.match(ln):
            if buf:
                flush_block(buf)
            buf = [ln]
        elif buf:
            buf.append(ln)
            if BALANCE_TAIL.search(ln):
                flush_block(buf)
                buf = []

    if buf:
        flush_block(buf)

    return acct, p_from, p_to, rows


_MONTH = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}
SBI_START = re.compile(
    r"^(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})\s+(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})\s+(.+)$"
)
SBI_ACCT = re.compile(r"Account Number\s*:\s*(\d+)", re.I)
SBI_PERIOD = re.compile(
    r"Account Statement from\s+(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})\s+to\s+(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})",
    re.I,
)
SIB_YMD = re.compile(
    r"^(?:\d+\s+)?(\d{2}-\d{2}-\d{4})\s+(\d{2}-\d{2}-\d{4})\s*(.*)$"
)
SIB_ACCT2 = re.compile(r"Account\s*No\s*:?\s*(\d+)", re.I)


def _parse_mon_date(s: str) -> date:
    day, mon, year = s.split()
    return date(int(year), _MONTH[mon[:3].title()], int(day))


def _clean_pdf_text(text: str) -> str:
    return (
        text.replace("(cid:9)", " ")
        .replace("\u00a0", " ")
        .replace("\t", " ")
    )


SIB_YMD_ROW = re.compile(
    r"^(\d+)\s+(\d{2}-\d{2}-\d{4})\s+(\d{2}-\d{2}-\d{4})\s*(.*)$"
)
SBI_TSV_ROW = re.compile(r"^(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})\t")
SBI_ACCT_LOOSE = re.compile(r"Account\s+Nu[a-z]*\s*:?\s*_?(\d{10,})", re.I)


def _acct_from_text(text: str) -> str:
    for rx in (SBI_ACCT, SBI_ACCT_LOOSE, SIB_ACCT2, ACCOUNT_RE):
        m = rx.search(text)
        if m:
            return re.sub(r"\D", "", m.group(1))
    return ""


def _money_cell(s: str) -> Decimal:
    t = (s or "").strip().replace(" ", "")
    if not t or t in {".", "-", "--"}:
        return Decimal("0")
    try:
        return _parse_indian_decimal(t)
    except Exception:
        return Decimal("0")


def _split_wdr_dep(amts: list[Decimal], bal: Decimal, prev: Decimal | None, desc: str) -> tuple[Decimal, Decimal]:
    eps = Decimal("0.05")
    candidates = [a for a in amts if a > 0]
    if prev is not None:
        for a in candidates:
            if abs(prev + a - bal) < eps:
                return Decimal("0"), a
            if abs(prev - a - bal) < eps:
                return a, Decimal("0")
        if bal > prev:
            return Decimal("0"), (bal - prev)
        if bal < prev:
            return (prev - bal), Decimal("0")
    amt = candidates[-1] if candidates else Decimal("0")
    low = desc.upper()
    credit = any(
        k in low
        for k in ("BY TRANSFER", "CREDIT", "INTEREST", "DEPOSIT", "WISE PAYMENTS", "UPI/CR", "NEFT CR")
    )
    debit = any(
        k in low for k in ("TO TRANSFER", "DEBIT", "WITHDRAW", "UPI/DR", "NEFT TO", "CHARGES", "ATM WDL")
    )
    if credit and not debit:
        return Decimal("0"), amt
    return amt, Decimal("0")


def parse_sbi_statement_text(text: str) -> tuple[str, date | None, date | None, list[ParsedLedgerRow]]:
    text = _clean_pdf_text(text)
    acct = _acct_from_text(text)
    p_from = p_to = None
    mp = SBI_PERIOD.search(text)
    if mp:
        p_from = _parse_mon_date(mp.group(1))
        p_to = _parse_mon_date(mp.group(2))
    lines = [_norm_line(ln) for ln in text.splitlines() if _norm_line(ln)]
    rows: list[ParsedLedgerRow] = []
    buf: list[str] = []
    prev: Decimal | None = None

    def flush(block: list[str]) -> None:
        nonlocal prev
        if not block:
            return
        merged = _norm_line(" ".join(block))
        dm = SBI_START.match(merged)
        if not dm:
            return
        rest = dm.group(3)
        amounts = [_parse_indian_decimal(a) for a in AMOUNT_TOKEN.findall(rest)]
        if len(amounts) < 2:
            return
        desc = rest
        for a in AMOUNT_TOKEN.findall(rest):
            desc = desc.replace(a, " ", 1)
        desc = _norm_line(desc)
        bal = amounts[-1]
        wdr, dep = _split_wdr_dep(amounts[:-1], bal, prev, desc)
        rows.append(
            ParsedLedgerRow(
                txn_date=_parse_mon_date(dm.group(1)),
                particulars=desc[:2000],
                withdrawal=wdr,
                deposit=dep,
                balance_after=bal,
                balance_dr_cr="Cr",
            )
        )
        prev = bal

    for ln in lines:
        if SBI_START.match(ln):
            if buf:
                flush(buf)
            buf = [ln]
        elif buf:
            buf.append(ln)
            if len(AMOUNT_TOKEN.findall(ln)) >= 1 and len(AMOUNT_TOKEN.findall(_norm_line(" ".join(buf)))) >= 2:
                flush(buf)
                buf = []
    if buf:
        flush(buf)
    return acct, p_from, p_to, rows


def parse_sbi_tsv(text: str) -> tuple[str, date | None, date | None, list[ParsedLedgerRow]]:
    acct = _acct_from_text(text)
    p_from = p_to = None
    mp = SBI_PERIOD.search(text)
    if mp:
        p_from = _parse_mon_date(mp.group(1))
        p_to = _parse_mon_date(mp.group(2))
    rows: list[ParsedLedgerRow] = []
    for ln in text.splitlines():
        if not SBI_TSV_ROW.match(ln):
            continue
        parts = ln.split("\t")
        if len(parts) < 6:
            continue
        try:
            txn = _parse_mon_date(parts[0].strip())
        except (ValueError, KeyError, IndexError):
            continue
        desc = _norm_line((parts[2] if len(parts) > 2 else "") + " " + (parts[3] if len(parts) > 3 else ""))
        wdr = _money_cell(parts[4] if len(parts) > 4 else "")
        dep = _money_cell(parts[5] if len(parts) > 5 else "")
        bal = _money_cell(parts[6] if len(parts) > 6 else "")
        if wdr == 0 and dep == 0:
            continue
        rows.append(
            ParsedLedgerRow(
                txn_date=txn,
                particulars=desc[:2000],
                withdrawal=wdr,
                deposit=dep,
                balance_after=bal,
                balance_dr_cr="Cr",
            )
        )
    return acct, p_from, p_to, rows


def parse_sbi_pdf_tables(raw: bytes) -> tuple[str, date | None, date | None, list[ParsedLedgerRow]]:
    if pdfplumber is None:
        return "", None, None, []
    acct = ""
    p_from = p_to = None
    rows: list[ParsedLedgerRow] = []
    with pdfplumber.open(BytesIO(raw)) as pdf:
        head = _clean_pdf_text((pdf.pages[0].extract_text() or "") if pdf.pages else "")
        acct = _acct_from_text(head)
        mp = SBI_PERIOD.search(head)
        if mp:
            p_from = _parse_mon_date(mp.group(1))
            p_to = _parse_mon_date(mp.group(2))
        for page in pdf.pages:
            for table in page.extract_tables() or []:
                for raw_row in table:
                    cells = [_norm_line(str(c or "").replace("\n", " ")) for c in (raw_row or [])]
                    if not cells or "Txn Date" in (cells[0] or ""):
                        continue
                    if len(cells) < 5:
                        continue
                    try:
                        txn = _parse_mon_date(cells[0])
                    except (ValueError, KeyError, IndexError):
                        continue
                    desc = _norm_line(" ".join(cells[2:-3] if len(cells) >= 7 else cells[1:-2]))
                    wdr = _money_cell(cells[-3] if len(cells) >= 3 else "")
                    dep = _money_cell(cells[-2] if len(cells) >= 2 else "")
                    bal = _money_cell(cells[-1])
                    if wdr == 0 and dep == 0:
                        continue
                    rows.append(
                        ParsedLedgerRow(
                            txn_date=txn,
                            particulars=desc[:2000],
                            withdrawal=wdr,
                            deposit=dep,
                            balance_after=bal,
                            balance_dr_cr="Cr",
                        )
                    )
    return acct, p_from, p_to, rows


def parse_sib_ymd_statement_text(text: str) -> tuple[str, date | None, date | None, list[ParsedLedgerRow]]:
    """South Indian Bank PDF: amount often sits on the line before serial + DD-MM-YYYY."""
    text = _clean_pdf_text(text)
    acct = _acct_from_text(text)
    lines = [_norm_line(ln) for ln in text.splitlines() if _norm_line(ln)]
    rows: list[ParsedLedgerRow] = []
    pending_text: list[str] = []
    pending_amt: list[Decimal] = []
    prev: Decimal | None = None
    for ln in lines:
        dm = SIB_YMD_ROW.match(ln)
        if not dm:
            if re.fullmatch(r"[\d,]+\.\d{2}", ln):
                pending_amt.append(_parse_indian_decimal(ln))
            elif not ln.lower().startswith("****end"):
                pending_text.append(ln)
            continue
        rest = dm.group(4) or ""
        on_line = [_parse_indian_decimal(a) for a in AMOUNT_TOKEN.findall(rest)]
        desc = _norm_line(" ".join(pending_text + [AMOUNT_TOKEN.sub(" ", rest)]))
        amts = pending_amt + on_line
        if not amts:
            pending_text, pending_amt = [], []
            continue
        bal = amts[-1]
        body = amts[:-1] if len(amts) > 1 else amts
        wdr, dep = _split_wdr_dep(body, bal, prev, desc)
        rows.append(
            ParsedLedgerRow(
                txn_date=_parse_period_date(dm.group(2)),
                particulars=desc[:2000],
                withdrawal=wdr,
                deposit=dep,
                balance_after=bal,
                balance_dr_cr="Cr",
            )
        )
        prev = bal
        pending_text, pending_amt = [], []
    return acct, None, None, rows


def parse_sib_xls_bytes(raw: bytes) -> tuple[str, date | None, date | None, list[ParsedLedgerRow]]:
    try:
        import xlrd
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("xlrd is not installed.") from exc
    wb = xlrd.open_workbook(file_contents=raw)
    sh = wb.sheet_by_index(0)
    header = [str(sh.cell_value(0, c) or "").strip().lower() for c in range(sh.ncols)]

    def col(*names: str) -> int:
        for i, h in enumerate(header):
            if any(n == h or n in h for n in names):
                return i
        return -1

    i_date = col("transaction date")
    i_part = col("particulars")
    i_wdr = col("withdrawals")
    i_dep = col("deposits")
    i_bal = col("balance amount", "balance")
    if i_date < 0:
        return "", None, None, []
    rows: list[ParsedLedgerRow] = []
    for r in range(1, sh.nrows):
        d_raw = str(sh.cell_value(r, i_date) or "").strip()
        if not re.match(r"\d{2}-\d{2}-\d{4}$", d_raw):
            continue
        desc = str(sh.cell_value(r, i_part) or "") if i_part >= 0 else ""
        wdr = _money_cell(str(sh.cell_value(r, i_wdr) or "") if i_wdr >= 0 else "")
        dep = _money_cell(str(sh.cell_value(r, i_dep) or "") if i_dep >= 0 else "")
        bal = _money_cell(str(sh.cell_value(r, i_bal) or "") if i_bal >= 0 else "")
        if wdr == 0 and dep == 0:
            continue
        rows.append(
            ParsedLedgerRow(
                txn_date=_parse_period_date(d_raw),
                particulars=_norm_line(desc)[:2000],
                withdrawal=wdr,
                deposit=dep,
                balance_after=bal,
                balance_dr_cr="Cr",
            )
        )
    return "", None, None, rows


def _pack(acct, p_from, p_to, parsed) -> dict:
    order = 0
    out_rows: list[dict] = []
    for r in parsed:
        order += 1
        fp = _row_fingerprint(r.txn_date, r.particulars, r.withdrawal, r.deposit, r.balance_after, acct)
        out_rows.append(
            {
                "sort_order": order,
                "txn_date": r.txn_date,
                "particulars": r.particulars[:2000],
                "withdrawal": r.withdrawal,
                "deposit": r.deposit,
                "balance_after": r.balance_after,
                "balance_dr_cr": r.balance_dr_cr,
                "dedupe_hash": fp,
            }
        )
    return {
        "account_number": acct,
        "statement_from": p_from,
        "statement_to": p_to,
        "rows": out_rows,
        "row_count": len(out_rows),
    }


def parse_bank_pdf(fileobj: BinaryIO) -> dict:
    raw = fileobj.read() if hasattr(fileobj, "read") else fileobj
    if not isinstance(raw, bytes):
        raw = raw.read()
    text = extract_pdf_text(BytesIO(raw))
    candidates = [
        _pack(*parse_sbi_pdf_tables(raw)),
        _pack(*parse_sib_statement_text(text)),
        _pack(*parse_sbi_statement_text(text)),
        _pack(*parse_sib_ymd_statement_text(text)),
    ]
    return max(candidates, key=lambda d: d.get("row_count") or 0)


def parse_statement_bytes(raw: bytes, name: str = "") -> dict:
    """PDF, SIB Excel, or SBI tab-separated .xls export."""
    if raw[:4] == b"\xd0\xcf\x11\xe0":
        packed = _pack(*parse_sib_xls_bytes(raw))
        if packed["row_count"]:
            if not packed["account_number"] and "sevendyne" in (name or "").lower():
                packed["account_number"] = "1011073000000048"
            return packed
    head = raw[:800]
    if head.lstrip()[:20].startswith(b"Account") or b"Txn Date" in head:
        text = raw.decode("utf-8", errors="replace")
        packed = _pack(*parse_sbi_tsv(text))
        if packed["row_count"]:
            return packed
        return _pack(*parse_sbi_statement_text(text))
    return parse_bank_pdf(BytesIO(raw))


def parse_south_indian_bank_pdf(fileobj: BinaryIO) -> dict:
    raw = fileobj.read() if hasattr(fileobj, "read") else fileobj
    if isinstance(raw, bytes):
        return parse_statement_bytes(raw)
    return parse_bank_pdf(raw)

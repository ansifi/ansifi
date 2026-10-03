"""Policy scan before an AiJob is visible in a tenant digest."""
from __future__ import annotations

import re

from ai_review.scope import foreign_client_names
from ai_review.store import Store

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b", re.I)
HOST_RE = re.compile(
    r"\b(?:localhost|127\.0\.0\.1|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}"
    r"|167\.233\.\d{1,3}\.\d{1,3}|[\w-]+\.(?:internal|local|lan|corp))\b",
    re.I,
)


def _word_in(text: str, name: str) -> bool:
    if not name or len(name) < 3:
        return False
    return re.search(r"(?<![A-Za-z0-9])" + re.escape(name) + r"(?![A-Za-z0-9])", text, re.I) is not None


def scan_text(text: str, tenant_id: str) -> str:
    blob = text or ""
    for name in sorted(foreign_client_names(tenant_id), key=len, reverse=True):
        if _word_in(blob, name):
            return "named_client"
    if EMAIL_RE.search(blob):
        return "mailbox_leak"
    if HOST_RE.search(blob):
        return "host_leak"
    return "none"


def policy_scan(job_id: int, store: Store | None = None) -> str:
    store = store or Store()
    job = store.get_job(job_id)
    if not job:
        return "none"
    text = store.jobable_text(job["jobable_type"], int(job["jobable_id"]))
    flag = scan_text(text, job["tenant_id"])
    store.set_job_policy(job_id, flag, blocked=flag != "none")
    return flag

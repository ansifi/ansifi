"""Stub AI drafts. Real generation is out of scope for this change."""
from __future__ import annotations


class DraftGenerator:
    @staticmethod
    def call(*, tenant: str, type: str, **kwargs) -> dict:
        extra = kwargs.get("about") or kwargs.get("subject") or type
        return {
            "title": f"[AI] {type} — {tenant}",
            "body": f"[AI draft] {type} for {tenant}: {extra}. Review and approve before anything is sent.",
        }

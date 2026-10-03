"""Reuse hub tenants.json — SaaS parent is the isolation key (sevendyne / dummy_client)."""
from __future__ import annotations

from tenants import all_clients, get as get_tenant, is_saas_tenant, nested_employers


def saas_tenant_id(tenant_id: str) -> str:
    row = get_tenant(tenant_id)
    if not row:
        return (tenant_id or "").strip().lower()
    if is_saas_tenant(row):
        return row["id"]
    return str(row.get("managed_by") or row["id"])


def tenant_names(tenant_id: str) -> set[str]:
    """Names this tenant may mention: itself plus nested employer desks."""
    sid = saas_tenant_id(tenant_id)
    row = get_tenant(sid)
    names: set[str] = set()
    if row:
        names.add(row["name"].strip().lower())
        names.add(row["id"].strip().lower())
    for nested in nested_employers(sid):
        names.add(nested["name"].strip().lower())
        names.add(nested["id"].strip().lower())
    return {n for n in names if n}


def foreign_client_names(tenant_id: str) -> set[str]:
    allowed = tenant_names(tenant_id)
    out: set[str] = set()
    for row in all_clients():
        for piece in (row.get("name"), row.get("id"), row.get("company_hint")):
            val = str(piece or "").strip().lower()
            if val and val not in allowed:
                out.add(val)
    return out


def saas_tenants() -> list[dict]:
    return [row for row in all_clients() if is_saas_tenant(row)]

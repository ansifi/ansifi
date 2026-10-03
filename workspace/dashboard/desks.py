"""Work status for Analysis / Content / Network / Operate.

Home shows status, not a folder tree. Operate is a status page only — not payrolls.
"""
from __future__ import annotations

from pathlib import Path

from mail_status import mailbox_status

WORKS = Path("/home/ansif/works")
SKIP_DRAFTS = {"SERIES-from-port-commits.md", "2026-08-13_redmine-how-to-build-drafts.md"}

DESKS = (
    {
        "id": "analysis",
        "title": "Analysis",
        "desk": "01_Build",
        "href": "/app/analysis.html",
        "dashboard": "/app/analysis.html",
        "dashboard_label": "Open Analysis",
        "now": "Projects, programmes, and product ideas in Build.",
    },
    {
        "id": "content",
        "title": "Content",
        "desk": "02_Content",
        "href": "/app/content.html",
        "dashboard": "/app/content.html",
        "dashboard_label": "Open Content",
        "now": "What is ready to push to social. Nothing auto-publishes.",
    },
    {
        "id": "network",
        "title": "Network",
        "desk": "03_Network",
        "href": "/app/network.html",
        "dashboard": "/app/network.html",
        "dashboard_label": "Open Network",
        "now": "Mail from aes37group@gmail.com only. Client threads filtered.",
    },
    {
        "id": "operate",
        "title": "Operate",
        "desk": "04_Operate/Ansif",
        "href": "/app/operate.html",
        "dashboard": "/app/operate.html",
        "dashboard_label": "Open Operate",
        "now": "Ansif personal profile: freelance (GEO.XYZ under Sevendyne payroll), other personal work, income and tax.",
    },
)


def _row(title: str, status: str, kind: str, detail: str = "", lane: str | None = None, action: str = "") -> dict:
    if lane is None:
        lane = "planned" if kind in {"idea", "not_started", "future", "hold"} else "active"
    return {
        "title": title,
        "status": status,
        "kind": kind,
        "lane": lane,
        "detail": detail,
        "action": action,
    }


def _first_heading(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
    except OSError:
        pass
    return path.stem.replace("-", " ")


def _analysis_items() -> tuple[str, list[dict]]:
    items = [
        _row(
            "GEO.XYZ (Jan / Redmine)",
            "Ongoing",
            "ongoing",
            "Paid client project in technicals/geoxyz/. This batch is on the draft-PR branch. Next desk work is notes, not a hunt for a replacement contract.",
            action="Next: notes in 01_Build/studies/learns/jan-redmine/. Do not hunt a replacement contract.",
        ),
        _row(
            "KDE projects",
            "In progress",
            "progress",
            "New Qt / embedded work from KDE is in progress. Delivery path is studies → Empever when billed as training or embedded, Sevendyne when billed as a project desk.",
        ),
        _row(
            "RoR AI programme",
            "Learning ongoing",
            "ongoing",
            "Redmine / Rails maps and warehouse notes in studies/learns/jan-redmine/. Members pagination and IMAP maps are checked. Webhooks map is filled, not checked.",
            action="Fill / check maps, then warehouse notes. No new public post until the map is checked.",
        ),
        _row(
            "Research products",
            "Not started",
            "not_started",
            "01_Build/resources/ is idea folders only. Axxxx retail / robotics Operate desk is 2039 — do not create 04_Operate/Axxxx/ yet.",
        ),
        _row("Idea · food waste", "Idea", "idea", "Product R&D. Empty until a real file starts."),
        _row("Idea · home security", "Idea", "idea", "Product R&D. Empty until a real file starts."),
        _row("Idea · in-vehicle navigation", "Idea", "idea", "Product R&D. Empty until a real file starts."),
        _row("Idea · mobile workspace", "Idea", "idea", "Phone / web operator for these desks. Specs live in workspace/design/."),
        _row("Idea · portable solar", "Idea", "idea", "Product R&D. Empty until a real file starts."),
        _row("Idea · tbd_6 / tbd_7", "Idea", "idea", "Named when you start."),
    ]
    summary = "GEO.XYZ ongoing · KDE in progress · RoR AI learning · product ideas not started"
    return summary, items


def _content_items() -> tuple[str, list[dict]]:
    drafts_dir = WORKS / "02_Content" / "Posts" / "drafts"
    published = WORKS / "02_Content" / "Posts" / "published" / "log.json"
    items = [
        _row(
            "Members pagination",
            "Ready to post",
            "ready",
            "Map checked. Draft: blog-2026-08-25-redmine-members-pagination.md. Public copy stays generic — no project names.",
            action="Open the draft in 02_Content/Posts/drafts/. Publish by hand when you want it live.",
        ),
        _row(
            "Busy-instance field guide",
            "Ready to post",
            "ready",
            "Map checked. Draft: blog-2026-08-25-redmine-busy-instance-field-guide.md.",
            action="Open the draft in 02_Content/Posts/drafts/. Publish by hand when you want it live.",
        ),
        _row(
            "Mailbox OAuth (not user login)",
            "Ready to post",
            "ready",
            "IMAP map checked. Draft: blog-2026-08-26-redmine-imap-mailbox-oauth.md. Do not publish until you want it live.",
            action="Open the draft in 02_Content/Posts/drafts/. Publish by hand when you want it live.",
        ),
        _row(
            "Native webhooks",
            "Hold",
            "hold",
            "Map filled 21 Sep, not checked. No new public draft until the map is checked.",
        ),
        _row(
            "Wiki export / skip-is-a-skill",
            "Later in series",
            "progress",
            "After the first three posts. Series note: Posts/drafts/SERIES-from-port-commits.md.",
            lane="planned",
        ),
        _row(
            "Published this month",
            "None yet",
            "not_started",
            "Posts/published/log.json is empty.",
            lane="active",
            action="Nothing auto-publishes. When a map is checked, open the draft and post by hand (Dev.to / Medium / Hashnode). How: 04_Operate/Empever/notes/post-publishing.md.",
        ),
    ]
    extra = []
    if drafts_dir.is_dir():
        for path in sorted(drafts_dir.glob("*.md")):
            if path.name in SKIP_DRAFTS or path.name.startswith("blog-2026-08-25") or path.name.startswith("blog-2026-08-26"):
                continue
            extra.append(_row(path.name, "Draft in folder", "progress", _first_heading(path)))
    items.extend(extra[:4])
    pub_note = "no live posts yet"
    if published.is_file():
        try:
            raw = published.read_text(encoding="utf-8").strip()
            if raw and raw not in {"[]", "{}"}:
                pub_note = "published log has entries"
        except OSError:
            pass
    summary = f"Three posts ready · webhooks on hold · {pub_note}"
    return summary, items


def _network_items(mail: dict) -> tuple[str, list[dict]]:
    items = [
        _row(
            "Inboxes in scope",
            "One Gmail only",
            "mail",
            "aes37group@gmail.com. Sevendyne HR / marketing boxes stay off this desk. Nothing is sent from here.",
        )
    ]
    for box in mail.get("boxes") or []:
        if box.get("connected"):
            detail = f"{box.get('unseen') or 0} unread · {box.get('total') or 0} in inbox"
            items.append(_row(box["email"], "Connected", "mail", detail))
        else:
            items.append(
                _row(
                    box["email"],
                    "Not connected",
                    "hold",
                    box.get("error") or "Add a Gmail app password to the gitignored gmail_sync_accounts.json.",
                )
            )
    hits = mail.get("signals") or mail.get("client_hits") or []
    if hits:
        for hit in hits[:6]:
            chips = hit.get("signals") or []
            label = (chips[0]["label"] if chips else None) or "Inbox signal"
            items.append(
                _row(
                    hit.get("subject") or "(no subject)",
                    label,
                    "ongoing",
                    f"{hit.get('from')} · {hit.get('when') or hit.get('date') or ''}".strip(" ·"),
                )
            )
    else:
        items.append(
            _row(
                "Project / client signals",
                "None in the last headers" if mail.get("connected") else "Waiting for inbox login",
                "not_started" if mail.get("connected") else "hold",
                "Shows hiring, project need, payroll, training, and named-client threads from aes37group@gmail.com.",
            )
        )
    items.append(
        _row(
            "Named people from posts",
            "Empty table",
            "not_started",
            "03_Network/Leads/target-people.md has the headers only. Inbound and outbound still happen by hand.",
            lane="planned",
        )
    )
    connected = sum(1 for b in mail.get("boxes") or [] if b.get("connected"))
    summary = f"{connected}/1 inbox connected · {len(hits)} project/client signals"
    return summary, items


def _operate_items() -> tuple[str, list[dict]]:
    items = [
        _row(
            "GEO.XYZ project development",
            "Active · Sevendyne payroll",
            "live",
            "Paid client work in 01_Build/technicals/geoxyz/. Delivery and pay run through Sevendyne Consultancy Services LLP. This batch is on the draft-PR branch. Next is notes — do not hunt a replacement contract.",
            action="Status only on this desk. Tenant invoices and payroll figures stay in Sevendyne payrolls.",
        ),
        _row(
            "Ansif personal books",
            "Tax working papers",
            "ongoing",
            "04_Operate/Ansif/finance/ — salary, freelance receipts, interest, bank statements. Upload SBI/SIB PDF or Excel and categorise credits, debits, and interest.",
        ),
        _row(
            "Sevendyne Consultancy Services LLP",
            "Live",
            "live",
            "Talent consultancy since 2016. GEO.XYZ is one payroll desk. This card does not open tenant invoices or payouts.",
        ),
        _row(
            "Empever",
            "Under registration",
            "forming",
            "Training yeses bill here. Official launch 2028.",
            lane="planned",
        ),
    ]
    summary = "GEO.XYZ under Sevendyne payroll · Ansif personal income and tax on this desk"
    return summary, items


def report_for(spec: dict, mail: dict | None = None) -> dict:
    key = spec["id"]
    if key == "analysis":
        summary, items = _analysis_items()
    elif key == "content":
        summary, items = _content_items()
    elif key == "network":
        summary, items = _network_items(mail or mailbox_status(live=True))
    else:
        summary, items = _operate_items()
    return {
        "id": spec["id"],
        "title": spec["title"],
        "desk": spec["desk"],
        "href": spec["href"],
        "path": str(WORKS / spec["desk"]),
        "exists": (WORKS / spec["desk"]).is_dir(),
        "summary": summary,
        "now": spec["now"],
        "dashboard": spec.get("dashboard") or spec["href"],
        "dashboard_label": spec.get("dashboard_label") or ("Open " + spec["title"]),
        "items": items,
    }


def all_reports() -> list[dict]:
    return [report_for(spec) for spec in DESKS if spec["id"] == "operate"]


def one_report(app_id: str) -> dict | None:
    key = (app_id or "").strip().lower()
    mail = None
    if key == "network":
        mail = mailbox_status(live=True)
    for spec in DESKS:
        if spec["id"] == key:
            return report_for(spec, mail=mail)
    return None


def _shop_items() -> tuple[str, list[dict]]:
    items = [
        _row(
            "Desktop + phone",
            "Local now",
            "live",
            "Electron and Android are the operator for these desks. Server is localhost; cloud after it works well.",
            action="Keep the A app open. Phone uses http://ansif-workspace.local:4040/app/ on the same Wi-Fi.",
        ),
        _row(
            "This month’s rupees",
            "On the books",
            "ongoing",
            "Jan salary ₹1.90L (project ₹2.20L, Sevendyne fee ₹30k). Training target ₹50k–₹1L. Detail: 04_Operate/Ansif/finance/cash-flow.md.",
        ),
        _row(
            "Shop window",
            "Leftover",
            "progress",
            "Portfolio, résumé, GitHub Pages in 04_Operate/Ansif/. Not a hunt for a Jan replacement.",
        ),
        _row(
            "AES Group",
            "Later",
            "future",
            "Takes 10% Sevendyne / 20% Empever when the holding exists. Plan in 04_Operate/Ansif/aes-group/.",
        ),
        _row(
            "AnsAI",
            "2039",
            "future",
            "Robot company later. Do not create ansai/ now.",
        ),
        _row(
            "_referrals demos",
            "Not billed work",
            "idea",
            "Skill clones in 04_Operate/Ansif/profile/_referrals/. Demos only.",
        ),
    ]
    return "Desktop + phone local · salary on the books · AES / AnsAI later", items


def _split_lane(items: list[dict]) -> tuple[list[dict], list[dict]]:
    active = [i for i in items if i.get("lane") == "active"]
    planned = [i for i in items if i.get("lane") != "active"]
    return active, planned


def _section(sid: str, title: str, desk: str, blurb: str, summary: str, items: list[dict], href: str = "") -> dict:
    active, planned = _split_lane(items)
    return {
        "id": sid,
        "title": title,
        "desk": desk,
        "blurb": blurb,
        "summary": summary,
        "href": href,
        "exists": (WORKS / desk).is_dir(),
        "active": active,
        "planned": planned,
    }


def works_board() -> dict:
    """Operate desk only — personal profile, current work, books."""
    biz_sum, biz_items = _operate_items()
    return {
        "next": "GEO.XYZ development under Sevendyne payroll. Personal income and tax on this Operate desk.",
        "publish_how": "Nothing auto-publishes or auto-files. Bank PDFs are categorised here for working papers.",
        "host": "localhost",
        "sections": [
            _section("business", "Operate", "04_Operate/Ansif", "Personal profile, freelance, income and tax.", biz_sum, biz_items, "/app/operate.html"),
        ],
    }

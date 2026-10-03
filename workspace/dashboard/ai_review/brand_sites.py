"""Public-site post seeds. No nested client names, mailboxes, or internal hosts."""

SEVENDYNE_SITE = "https://www.sevendyne.com/"

SEVENDYNE_POSTS = (
    {
        "title": "Managed product engineering, not contractor placement",
        "body": (
            "Sevendyne has designed, built, and operated software products for remote clients since 2016. "
            "The offer is a full engineering team against the client's roadmap — development, QA, and delivery "
            "leadership under one desk — not placing individual contractors. Proof lives in the case studies "
            "on the public site."
        ),
    },
    {
        "title": "One Kochi floor: delivery teams and the training pipeline",
        "body": (
            "The Kochi office runs two things side by side: managed engineering teams on live client roadmaps, "
            "and a supervised training floor that feeds them. Same building, same delivery leads — so ramp-up, "
            "backup coverage, and bench strength sit in the team from day one."
        ),
    },
    {
        "title": "What the managed teams actually build in",
        "body": (
            "Public capabilities on the Sevendyne site include Qt, C++, Python, Java, Spring Boot, Laravel, "
            "Node.js, Angular, AI integration, and embedded work. Trading desks, logistics platforms, payments CRM, "
            "and industrial programmes are the kind of products those pods have run — for clients in Germany, "
            "the UK, UAE, Malaysia, Singapore, and India."
        ),
    },
    {
        "title": "Managed engineering versus staff augmentation",
        "body": (
            "Managed engineering means Sevendyne owns delivery with a cross-functional pod and a delivery lead. "
            "Staff augmentation places engineers when the client wants to direct the work. Both sit on the same "
            "Kochi floor; the difference is who holds the roadmap."
        ),
    },
    {
        "title": "The bench behind every managed team",
        "body": (
            "Paid programmes and internships on the Kochi floor build the engineers who staff managed teams. "
            "People intern here, then join a live client desk or a role Sevendyne helps them take elsewhere. "
            "That pipeline has run since 2016 — the same year the remote-client desks started."
        ),
    },
)

DUMMY_POSTS = (
    {
        "title": "A demo firm on the Empever desk",
        "body": (
            "Dummy Client is the second SaaS tenant on Empever — used to prove that one firm's posts, leads, "
            "and nested desks stay off another firm's home. Drafts here are for the demo workspace only."
        ),
    },
)


def posts_for(tenant_id: str) -> tuple[dict, ...]:
    key = (tenant_id or "").strip().lower()
    if key == "sevendyne":
        return SEVENDYNE_POSTS
    if key == "dummy_client":
        return DUMMY_POSTS
    return ()


def source_url(tenant_id: str) -> str:
    if (tenant_id or "").strip().lower() == "sevendyne":
        return SEVENDYNE_SITE
    return ""

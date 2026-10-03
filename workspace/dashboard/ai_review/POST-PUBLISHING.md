# Post publishing — what to do next

**Live:** 2026-09-23  
**Internal Operate note.** Not a public post. Do not copy nested client names, mailboxes, or hosts into `02_Content/Posts/`.

Hub home and the admin inbox show **drafts**. Approve does **not** publish yet because no platform keys are stored. `platforms` is empty; `platform_posts` is empty. Super-admin home therefore shows `pending · 0 views`.

---

## Who can publish

| Role | What happens |
|------|----------------|
| **Tenant admin** (`sevendyne` on `app.sevendyne.com`, `dummy` on dummy host) | Only they can Approve / Edit / Skip. Approve of a **post** is what would call the APIs. |
| **Super admin** (`empever`, `ansif`) | Sees titles and counts. Cannot approve. Never auto-publishes. |
| **Nested client / staff** | No Analysis, no Leads, no digest. |

Policy still runs before send: named nested clients, mailboxes, and internal hosts **block** the job. Approve all skips payroll.

---

## Platforms

### Official APIs (wired, waiting for keys)

Code: `saas_project/dashboard/ai_review/adapters.py`. On Approve of a `post_draft`, `_publish_post` loops **active** rows in `platforms` for that SaaS tenant.

| Platform | Adapter key | Credentials to store | What Approve does | What the daily run then does |
|----------|-------------|----------------------|-------------------|------------------------------|
| **Dev.to** | `devto` | `api_key` from [dev.to/settings/extensions](https://dev.to/settings/extensions) | `POST https://dev.to/api/articles` with `published: true` | GET article → views, reactions, comments |
| **Hashnode** | `hashnode` | `token` (personal access token) + `publication_id` from Hashnode developer settings | GraphQL `publishPost` at `https://gql.hashnode.com/` | GraphQL post → views, reactions, comments |

Each **SaaS tenant** needs its own keys (Sevendyne’s Dev.to vs Dummy’s). Do not reuse one key across tenants.

There is **no hub form** yet. `Store.add_platform` seals the JSON with `.run/auth-secret`. One-shot from `dashboard/` (paste keys locally, do not commit):

```python
from ai_review.store import Store
Store().add_platform(
    tenant_id="sevendyne",
    name="Dev.to",
    adapter_key="devto",
    credentials={"api_key": "…"},
)
Store().add_platform(
    tenant_id="sevendyne",
    name="Hashnode",
    adapter_key="hashnode",
    credentials={"token": "…", "publication_id": "…"},
)
```

Then tenant admin Approves a post. Status becomes **sent** if at least one adapter returns an id/url; otherwise **approved** (local only). Failed publishes store `platform_posts.status = failed` and an adapter error in `adapter_health`.

### Compose-only (no unofficial API)

Analysis → **3 Post** only opens a compose tab. Paste by hand. Views will not appear on the hub until a real adapter row exists.

| Platform | Compose URL | API? |
|----------|-------------|------|
| LinkedIn | `https://www.linkedin.com/feed/` | No (do not scrape / unofficial) |
| Medium | `https://medium.com/new-story` | Not wired |
| X / Twitter | `https://twitter.com/compose/tweet` | Not wired |

### Gmail (replies, not blog posts)

`GmailAdapter` fetches threads and sends a reply. Needs an OAuth **access_token**, not a blog API key. Same `platforms` table with `adapter_key = gmail`. Not required for the five Sevendyne site stories.

---

## What you will see after keys + Approve

1. Tenant admin inbox: post job **sent**.
2. Super-admin / Sevendyne home: status **sent**, **views** fill on the next daily AI run (`POST /api/ai/run` or the once-per-day path).
3. Analysis → **Blog stories** (`/analyse/?view=stories`): same drafts plus live URL/views when `platform_posts` exists.
4. Click a story on home → Analysis Blog stories.

Until keys exist, Approve only marks the sqlite job approved. Nothing hits Dev.to or Hashnode.

---

## Order of work (when leftover time)

1. Create a **Sevendyne** Dev.to API key (and Hashnode token + publication id if that blog is in use).
2. Run `add_platform` locally, confirm a row in `platforms` (credentials stay sealed — do not print them).
3. Same for **dummy_client** only if you want the demo tenant to publish.
4. Tenant admin: Approve **one** Sevendyne public-site story (no nested names, no `@` mailboxes).
5. Check the live Dev.to/Hashnode URL, then home **views**.
6. Later: a small tenant-admin “connected accounts” form so keys are not pasted in a Python shell. Super admin should still not see those secrets (same rule as hiding Sevendyne logins).

Do **not** auto-publish, auto-mail, or auto-send payroll. LinkedIn / forums stay manual.

# Ansif OS — Analysis, Leads, hub

**Live:** 2026-09-30  
Source for the desk apps that are **not** Sevendyne payroll.

| App | This folder | What |
|-----|-------------|------|
| Hub | `dashboard/` | Login, digest, stats home |
| Analysis | `analysis/` | Work + notes (`coding-agent`) |
| Leads | `leads/` | Posts + Network (`leads-crm`) |
| Automate | `automate/` | Playwright operator (not a fourth product) |

**Sevendyne Operates** (invoices, payouts, staff, bank ledger) stays in `04_Operate/Empever/saas_project/payroll-hrms/`. The live desk is [app.sevendyne.com](https://app.sevendyne.com) — that host opens Operates as home.

This tree is also pushed to [ansifi.github.io/os/](https://ansifi.github.io/os/) (`ansifi/ansifi.github.io`). GitHub Pages does **not** run the Python/Node servers. Run them from this folder or from `saas_project` on localhost.

Do not put payroll sqlite, invoice PDFs, `.env`, or `leads-board.json` here.

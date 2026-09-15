# LeakSnap — Project Context (read this first in Cursor)

## What this is
A tool that scans a business website for 4 "revenue leak" flaws (missing
tracking pixel, no mobile-friendly contact form, no booking system, slow
load speed) and turns that into a lead-gen mechanism, sold two ways:

1. **White-label widget** (`backend/` + `widget/`) — a `<script>` tag
   agencies (e.g. Adexorb, IndexGraph) embed on their own site. Visitor
   scans a URL, sees 1 free flaw, trades email for the full report, agency
   captures the lead. This is the priority build — two real agency owners
   have agreed to try it once it's ready.
2. **Standalone site** (`docs/standalone-static/index.html`) — same scan
   engine, but as your own direct-to-business-owner product (paywall at
   $99 instead of email-gate). Secondary, not currently being built out.

## Business goal
$5,000 in 30 days. Primary path now: sell the white-label widget to small
web-dev/SEO/local-marketing agencies as a $500-800 one-time integration +
$150/mo upsell. Two agencies (Adexorb, IndexGraph — both small web-dev/SEO
shops) have verbally agreed to trial it before paying. Getting them live
and getting a testimonial is the immediate priority — everything else
(more agencies, standalone site) comes after that proof point.

## Current state (as of last handoff)
- `backend/scanner.py` — flaw detection logic, tested against live sites, works.
- `backend/app.py` — Flask API:
  - `/api/scan` teaser (rate-limited)
  - `/api/lead` email-gated full report, SQLite `leads.db`, tagged by `agency_id`
  - `/widget/embed.js` served from the same origin (one Render URL is enough)
  - `/admin/leads` and `/admin/snippet` behind `ADMIN_TOKEN`
  - optional Resend email to the agency (`RESEND_API_KEY` + `notification_email` in `agencies.json`)
- `widget/embed.js` — floating button + modal, inline validation, optional
  `data-powered-by="true"` footer. Demo loads the widget from the API origin.
- `render.yaml` + `backend/Procfile` ready for Render/Railway. **Not deployed yet.**

## Immediate next steps (in priority order)
1. Deploy `backend/` on Render (Blueprint from `render.yaml`, or Web Service
   with Root Directory `backend`). Copy `ADMIN_TOKEN` from the dashboard.
2. Open `https://YOUR-APP.onrender.com/admin/snippet?token=ADMIN_TOKEN`, send
   Adexorb + IndexGraph their snippets. Fill `notification_email` in
   `backend/agencies.json` and set `RESEND_API_KEY` / `FROM_EMAIL` when you
   want email alerts.
3. Confirm the widget on a real external site (not just demo.html).
4. Once one lead comes through, that's the testimonial — pitch the next 5-8 agencies.

## TODO / backlog
- [x] Swap `leads.csv` for SQLite once volume starts (Postgres still later).
- [x] Add an `agencies` config (`backend/agencies.json`: id -> branding, notification email).
- [x] Auto-email the agency when a new lead lands (Resend; skipped if no API key).
- [x] Rate-limit `/api/scan` — public unauthenticated endpoint.
- [ ] Minify/bundle `embed.js` before shipping to a real client site.
- [ ] Add PDF export of the unlocked report (WeasyPrint).
- [x] Simple admin view to read leads without shell access (`/admin/leads`).
- [x] Optional "powered by LeakSnap" footer in the modal (`data-powered-by="true"`).
- [ ] Postgres + persistent disk before >1 agency is paying (Render free FS is ephemeral).

## Run locally
```bash
cd backend && pip install -r requirements.txt
set ADMIN_TOKEN=dev-admin
set FLASK_DEBUG=1
python app.py   # :5001
# open http://localhost:8000 is no longer required for the widget file —
# demo.html loads embed.js from :5001. You can still serve docs/ if you want:
#   python -m http.server 8000
# then open docs/demo.html, or just open the file and use the :5001 script src.
```
Admin (local): http://localhost:5001/admin/leads?token=dev-admin
NOTE: fill notification_email for adexorb + indexgraph with their real emails before relying on auto-notify (or leave blank and just check /admin/leads manually).

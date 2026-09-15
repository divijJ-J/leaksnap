You are picking up an existing, partially-live project called LeakSnap. Read this whole prompt before doing anything — it has everything you need.

## Business context
DiviJ is running a B2B lead-gen/data-broker business with a $5,000-in-30-days goal, $0 upfront spend. The core insight: local service businesses (roofers, med spas, solar installers, etc.) often have broken website infrastructure — no ad tracking, no mobile-friendly contact form, no booking system, slow load speed — and small web-dev/SEO/marketing agencies who already sell fixes to these businesses are the buyer, not the end business owner directly.

The product being sold is a white-label embeddable widget ("LeakSnap") that agencies put on their own site. A visitor pastes their website URL into a popup, sees one free flaw, then trades their email for the full report — the agency gets a warm, pre-qualified lead. Pricing model: $500-800 one-time integration + $150/mo hosting/maintenance upsell, per agency.

Two real agency owners — Adexorb and IndexGraph (small web-dev/SEO/AI-visibility shops) — have verbally agreed to trial it. Getting them live and turning that into a testimonial is the current priority; more agencies come after that proof point. Prospecting sources for finding more agencies like these: Clutch.co, DesignRush.com, GoodFirms.co, UpCity.com, TechBehemoths.com (filter by "small business," "local SEO," "web development").

## What's already built and live (do not rebuild from scratch — extend this)

**GitHub repo:** https://github.com/divijJ-J/leaksnap (main branch)

**Live backend API (Render):** https://leaksnap-api.onrender.com
  - `POST /api/scan` — teaser scan, 1 flaw shown free, rest locked. Body: `{url, agency_id}`.
  - `POST /api/lead` — email-gated full report, saves lead to SQLite. Body: `{url, name, email, agency_id}`.
  - `GET /widget/embed.js` — serves the embed script from this same origin.
  - `GET /admin/leads?token=ADMIN_TOKEN` — HTML view of captured leads.
  - `GET /admin/snippet?token=ADMIN_TOKEN` — copy-paste embed snippets per agency.
  - `GET /admin/activate?agency_id=X&token=ADMIN_TOKEN` — marks an agency as paid (bypasses trial expiry).
  - `GET /health` — deploy health check.
  - Admin token (current): `leaksnap-admin-2026-secure`

**Trial/paywall logic (already implemented and tested):**
  - First request from a new `agency_id` auto-starts a 7-day trial (stored in SQLite `agency_status` table, tracked by `first_seen`).
  - After 7 days, `/api/scan` and `/api/lead` return HTTP 402 with `{"error": "Trial expired (7 days). Contact us to activate."}` unless the agency has been marked `active=1`.
  - `/admin/activate` is how you (the operator) manually flip an agency from trial to paid once they pay — no code change needed, just hit that URL.
  - `TRIAL_DAYS` is configurable via env var (default 7).

**Live animated sales demo (Render static site):** https://leaksnap-demo.onrender.com/demo-video.html
  - 5-scene self-playing loop (~18s): (1) problem hook, (2) LeakSnap brand intro, (3) simulated live scan revealing 4 flaws, (4) email-gated unlock/lead-capture, (5) CTA with pricing ($500-800 + $150/mo, 7-day trial). Pure CSS/JS animation, no video file — meant to be screen-recorded or linked directly.
  - Also in the same `docs/` folder: `demo.html` (a working, non-simulated embed test page using a real `demo-agency` agency_id against the real API) and `standalone-static/index.html` (an alternate direct-to-business-owner product, $99 paywall instead of email-gate — secondary, not being actively built out).

**Repo structure:**
```
backend/
  app.py           Flask API — see endpoints above
  scanner.py       Core flaw-detection logic (regex-based: pixel/GA4 detection,
                    viewport+form detection, booking-widget detection, response-time check)
  db.py            (superseded — SQLite logic now lives inline in app.py)
  agencies.json    Per-agency branding config: {id: {name, notification_email, accent}}.
                    Currently has demo-agency, adexorb, indexgraph — all with empty
                    notification_email (TODO: fill with real emails if using Resend alerts)
  requirements.txt flask, flask-cors, requests, gunicorn, jinja2
  Procfile / the app is deployed via Render's Python runtime, not Procfile directly
widget/
  embed.js         The single <script> tag agencies paste on their site. Floating button
                    -> modal -> calls /api/scan then /api/lead. Sends agency_id on both
                    calls (required for trial-gating to work). Handles HTTP 402 by showing
                    "This trial has ended. Contact us to keep it active."
docs/
  demo.html            Local/live test harness loading the widget against the real API
  demo-video.html      The 5-scene animated sales reel described above
  standalone-static/index.html   Secondary direct-to-owner product (not priority)
render.yaml        Render Blueprint config (references backend/ as root via build/start
                    commands, NOT Render's native rootDir — that setting isn't exposed
                    via the MCP tool used to deploy, so build/start commands do
                    `cd backend && ...` instead)
.gitignore
CONTEXT.md          An earlier version of this same context file — this prompt supersedes it
```

**Two Render services currently live:**
  - `leaksnap-api` (web service) — the backend, buildCommand `pip install -r backend/requirements.txt`, startCommand `cd backend && gunicorn app:app --bind 0.0.0.0:$PORT --timeout 30`
  - `leaksnap-demo` (static site) — serves the `docs/` folder, publishPath `docs`
  - Note: an earlier misconfigured service also named `leaksnap` (without working build paths) was created first and abandoned — it's still sitting in the Render dashboard unused and can be deleted manually (no delete-service tool was available via MCP at the time).

## Known gaps / not yet done
  - `notification_email` fields in `agencies.json` are empty — no auto-email-on-lead yet (Resend integration exists in code via `RESEND_API_KEY`/`FROM_EMAIL` env vars but is inert until keys + emails are set).
  - `embed.js` is not minified/bundled.
  - No PDF export of the unlocked report.
  - No real auth on `/admin/*` beyond a static token in the URL — fine for now, not hardened.
  - Adexorb and IndexGraph have NOT yet actually embedded the snippet on their live sites — they've only verbally agreed. Nobody outside the operator has tested it live yet.
  - SQLite (not Postgres) — Render's free-tier filesystem is ephemeral, so the `leads.db` file and trial-status data will be wiped on redeploy/restart. This is fine for a short trial period but is a real risk if this runs long — flag it if asked to scale this up.

## What to do with this prompt
Treat everything above as ground truth about the current state. Don't rebuild the scanner, widget, or paywall from zero — read/extend the actual files in the repo. If asked to continue development, prioritize in this order: (1) get the snippet actually live on Adexorb's or IndexGraph's site and confirm a real lead comes through, (2) fix the ephemeral-SQLite risk before this scales past a couple of agencies, (3) everything else in "Known gaps" above.

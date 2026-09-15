You are picking up an existing, live project called LeakSnap. This prompt is fully self-contained — every file's actual code is inlined below. You do not need GitHub access, prior conversation history, or any other context to act on this.

## Business context
DiviJ is running a B2B lead-gen business with a $5,000-in-30-days goal, $0 upfront spend. Core insight: local
service businesses (roofers, med spas, solar installers) often have broken website infrastructure - no ad
tracking, no mobile-friendly contact form, no booking system, slow load speed. Small web-dev/SEO/marketing
agencies who already sell fixes to these businesses are the buyer, not the end business owner directly.

Product: a white-label embeddable widget ("LeakSnap") agencies put on their own site. A visitor pastes a URL,
sees one free flaw, trades email for the full report - the agency gets a warm lead. Pricing: $500-800 one-time
integration + $150/mo hosting/maintenance upsell, per agency, with a 7-day free trial per agency before paywall
kicks in.

Two real agencies - Adexorb and IndexGraph (small web-dev/SEO/AI-visibility shops) - verbally agreed to trial it.
Getting them live and turning that into a testimonial is the current priority. More-agency prospecting sources:
Clutch.co, DesignRush.com, GoodFirms.co, UpCity.com, TechBehemoths.com.

## Live infrastructure (already deployed - do not redeploy from scratch)
- GitHub repo: https://github.com/divijJ-J/leaksnap (main branch)
- Backend API (Render web service "leaksnap-api"): https://leaksnap-api.onrender.com
- Animated sales demo (Render static site "leaksnap-demo"): https://leaksnap-demo.onrender.com/demo-video.html
- Admin token (current): leaksnap-admin-2026-secure
- Render workspace ID: tea-dak2qfgae00c73es4ldg
- Note: an earlier misconfigured Render service also named "leaksnap" (broken build paths, code was at repo
  root instead of backend/) was abandoned and is still sitting unused in the dashboard - safe to delete manually.

## Known gaps (in priority order)
1. Adexorb/IndexGraph have NOT actually embedded the snippet yet - only verbally agreed. No real external lead yet.
2. SQLite on Render free tier is EPHEMERAL - leads.db and trial-status wipe on redeploy/restart. Fine short-term,
   real risk if this scales past a couple agencies. Migrate to Postgres before then.
3. notification_email fields in agencies.json are empty - no auto-email-on-lead yet (Resend code exists, inert
   until RESEND_API_KEY/FROM_EMAIL env vars + real emails are set).
4. embed.js is not minified/bundled.
5. No PDF export of the unlocked report.
6. /admin/* auth is just a static token in the URL - fine for now, not hardened.

## Full file contents (exact current state of the repo)

### FILE: render.yaml
```
services:
  - type: web
    name: leaksnap
    runtime: python
    plan: free
    rootDir: backend
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn app:app --bind 0.0.0.0:$PORT --timeout 30
    healthCheckPath: /health
    envVars:
      - key: ADMIN_TOKEN
        generateValue: true
      - key: PYTHON_VERSION
        value: "3.12.0"

```

### FILE: .gitignore
```
__pycache__/
*.pyc
.venv/
venv/
leads.csv
leads.db
.env

```

### FILE: backend/requirements.txt
```
flask
flask-cors
requests
gunicorn
jinja2

```

### FILE: backend/agencies.json
```
{
  "demo-agency": {
    "name": "Demo Agency",
    "notification_email": "",
    "accent": "#ff5a3c"
  },
  "adexorb": {
    "name": "Adexorb",
    "notification_email": "",
    "accent": "#ff5a3c"
  },
  "indexgraph": {
    "name": "IndexGraph",
    "notification_email": "",
    "accent": "#ff5a3c"
  }
}

```

### FILE: backend/scanner.py
```
"""
SiteLeakCheck — core scanner logic.
Given a URL, fetches the page and checks for the 4 key "revenue leak" flaws:
1. No conversion tracking (Meta Pixel / Google Ads / GA4)
2. No mobile-friendly contact form
3. No booking/scheduling automation
4. Slow load speed
"""
import re
import time
import requests

TIMEOUT = 10

PIXEL_PATTERNS = [
    r"fbq\(", r"connect\.facebook\.net", r"gtag\(",
    r"googletagmanager\.com", r"google-analytics\.com", r"snap\.licdn\.com",
]

BOOKING_PATTERNS = [
    r"calendly\.com", r"acuityscheduling\.com", r"squareup\.com/appointments",
    r"book(ing)?[-_ ]?now", r"schedule[-_ ]?(an?[-_ ]?)?appointment",
    r"setmore\.com", r"square site",
]

def fetch_site(url: str):
    if not url.startswith("http"):
        url = "https://" + url
    start = time.time()
    try:
        resp = requests.get(
            url, timeout=TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0 (SiteLeakCheck Bot)"},
            allow_redirects=True,
        )
        elapsed = time.time() - start
        return resp.text, elapsed, resp.status_code, None
    except requests.RequestException as e:
        return None, None, None, str(e)


def check_pixel(html: str):
    found = any(re.search(p, html, re.I) for p in PIXEL_PATTERNS)
    return {
        "flaw": "No conversion tracking detected",
        "present": found,
        "detail": "No Meta Pixel / Google Ads / GA4 tag found in page source — ad spend may be running blind."
        if not found else "Tracking tag(s) detected.",
    }


def check_mobile_form(html: str):
    has_viewport = bool(re.search(r'<meta[^>]+name=["\']viewport["\']', html, re.I))
    has_form = bool(re.search(r"<form\b", html, re.I))
    ok = has_viewport and has_form
    return {
        "flaw": "No mobile-friendly contact form",
        "present": not ok,
        "detail": (
            "No mobile viewport tag found — site likely isn't optimized for phones." if not has_viewport
            else "No <form> element detected on the page — visitors may have no way to contact the business."
            if not has_form else "Viewport tag and a contact form were both detected."
        ),
    }


def check_booking(html: str):
    found = any(re.search(p, html, re.I) for p in BOOKING_PATTERNS)
    return {
        "flaw": "No booking/scheduling automation",
        "present": not found,
        "detail": "No booking widget (Calendly, Acuity, Square, etc.) detected — after-hours leads are likely lost."
        if not found else "Booking/scheduling system detected.",
    }


def check_speed(elapsed: float):
    slow = elapsed is not None and elapsed > 3.0
    return {
        "flaw": "Slow page load speed",
        "present": slow,
        "detail": f"Page took {elapsed:.2f}s to respond — over the 3s threshold that hurts conversions and paid ad Quality Score."
        if slow else f"Page responded in {elapsed:.2f}s — within acceptable range." if elapsed is not None else "Could not measure.",
    }


def scan(url: str):
    html, elapsed, status, error = fetch_site(url)
    if error:
        return {"url": url, "error": error}

    checks = [
        check_pixel(html),
        check_mobile_form(html),
        check_booking(html),
        check_speed(elapsed),
    ]
    flaw_count = sum(1 for c in checks if c["present"])
    return {
        "url": url,
        "status_code": status,
        "load_time_sec": round(elapsed, 2) if elapsed else None,
        "flaws_found": flaw_count,
        "checks": checks,
    }


if __name__ == "__main__":
    import sys, json
    target = sys.argv[1] if len(sys.argv) > 1 else "example.com"
    print(json.dumps(scan(target), indent=2))

```

### FILE: backend/app.py
```
"""
LeakSnap Widget Backend — white-label API for embeddable "Free Website Audit" widgets.

Endpoints:
  POST /api/scan        teaser scan (1 unlocked flaw)
  POST /api/lead        email-gated full report + persist lead
  GET  /health          deploy health check
  GET  /widget/embed.js served from this same origin so one deploy is enough
  GET  /admin/leads     HTML lead list (requires ADMIN_TOKEN)
  GET  /admin/snippet   copy-paste embed snippets per agency
"""
from flask import Flask, request, jsonify, send_from_directory, render_template_string
from flask_cors import CORS
from scanner import scan
import os
import re
import sqlite3
import datetime
import threading
import time
import json
import requests as http_requests

app = Flask(__name__)
CORS(app)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BACKEND_DIR, "leads.db")
AGENCIES_FILE = os.path.join(BACKEND_DIR, "agencies.json")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
FROM_EMAIL = os.environ.get("FROM_EMAIL", "LeakSnap <noreply@leaksnap.dev>")
RATE_LIMIT = int(os.environ.get("SCAN_RATE_LIMIT", "10"))
RATE_WINDOW = int(os.environ.get("SCAN_RATE_WINDOW", "60"))

_rate_lock = threading.Lock()
_rate_hits = {}  # ip -> [timestamps]


def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


TRIAL_DAYS = int(os.environ.get("TRIAL_DAYS", "7"))


def _init_db():
    conn = _db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            agency_id TEXT NOT NULL,
            name TEXT,
            email TEXT NOT NULL,
            scanned_url TEXT NOT NULL,
            flaws_found INTEGER
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS agency_status (
            agency_id TEXT PRIMARY KEY,
            first_seen TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.commit()
    conn.close()


def _check_access(agency_id):
    """Returns (allowed: bool, reason: str|None). Lazily starts the trial
    clock on an agency's first request, then blocks once trial expires
    unless it's been marked active (paid) via /admin/activate."""
    conn = _db()
    row = conn.execute(
        "SELECT * FROM agency_status WHERE agency_id = ?", (agency_id,)
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO agency_status (agency_id, first_seen, active) VALUES (?, ?, 0)",
            (agency_id, datetime.datetime.utcnow().isoformat()),
        )
        conn.commit()
        conn.close()
        return True, None

    if row["active"]:
        conn.close()
        return True, None

    first_seen = datetime.datetime.fromisoformat(row["first_seen"])
    days_elapsed = (datetime.datetime.utcnow() - first_seen).days
    conn.close()
    if days_elapsed >= TRIAL_DAYS:
        return False, f"Trial expired ({TRIAL_DAYS} days). Contact us to activate."
    return True, None


def _load_agencies():
    if not os.path.exists(AGENCIES_FILE):
        return {}
    with open(AGENCIES_FILE, encoding="utf-8") as f:
        return json.load(f)


def _client_ip():
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _rate_limited():
    ip = _client_ip()
    now = time.time()
    with _rate_lock:
        hits = [t for t in _rate_hits.get(ip, []) if now - t < RATE_WINDOW]
        if len(hits) >= RATE_LIMIT:
            _rate_hits[ip] = hits
            return True
        hits.append(now)
        _rate_hits[ip] = hits
        if len(_rate_hits) > 5000:
            stale = [k for k, v in _rate_hits.items() if not v or now - v[-1] > RATE_WINDOW]
            for k in stale:
                _rate_hits.pop(k, None)
        return False


def _valid_email(email):
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


def _admin_ok():
    if not ADMIN_TOKEN:
        return False
    token = request.args.get("token") or request.headers.get("Authorization", "").replace("Bearer ", "")
    return token == ADMIN_TOKEN


def _notify_agency(agency_id, name, email, url, flaws_found):
    agencies = _load_agencies()
    agency = agencies.get(agency_id) or {}
    to_email = agency.get("notification_email")
    if not RESEND_API_KEY or not to_email:
        return
    agency_name = agency.get("name") or agency_id
    try:
        http_requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": FROM_EMAIL,
                "to": [to_email],
                "subject": f"New LeakSnap lead for {agency_name}",
                "text": (
                    f"New website audit lead\n\n"
                    f"Agency: {agency_name}\n"
                    f"Name: {name or '(none)'}\n"
                    f"Email: {email}\n"
                    f"Scanned: {url}\n"
                    f"Flaws found: {flaws_found}\n"
                ),
            },
            timeout=8,
        )
    except http_requests.RequestException:
        app.logger.exception("Failed to notify agency %s", agency_id)


_init_db()


@app.route("/api/scan", methods=["POST"])
def api_scan():
    if _rate_limited():
        return jsonify({"error": "Too many scans. Try again in a minute."}), 429

    data = request.get_json(force=True, silent=True) or {}
    url = (data.get("url") or "").strip()
    agency_id = (data.get("agency_id") or "unknown").strip() or "unknown"
    if not url:
        return jsonify({"error": "Missing url"}), 400

    allowed, reason = _check_access(agency_id)
    if not allowed:
        return jsonify({"error": reason}), 402

    result = scan(url)
    if "error" in result:
        return jsonify(result), 400

    teaser = dict(result)
    teaser["checks"] = [
        c if i == 0 else {"flaw": c["flaw"], "present": c["present"], "detail": "🔒 unlock full report"}
        for i, c in enumerate(result["checks"])
    ]
    return jsonify(teaser)


@app.route("/api/lead", methods=["POST"])
def api_lead():
    if _rate_limited():
        return jsonify({"error": "Too many requests. Try again in a minute."}), 429

    data = request.get_json(force=True, silent=True) or {}
    url = (data.get("url") or "").strip()
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    agency_id = (data.get("agency_id") or "unknown").strip() or "unknown"

    if not url or not email:
        return jsonify({"error": "Missing url or email"}), 400
    if not _valid_email(email):
        return jsonify({"error": "Invalid email"}), 400

    allowed, reason = _check_access(agency_id)
    if not allowed:
        return jsonify({"error": reason}), 402

    result = scan(url)
    if "error" in result:
        return jsonify(result), 400

    conn = _db()
    conn.execute(
        "INSERT INTO leads (timestamp, agency_id, name, email, scanned_url, flaws_found) VALUES (?, ?, ?, ?, ?, ?)",
        [
            datetime.datetime.utcnow().isoformat(),
            agency_id,
            name,
            email,
            url,
            result["flaws_found"],
        ],
    )
    conn.commit()
    conn.close()

    _notify_agency(agency_id, name, email, url, result["flaws_found"])
    return jsonify(result)


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/widget/embed.js")
def embed_js():
    return send_from_directory(os.path.join(ROOT, "widget"), "embed.js", mimetype="application/javascript")


ADMIN_LEADS_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>LeakSnap leads</title>
<style>
  body { font-family: sans-serif; background:#0b0f14; color:#e8edf2; padding:32px; }
  table { border-collapse: collapse; width:100%; }
  th, td { text-align:left; padding:8px 10px; border-bottom:1px solid #22303f; font-size:14px; }
  th { color:#8ea0b3; }
  a { color:#ff5a3c; }
</style>
</head>
<body>
<h1>Leads ({{ rows|length }})</h1>
<p><a href="/admin/snippet?token={{ token }}">Embed snippets</a></p>
<table>
  <tr><th>When</th><th>Agency</th><th>Name</th><th>Email</th><th>URL</th><th>Flaws</th></tr>
  {% for r in rows %}
  <tr>
    <td>{{ r.timestamp }}</td>
    <td>{{ r.agency_id }}</td>
    <td>{{ r.name }}</td>
    <td>{{ r.email }}</td>
    <td>{{ r.scanned_url }}</td>
    <td>{{ r.flaws_found }}</td>
  </tr>
  {% endfor %}
</table>
</body>
</html>
"""

SNIPPET_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>LeakSnap embed snippets</title>
<style>
  body { font-family: sans-serif; background:#0b0f14; color:#e8edf2; padding:32px; max-width:820px; }
  pre { background:#12181f; padding:16px; overflow:auto; border-radius:8px; }
  a { color:#ff5a3c; }
</style>
</head>
<body>
<h1>Agency embed snippets</h1>
<p>Paste this on the agency site. API + widget both come from <code>{{ base }}</code>.</p>
<p><a href="/admin/leads?token={{ token }}">Back to leads</a></p>
{% for id, agency in agencies.items() %}
  <h3>{{ agency.name }} (<code>{{ id }}</code>)</h3>
  <pre>&lt;script src="{{ base }}/widget/embed.js"
        data-agency-id="{{ id }}"
        data-api-base="{{ base }}"
        data-accent="{{ agency.accent or '#ff5a3c' }}"&gt;&lt;/script&gt;</pre>
{% endfor %}
</body>
</html>
"""


@app.route("/admin/activate")
def admin_activate():
    if not _admin_ok():
        return jsonify({"error": "Unauthorized. Set ADMIN_TOKEN and pass ?token="}), 401
    agency_id = request.args.get("agency_id", "").strip()
    if not agency_id:
        return jsonify({"error": "Missing agency_id"}), 400
    conn = _db()
    conn.execute(
        "INSERT INTO agency_status (agency_id, first_seen, active) VALUES (?, ?, 1) "
        "ON CONFLICT(agency_id) DO UPDATE SET active = 1",
        (agency_id, datetime.datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()
    return jsonify({"agency_id": agency_id, "active": True})


@app.route("/admin/leads")
def admin_leads():
    if not _admin_ok():
        return jsonify({"error": "Unauthorized. Set ADMIN_TOKEN and pass ?token="}), 401
    conn = _db()
    rows = [dict(r) for r in conn.execute("SELECT * FROM leads ORDER BY id DESC").fetchall()]
    conn.close()
    return render_template_string(
        ADMIN_LEADS_HTML,
        rows=rows,
        token=request.args.get("token", ""),
    )


@app.route("/admin/snippet")
def admin_snippet():
    if not _admin_ok():
        return jsonify({"error": "Unauthorized. Set ADMIN_TOKEN and pass ?token="}), 401
    base = request.host_url.rstrip("/")
    if request.headers.get("X-Forwarded-Proto") == "https" and base.startswith("http://"):
        base = "https://" + base[len("http://"):]
    return render_template_string(
        SNIPPET_HTML,
        agencies=_load_agencies(),
        base=base,
        token=request.args.get("token", ""),
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")

```

### FILE: widget/embed.js
```
/**
 * LeakSnap Embed Widget
 * -----------------------
 * Agencies paste this on their site:
 *
 *   <script src="https://YOUR-DOMAIN/widget/embed.js"
 *           data-agency-id="adexorb"
 *           data-api-base="https://YOUR-DOMAIN"
 *           data-accent="#ff5a3c"
 *           data-powered-by="true"></script>
 *
 * It injects a floating "Free Website Audit" button (bottom-right) that opens
 * a modal: URL input -> free teaser flaw -> email-gated full report.
 * Every submitted lead is captured server-side, tagged with data-agency-id.
 */
(function () {
  var scriptTag = document.currentScript;
  var AGENCY_ID = scriptTag.getAttribute("data-agency-id") || "unknown";
  var API_BASE = (scriptTag.getAttribute("data-api-base") || "").replace(/\/$/, "");
  var ACCENT = scriptTag.getAttribute("data-accent") || "#ff5a3c";
  var POWERED_BY = (scriptTag.getAttribute("data-powered-by") || "false").toLowerCase() === "true";

  var css = `
    .lsw-btn { position:fixed; bottom:24px; right:24px; z-index:999999; background:${ACCENT};
      color:#fff; border:none; padding:14px 20px; border-radius:999px; font-family:sans-serif;
      font-weight:600; font-size:14px; cursor:pointer; box-shadow:0 6px 20px rgba(0,0,0,.25); }
    .lsw-overlay { position:fixed; inset:0; background:rgba(0,0,0,.6); z-index:999998;
      display:none; align-items:center; justify-content:center; }
    .lsw-modal { background:#12181f; color:#e8edf2; width:min(420px,90vw); border-radius:14px;
      padding:24px; font-family:sans-serif; max-height:85vh; overflow:auto; }
    .lsw-modal h3 { margin-top:0; }
    .lsw-modal input { width:100%; padding:12px; border-radius:8px; border:1px solid #2a3947;
      background:#0f151d; color:#e8edf2; margin-bottom:10px; box-sizing:border-box; }
    .lsw-modal button.lsw-submit { width:100%; padding:12px; border:none; border-radius:8px;
      background:${ACCENT}; color:#fff; font-weight:700; cursor:pointer; }
    .lsw-close { float:right; cursor:pointer; color:#8ea0b3; }
    .lsw-flaw { padding:10px 0; border-bottom:1px solid #22303f; font-size:14px; }
    .lsw-flaw b { color: ${ACCENT}; }
    .lsw-muted { color:#8ea0b3; font-size:13px; }
    .lsw-error { color:#ff6b6b; font-size:13px; margin:0 0 10px; display:none; }
    .lsw-powered { margin-top:16px; text-align:center; color:#8ea0b3; font-size:11px; }
  `;
  var styleEl = document.createElement("style");
  styleEl.textContent = css;
  document.head.appendChild(styleEl);

  var btn = document.createElement("button");
  btn.className = "lsw-btn";
  btn.textContent = "🔍 Free Website Audit";
  document.body.appendChild(btn);

  var overlay = document.createElement("div");
  overlay.className = "lsw-overlay";
  overlay.innerHTML = `
    <div class="lsw-modal">
      <span class="lsw-close">&times;</span>
      <h3>Free Website Audit</h3>
      <p class="lsw-muted">Paste your website — we'll show you what's costing you leads.</p>
      <input type="text" id="lsw-url" placeholder="yourwebsite.com" />
      <p class="lsw-error" id="lsw-url-error">Enter a website to scan.</p>
      <button class="lsw-submit" id="lsw-scan-btn">Scan Now</button>
      <div id="lsw-results"></div>
      ${POWERED_BY ? '<div class="lsw-powered">Powered by LeakSnap</div>' : ""}
    </div>
  `;
  document.body.appendChild(overlay);

  function open() { overlay.style.display = "flex"; }
  function close() { overlay.style.display = "none"; }
  function isEmail(v) { return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v); }
  function showError(id, msg) {
    var el = document.getElementById(id);
    if (!el) return;
    el.textContent = msg;
    el.style.display = "block";
  }
  function hideError(id) {
    var el = document.getElementById(id);
    if (el) el.style.display = "none";
  }

  btn.onclick = open;
  overlay.querySelector(".lsw-close").onclick = close;
  overlay.onclick = function (e) { if (e.target === overlay) close(); };

  overlay.querySelector("#lsw-scan-btn").onclick = async function () {
    var url = document.getElementById("lsw-url").value.trim();
    var results = document.getElementById("lsw-results");
    hideError("lsw-url-error");
    if (!url) {
      showError("lsw-url-error", "Enter a website to scan.");
      return;
    }
    results.innerHTML = '<p class="lsw-muted">Scanning...</p>';

    try {
      var res = await fetch(API_BASE + "/api/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url, agency_id: AGENCY_ID }),
      });
      var data = await res.json();
      if (res.status === 402) {
        results.innerHTML = '<p class="lsw-muted">This trial has ended. Contact us to keep it active.</p>';
        return;
      }
      if (!res.ok || data.error) {
        results.innerHTML = '<p class="lsw-muted">' + (data.error || "Could not scan that site.") + "</p>";
        return;
      }
      renderTeaser(data, url);
    } catch (e) {
      results.innerHTML = '<p class="lsw-muted">Something went wrong. Is the scan API running?</p>';
    }
  };

  function renderTeaser(data, url) {
    var results = document.getElementById("lsw-results");
    var html = `<p><b>${data.flaws_found} of 4 issues found</b> on ${data.url}</p>`;
    data.checks.forEach(function (c) {
      html += `<div class="lsw-flaw">${c.present ? "⚠️" : "✅"} <b>${c.flaw}</b><br><span class="lsw-muted">${c.detail}</span></div>`;
    });
    html += `
      <p class="lsw-muted" style="margin-top:12px;">Enter your email to unlock the full report:</p>
      <input type="text" id="lsw-name" placeholder="Name" />
      <input type="email" id="lsw-email" placeholder="Email" />
      <p class="lsw-error" id="lsw-email-error">Enter a valid email.</p>
      <button class="lsw-submit" id="lsw-unlock-btn">Unlock Full Report</button>
    `;
    results.innerHTML = html;

    document.getElementById("lsw-unlock-btn").onclick = async function () {
      var name = document.getElementById("lsw-name").value.trim();
      var email = document.getElementById("lsw-email").value.trim();
      hideError("lsw-email-error");
      if (!email || !isEmail(email)) {
        showError("lsw-email-error", "Enter a valid email to unlock the report.");
        return;
      }
      results.innerHTML = '<p class="lsw-muted">Unlocking...</p>';

      try {
        var res = await fetch(API_BASE + "/api/lead", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url: url, name: name, email: email, agency_id: AGENCY_ID }),
        });
        var unlocked = await res.json();
        if (!res.ok || unlocked.error) {
          results.innerHTML = '<p class="lsw-muted">' + (unlocked.error || "Could not unlock the report.") + "</p>";
          return;
        }
        renderFull(unlocked);
      } catch (e) {
        results.innerHTML = '<p class="lsw-muted">Something went wrong.</p>';
      }
    };
  }

  function renderFull(data) {
    var results = document.getElementById("lsw-results");
    var html = `<p><b>${data.flaws_found} of 4 issues found</b> on ${data.url}</p>`;
    data.checks.forEach(function (c) {
      html += `<div class="lsw-flaw">${c.present ? "⚠️" : "✅"} <b>${c.flaw}</b><br><span class="lsw-muted">${c.detail}</span></div>`;
    });
    html += `<p class="lsw-muted" style="margin-top:12px;">We'll be in touch about how to fix these. 🎉</p>`;
    results.innerHTML = html;
  }
})();

```

### FILE: docs/demo.html
```
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Demo Agency Site — LeakSnap Widget Preview</title>
<style>body{font-family:sans-serif;background:#0b0f14;color:#e8edf2;padding:60px;text-align:center;}</style>
</head>
<body>
  <h1>Demo Agency Website</h1>
  <p>This simulates what the widget looks like once embedded on a client's (e.g. Adexorb's) site.</p>
  <p>Click the floating button, bottom-right ↘</p>

  <!-- This is the exact snippet an agency would paste on their real site -->
  <script src="http://localhost:5001/widget/embed.js"
          data-agency-id="demo-agency"
          data-api-base="http://localhost:5001"
          data-accent="#ff5a3c"
          data-powered-by="true"></script>
</body>
</html>

```

### FILE: docs/demo-video.html
```
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>LeakSnap — Sales Demo Reel</title>
<style>
  :root { --bg:#0b0f14; --card:#121821; --accent:#ff5a3c; --text:#e8edf2; --muted:#8ea0b3; --ok:#5fd68a; }
  * { box-sizing:border-box; margin:0; padding:0; }
  html,body { width:100%; height:100%; background:var(--bg); overflow:hidden; }
  body { font-family:-apple-system,Segoe UI,Roboto,sans-serif; color:var(--text);
    display:flex; align-items:center; justify-content:center; }

  .stage { width:460px; height:640px; position:relative; }
  .scene { position:absolute; inset:0; opacity:0; pointer-events:none; transition:opacity .6s ease;
    display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; padding:24px; }
  .scene.active { opacity:1; }

  #s1 h1 { font-size:30px; line-height:1.3; margin-bottom:14px; }
  #s1 .accent { color:var(--accent); }
  #s1 p { color:var(--muted); font-size:15px; }

  #s2 .logo { font-size:46px; margin-bottom:10px; }
  #s2 h1 { font-size:32px; margin-bottom:8px; }
  #s2 p { color:var(--muted); font-size:15px; max-width:320px; }

  .phone { width:100%; background:#0f151d; border-radius:24px; padding:20px; box-shadow:0 30px 80px rgba(0,0,0,.6); text-align:left; }
  .url-bar { background:#1a222c; border-radius:8px; padding:10px 14px; font-size:13px; color:var(--muted); margin-bottom:14px;
    display:flex; align-items:center; gap:8px; }
  .dot { width:8px; height:8px; border-radius:50%; background:var(--accent); flex-shrink:0; }
  .scan-title { font-size:18px; margin-bottom:2px; }
  .sub { color:var(--muted); font-size:12.5px; margin-bottom:14px; }
  .scanline { height:3px; background:#1a222c; border-radius:2px; overflow:hidden; margin-bottom:14px; }
  .scanline-fill { height:100%; width:0%; background:linear-gradient(90deg,var(--accent),#ffb199); border-radius:2px; }
  .s3active .scanline-fill { animation: fill 3s ease-in-out forwards; }
  @keyframes fill { to { width:100%; } }
  .flaw { opacity:0; transform:translateY(8px); background:var(--card); border-radius:10px; padding:10px 12px;
    margin-bottom:8px; border:1px solid #1c2733; display:flex; gap:9px; align-items:flex-start; }
  .s3active .flaw { animation: reveal .45s ease forwards; }
  .s3active .flaw:nth-child(1) { animation-delay: .7s; }
  .s3active .flaw:nth-child(2) { animation-delay: 1.3s; }
  .s3active .flaw:nth-child(3) { animation-delay: 1.9s; }
  .s3active .flaw:nth-child(4) { animation-delay: 2.5s; }
  @keyframes reveal { to { opacity:1; transform:translateY(0); } }
  .badge { width:18px; height:18px; border-radius:50%; flex-shrink:0; display:flex; align-items:center; justify-content:center;
    font-size:11px; font-weight:700; background:#3a1414; color:#ff6b6b; }
  .flaw b { font-size:12.5px; }
  .flaw span { display:block; color:var(--muted); font-size:11px; margin-top:1px; }
  .result-bar { opacity:0; text-align:center; margin-top:4px; padding:12px; border-radius:10px;
    background:linear-gradient(145deg,#1a2129,#12181f); border:1px solid #2a3947; }
  .s3active .result-bar { animation: reveal .5s ease forwards; animation-delay: 3.1s; }
  .result-bar b { color:var(--accent); font-size:17px; }
  .loss { color:#ff6b6b; }
  .urgency { opacity:0; text-align:center; color:var(--muted); font-size:11px; margin-top:8px; }
  .s3active .urgency { animation: reveal .4s ease forwards; animation-delay: 3.7s; }

  .phone input { width:100%; padding:10px; border-radius:8px; border:1px solid #2a3947; background:#0f151d;
    color:var(--text); margin-bottom:8px; font-size:13px; }
  .typewriter { border-right:2px solid var(--accent); white-space:nowrap; overflow:hidden; width:0; }
  .s4active .typewriter { animation: type 1.6s steps(20) forwards; }
  @keyframes type { to { width: 15ch; } }
  .unlock-btn { width:100%; padding:11px; border:none; border-radius:8px; background:var(--accent); color:#fff;
    font-weight:700; font-size:13px; text-align:center; opacity:0; }
  .s4active .unlock-btn { animation: reveal .4s ease forwards; animation-delay: 2.2s; }
  .lead-note { opacity:0; text-align:center; color:var(--ok); font-size:12.5px; margin-top:10px; }
  .s4active .lead-note { animation: reveal .4s ease forwards; animation-delay: 2.9s; }

  #s5 h1 { font-size:26px; margin-bottom:10px; }
  #s5 .price { font-size:38px; font-weight:800; color:var(--accent); margin:10px 0; }
  #s5 p { color:var(--muted); font-size:14px; max-width:320px; margin-bottom:6px; }
  #s5 .cta { margin-top:16px; padding:14px 30px; background:var(--accent); color:#fff; border-radius:8px;
    font-weight:700; font-size:14px; }

  .progress { position:absolute; bottom:-28px; left:0; right:0; display:flex; gap:6px; justify-content:center; }
  .progress .seg { width:36px; height:3px; border-radius:2px; background:#1c2733; }
  .progress .seg.done { background:var(--accent); }
</style>
</head>
<body>
<div class="stage">

  <div class="scene" id="s1">
    <h1>Is your client's website <span class="accent">quietly losing them customers?</span></h1>
    <p>Most local businesses have no idea what's broken on their own site — until someone shows them.</p>
    <p style="margin-top:10px; font-size:12.5px; color:var(--accent);">71% of local business sites we've scanned have at least one critical leak.</p>
  </div>

  <div class="scene" id="s2">
    <div class="logo">🔍</div>
    <h1>LeakSnap</h1>
    <p>A free-audit widget that scans any website in seconds and turns curious visitors into warm leads — for you.</p>
  </div>

  <div class="scene" id="s3">
    <div class="phone">
      <div class="url-bar"><span class="dot"></span> scanning: roofpro-example.com</div>
      <div class="scan-title">🔍 Live Website Audit</div>
      <div class="sub">Checking tracking, mobile forms, booking, speed...</div>
      <div class="scanline"><div class="scanline-fill"></div></div>
      <div class="flaw"><div class="badge">!</div><div><b>No conversion tracking detected</b><span>Ad spend running blind — est. <b class="loss">$800-1,200/mo</b> wasted.</span></div></div>
      <div class="flaw"><div class="badge">!</div><div><b>No mobile-friendly contact form</b><span>~<b class="loss">60% of visitors</b> are on mobile and can't reach you.</span></div></div>
      <div class="flaw"><div class="badge">!</div><div><b>No booking automation</b><span>After-hours leads lost — est. <b class="loss">$1,000+/mo</b> in missed jobs.</span></div></div>
      <div class="flaw"><div class="badge">!</div><div><b>Slow page load speed</b><span>4.8s load time — <b class="loss">~7% conversion drop</b> per extra second.</span></div></div>
      <div class="result-bar"><b>4 of 4</b> leaks found — an est. <b style="color:#ff6b6b">$2,400+/mo</b> in missed revenue.</div>
      <div class="urgency">⚡ 71% of local business sites we've scanned have at least one of these</div>
    </div>
  </div>

  <div class="scene" id="s4">
    <div class="phone">
      <div class="scan-title">Unlock the full report</div>
      <div class="sub">Enter your email to see exactly how to fix these:</div>
      <div class="typewriter" style="color:var(--muted); font-size:13px; margin-bottom:10px;">owner@roofpro.com</div>
      <div class="unlock-btn">Unlock Full Report</div>
      <div class="lead-note">Lead captured — sent straight to your dashboard</div>
    </div>
  </div>

  <div class="scene" id="s5">
    <h1>One script tag.<br>Leads on autopilot.</h1>
    <p>7-day free trial for every client site you add.</p>
    <div class="price">$500-800</div>
    <p>one-time setup, plus $150/mo hosting and maintenance</p>
    <p style="color:var(--accent); font-size:12.5px; margin-top:6px;">Every day without this, your competitors' agencies are already offering it.</p>
    <div class="cta">Try it free for 7 days</div>
  </div>

  <div class="progress" id="progress"></div>
</div>

<script>
  var scenes = ["s1","s2","s3","s4","s5"];
  var durations = [3600, 3000, 4700, 3600, 4300];
  var idx = 0;

  var progressEl = document.getElementById("progress");
  scenes.forEach(function(){ var d = document.createElement("div"); d.className="seg"; progressEl.appendChild(d); });
  var segs = progressEl.querySelectorAll(".seg");

  function show(i) {
    scenes.forEach(function(id, n){
      var el = document.getElementById(id);
      el.classList.toggle("active", n === i);
      if (id === "s3") el.classList.toggle("s3active", n === i);
      if (id === "s4") el.classList.toggle("s4active", n === i);
    });
    segs.forEach(function(seg, n){ seg.classList.toggle("done", n <= i); });
  }

  function next() {
    show(idx);
    setTimeout(function(){
      idx = (idx + 1) % scenes.length;
      next();
    }, durations[idx]);
  }
  next();
</script>
</body>
</html>

```

### FILE: docs/standalone-static/index.html
```
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SiteLeakCheck — Find Your Website's Revenue Leaks</title>
<style>
  :root { --bg:#0b0f14; --card:#121821; --accent:#ff5a3c; --text:#e8edf2; --muted:#8ea0b3; }
  * { box-sizing: border-box; }
  body { margin:0; font-family: -apple-system, Segoe UI, Roboto, sans-serif; background:var(--bg); color:var(--text); }
  .wrap { max-width: 640px; margin: 0 auto; padding: 48px 20px 80px; }
  h1 { font-size: 28px; margin-bottom: 8px; }
  p.sub { color: var(--muted); margin-top: 0; }
  .scan-box { display:flex; gap:8px; margin-top: 24px; }
  input[type=text] { flex:1; padding: 14px 16px; border-radius: 8px; border: 1px solid #22303f; background:#0f151d; color:var(--text); font-size:15px; }
  button { padding: 14px 22px; border-radius: 8px; border:none; background: var(--accent); color:white; font-weight:600; cursor:pointer; font-size:15px; }
  button:disabled { opacity:0.5; cursor:default; }
  .card { background: var(--card); border-radius: 12px; padding: 20px; margin-top: 16px; border:1px solid #1c2733; }
  .flaw { display:flex; align-items:flex-start; gap:10px; padding:12px 0; border-bottom:1px solid #1c2733; }
  .flaw:last-child { border-bottom:none; }
  .badge { flex-shrink:0; width:22px; height:22px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:13px; font-weight:700; }
  .badge.bad { background:#3a1414; color:#ff6b6b; }
  .badge.ok { background:#123a1e; color:#5fd68a; }
  .locked { filter: blur(5px); user-select:none; pointer-events:none; }
  .paywall { text-align:center; margin-top: 18px; padding: 22px; border-radius: 12px; background: linear-gradient(145deg,#1a2129,#12181f); border:1px solid #2a3947; }
  .paywall h3 { margin-top:0; }
  .price { font-size: 32px; font-weight:800; color: var(--accent); }
  .cta { display:inline-block; margin-top:14px; padding:14px 28px; background:var(--accent); color:white; border-radius:8px; font-weight:700; text-decoration:none; }
  .loading { color: var(--muted); margin-top: 20px; }
  .error { color:#ff6b6b; margin-top:16px; }
</style>
</head>
<body>
<div class="wrap">
  <h1>🔍 SiteLeakCheck</h1>
  <p class="sub">Paste any business website below. We'll instantly find the revenue leaks costing them customers — tracking gaps, broken mobile forms, missing booking systems, and slow load speed.</p>

  <div class="scan-box">
    <input type="text" id="urlInput" placeholder="e.g. yourbusiness.com" />
    <button id="scanBtn" onclick="runScan()">Scan Now</button>
  </div>

  <div id="results"></div>
</div>

<script>
async function runScan() {
  const url = document.getElementById('urlInput').value.trim();
  const btn = document.getElementById('scanBtn');
  const results = document.getElementById('results');
  if (!url) return;

  btn.disabled = true;
  btn.textContent = "Scanning...";
  results.innerHTML = '<p class="loading">Analyzing site — checking tracking, forms, booking, speed...</p>';

  try {
    const res = await fetch('/api/scan', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({url})
    });
    const data = await res.json();
    btn.disabled = false;
    btn.textContent = "Scan Now";

    if (data.error) {
      results.innerHTML = `<p class="error">Couldn't reach that site: ${data.error}</p>`;
      return;
    }

    renderResults(data);
  } catch (e) {
    btn.disabled = false;
    btn.textContent = "Scan Now";
    results.innerHTML = `<p class="error">Something went wrong. Try again.</p>`;
  }
}

function renderResults(data) {
  const results = document.getElementById('results');
  const flawed = data.checks.filter(c => c.present);
  const clean = data.checks.filter(c => !c.present);

  let html = `<div class="card"><strong>${data.url}</strong> — ${data.flaws_found} of 4 checks flagged an issue.</div>`;

  // Show first flaw free, rest locked behind paywall
  data.checks.forEach((c, i) => {
    const isFree = i === 0;
    const badgeClass = c.present ? 'bad' : 'ok';
    const badgeChar = c.present ? '!' : '✓';
    const lockedClass = isFree ? '' : 'locked';
    html += `<div class="card ${lockedClass}">
      <div class="flaw">
        <div class="badge ${badgeClass}">${badgeChar}</div>
        <div><strong>${c.flaw}</strong><br><span style="color:#8ea0b3;font-size:14px;">${isFree ? c.detail : 'Full detail unlocks in the paid report...'}</span></div>
      </div>
    </div>`;
  });

  html += `<div class="paywall">
    <h3>Unlock the Full Revenue Leak Report</h3>
    <div class="price">$99</div>
    <p style="color:#8ea0b3;">Full flaw breakdown + fix priority + downloadable PDF you can act on today.</p>
    <a class="cta" href="#" onclick="alert('Wire your Stripe/PayPal payment link here.'); return false;">Get Full Report — $99</a>
  </div>`;

  results.innerHTML = html;
}
</script>
</body>
</html>

```

## What to do with this prompt
Treat all of the above as ground truth. Do not rebuild the scanner, widget, or paywall from zero - the working
code is inlined above; recreate these exact files if you need to reconstruct the repo, then extend them. If
asked to continue development, work through "Known gaps" in the order listed.

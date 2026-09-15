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
    conn.commit()
    conn.close()


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
    if not url:
        return jsonify({"error": "Missing url"}), 400

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

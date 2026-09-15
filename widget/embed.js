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
        body: JSON.stringify({ url: url }),
      });
      var data = await res.json();
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

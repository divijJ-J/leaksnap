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

import json
import socket
import requests
from datetime import date, datetime
from urllib.parse import urlparse

DATA_FILE = "data.json"
TIMEOUT = 15
TODAY = date.today().isoformat()
FAIL_THRESHOLD = 3  # 連續幾天 HTTP + DNS 都失敗才標死

# App Store / Google Play 回應中，下架的特徵
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def check_web(url: str) -> bool:
    """Check if a website/API is reachable (2xx or 3xx)."""
    try:
        r = requests.head(url, timeout=TIMEOUT, headers=HEADERS, allow_redirects=True)
        return r.status_code < 400
    except Exception:
        return False


def check_app(url: str) -> bool:
    """
    Check if an app store listing is still live.
    A 404 status code means the app has been removed.
    """
    if not url:
        return True  # no checkUrl, skip
    try:
        r = requests.get(url, timeout=TIMEOUT, headers=HEADERS, allow_redirects=True)
        return r.status_code < 400
    except Exception:
        return False


def dns_alive(url: str) -> bool:
    """Check if the domain still resolves via DNS."""
    try:
        host = urlparse(url).hostname
        if not host:
            return False
        socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        return True
    except (socket.gaierror, Exception):
        return False


def main():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        projects = json.load(f)

    changed = False

    for p in projects:
        proj_type = p.get("type", "").upper()
        is_dead = bool(p.get("deadDate"))

        if proj_type in ("LINE BOT",):
            # LINE BOT hard to auto-check, skip
            continue

        if proj_type == "APP":
            check_url = p.get("checkUrl") or p.get("url", "")
            alive = check_app(check_url)
        else:
            check_url = p.get("checkUrl") or p.get("url", "")
            alive = check_web(check_url)

        if not alive:
            # Double check: retry once to avoid false positives
            import time
            time.sleep(5)
            if proj_type == "APP":
                alive = check_app(check_url)
            else:
                # Fallback to GET if HEAD failed (some servers don't support HEAD)
                try:
                    r = requests.get(check_url, timeout=TIMEOUT, headers=HEADERS, allow_redirects=True)
                    alive = r.status_code < 400
                except Exception:
                    alive = False

        # Last resort: if HTTP fails, check DNS
        # (Cloudflare/bot protection may block HTTP but domain is still alive)
        if not alive and dns_alive(check_url):
            print(f"🛡️  {p['name']} - HTTP failed but DNS alive, treating as alive ({check_url})")
            alive = True

        if not alive and not is_dead:
            fail_count = p.get("failCount", 0) + 1
            p["failCount"] = fail_count
            if fail_count >= FAIL_THRESHOLD:
                p["deadDate"] = TODAY
                p["failCount"] = 0
                print(f"💀 {p['name']} - marked dead after {FAIL_THRESHOLD} consecutive failures ({check_url})")
            else:
                print(f"⚠️  {p['name']} - fail {fail_count}/{FAIL_THRESHOLD} ({check_url})")
            changed = True
        elif alive and is_dead:
            print(f"🔮 {p['name']} - 復活了！清除 deadDate")
            p["deadDate"] = ""
            p["failCount"] = 0
            changed = True
        elif alive:
            if p.get("failCount", 0) > 0:
                p["failCount"] = 0
                changed = True
            print(f"✅ {p['name']} - alive")
        else:
            print(f"⚰️  {p['name']} - still dead")

    if changed:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(projects, f, ensure_ascii=False, indent=2)
        print(f"\n📝 data.json updated on {TODAY}")
    else:
        print("\n🎉 All projects alive!")


if __name__ == "__main__":
    main()

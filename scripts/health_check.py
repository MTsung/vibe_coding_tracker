import json
import requests
from datetime import date, datetime

DATA_FILE = "data.json"
TIMEOUT = 15
TODAY = date.today().isoformat()

# App Store / Google Play 回應中，下架的特徵
APP_STORE_GONE_HINTS = [
    "not available", "isn\u2019t available", "not found",
    "we can\u2019t find", "404", "no longer available"
]

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
        r = requests.get(url, timeout=TIMEOUT, headers=HEADERS, allow_redirects=True)
        return r.status_code < 400
    except Exception:
        return False


def check_app(url: str) -> bool:
    """
    Check if an app store listing is still live.
    Fetches the store page and looks for removal indicators.
    """
    if not url:
        return True  # no checkUrl, skip
    try:
        r = requests.get(url, timeout=TIMEOUT, headers=HEADERS, allow_redirects=True)
        if r.status_code >= 400:
            return False
        body = r.text.lower()
        return not any(hint in body for hint in APP_STORE_GONE_HINTS)
    except Exception:
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
                alive = check_web(check_url)

        if not alive and not is_dead:
            p["deadDate"] = TODAY
            print(f"💀 {p['name']} - marked dead ({check_url})")
            changed = True
        elif alive and is_dead:
            print(f"🔮 {p['name']} - 復活了！清除 deadDate")
            p["deadDate"] = ""
            changed = True
        elif alive:
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

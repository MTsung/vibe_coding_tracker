import json
import socket
import time
import requests
from datetime import date, datetime
from urllib.parse import urlparse

DATA_FILE = "data.json"
TIMEOUT = 15
TODAY = date.today().isoformat()
FAIL_THRESHOLD = 3  # 連續幾天檢查失敗才標死（可吸收暫時性的 5xx / 部署中斷）

# 這些狀態碼代表伺服器還活著，只是拒絕機器人：Cloudflare 挑戰頁（403）、
# 驗證牆（401）、限流（429）。站台本身仍在運作，不該判死。
# 其餘 >= 400 一律判死，包含 404/410（部署已移除）與 503
# （如 Render 的 x-render-routing: suspend-by-user，服務被擁有者停用）。
BOT_PROTECTION_STATUS = {401, 403, 429}

# App Store / Google Play 回應中，下架的特徵
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def probe(url: str, method: str = "head"):
    """
    Probe a URL.

    Returns (alive, status):
      alive  - 伺服器回應了 2xx / 3xx
      status - HTTP 狀態碼；None 代表連線層就失敗（DNS 掛掉、拒絕連線、
               TLS 失敗、逾時），也就是服務真的不在了

    保留狀態碼是為了區分「被擋 bot」和「真的沒了」：403 是 Cloudflare
    挑戰頁，404 是部署已移除，兩者不能一視同仁。
    """
    if not url:
        return True, None  # no checkUrl, skip
    try:
        fn = requests.head if method == "head" else requests.get
        r = fn(url, timeout=TIMEOUT, headers=HEADERS, allow_redirects=True)
        return r.status_code < 400, r.status_code
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        return False, None
    except Exception:
        # 其他協定層問題（重導向過多等）：拿不到可信的狀態碼
        return False, None


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

        check_url = p.get("checkUrl") or p.get("url", "")
        alive, status = probe(check_url, "get" if proj_type == "APP" else "head")

        if not alive:
            # Double check: retry once with GET to avoid false positives
            # (some servers don't support HEAD)
            time.sleep(5)
            alive, status = probe(check_url, "get")

        parsed_url = urlparse(check_url)
        is_app_store = parsed_url.hostname in ("apps.apple.com", "play.google.com")

        # 伺服器活著但擋機器人：視為存活。
        # app store 例外，那邊的錯誤狀態就是真的下架了。
        if not alive and status in BOT_PROTECTION_STATUS and not is_app_store:
            print(f"\U0001F6E1\uFE0F  {p['name']} - HTTP {status}, likely bot protection, treating as alive ({check_url})")
            alive = True

        # 判死前先記下死法，方便日後回查
        if not alive:
            if status is None:
                reason = ("domain still resolves but nothing is listening"
                          if dns_alive(check_url) else "domain no longer resolves")
            else:
                reason = f"HTTP {status}"
            print(f"\U0001F50D {p['name']} - {reason} ({check_url})")

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

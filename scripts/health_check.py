import json
import socket
import time
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


def probe(url: str, method: str = "head") -> tuple[bool, bool]:
    """
    Probe a URL and report both liveness and reachability.

    Returns (alive, reachable):
      alive     - 伺服器回應了 2xx / 3xx
      reachable - 伺服器有回應（TCP + TLS + HTTP 都通，狀態碼不論）

    區分這兩者很重要：reachable=False 代表連線層就失敗（DNS 掛掉、
    connection refused、timeout），也就是服務真的不在了；
    reachable=True 但 alive=False 則可能只是被 bot 保護擋下（403/503）。
    """
    if not url:
        return True, True  # no checkUrl, skip
    try:
        fn = requests.head if method == "head" else requests.get
        r = fn(url, timeout=TIMEOUT, headers=HEADERS, allow_redirects=True)
        return r.status_code < 400, True
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        # 連不上：DNS 失敗、拒絕連線、TLS 失敗、逾時
        return False, False
    except Exception:
        # 其他協定層問題（重導向過多等）：伺服器有回應，只是這次拿不到結果
        return False, True


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
        alive, reachable = probe(check_url, "get" if proj_type == "APP" else "head")

        if not alive:
            # Double check: retry once with GET to avoid false positives
            # (some servers don't support HEAD)
            time.sleep(5)
            alive, reachable = probe(check_url, "get")

        parsed_url = urlparse(check_url)
        is_app_store = parsed_url.hostname in ("apps.apple.com", "play.google.com")

        # 伺服器有回應但狀態碼是錯誤：常見於 Cloudflare / WAF 擋 bot（403、429、503），
        # 這種情況視為還活著。但 app store 的錯誤狀態就是真的下架了。
        if not alive and reachable and not is_app_store:
            print(f"🛡️  {p['name']} - server responded with an error status, likely bot protection, treating as alive ({check_url})")
            alive = True

        # 連線層就失敗：服務真的不在了。DNS 只用來說明是哪一種死法。
        if not alive and not reachable and dns_alive(check_url):
            print(f"� {p['name']} - domain still resolves but nothing is listening ({check_url})")

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

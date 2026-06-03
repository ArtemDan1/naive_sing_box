from urllib.parse import quote


def is_browser(ua: str) -> bool:
    return "mozilla" in ua.lower()


def detect_platform(ua: str) -> str:
    u = ua.lower()
    if "android" in u or "iphone" in u or "ipad" in u or "ios" in u:
        return "mobile"
    return "desktop"


def build_deeplinks(sub_url: str) -> dict[str, str]:
    enc = quote(sub_url, safe="")
    return {
        "singbox": f"sing-box://import-remote-profile?url={enc}",
        "hiddify": f"hiddify://import/{enc}",
        "karing": f"karing://install-config?url={enc}",
        "copy": sub_url,
    }

import json
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


_ASSET_JS = "/admin/assets/sub.js"
_ASSET_CSS = "/admin/assets/sub.css"


def render_sub_page(label: str, sub_url: str, platform: str) -> str:
    payload = {
        "label": label,
        "sub_url": sub_url,
        "platform": platform,
        "deeplinks": build_deeplinks(sub_url),
    }
    # json.dumps escapes quotes; additionally neutralize "</" so a label can
    # never break out of the inline <script> element.
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Подписка</title>
<link rel="stylesheet" href="{_ASSET_CSS}">
<script>window.__SUB__ = {data};</script>
</head>
<body>
<div id="sub"></div>
<script type="module" src="{_ASSET_JS}"></script>
</body>
</html>"""


def render_sub_404() -> str:
    return """<!doctype html>
<html lang="ru">
<head><meta charset="utf-8"><title>Не найдено</title>
<link rel="stylesheet" href="/admin/assets/sub.css"></head>
<body style="font-family:system-ui;padding:3rem;text-align:center">
<h1>Подписка не найдена</h1>
<p>Ссылка недействительна или подписка отключена.</p>
</body>
</html>"""

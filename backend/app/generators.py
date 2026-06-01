import json


def singbox_config(users: list[dict]) -> str:
    # The naive inbound requires at least one user; sing-box refuses to start
    # with an empty users list ("missing users"). When there are no enabled
    # clients we omit the inbound entirely so the process still starts cleanly.
    inbounds = []
    if users:
        inbounds.append({
            "type": "naive",
            "tag": "naive-in",
            "listen": "0.0.0.0",
            "listen_port": 1080,
            "network": "tcp",
            "users": users,
        })
    cfg = {
        "log": {"level": "warn"},
        "inbounds": inbounds,
        "outbounds": [{"type": "direct"}],
    }
    return json.dumps(cfg, indent=2)


def caddyfile(domain: str) -> str:
    return f"""{domain} {{
\t@naive method CONNECT
\thandle @naive {{
\t\treverse_proxy h2c://singbox:1080 {{
\t\t\theader_up Proxy-Authorization {{header.Proxy-Authorization}}
\t\t}}
\t}}
\thandle /api/* {{
\t\treverse_proxy fastapi:8000
\t}}
\thandle /sub/* {{
\t\treverse_proxy fastapi:8000
\t}}
\thandle_path /admin/* {{
\t\treverse_proxy frontend:80
\t}}
\thandle {{
\t\troot * /srv/fallback
\t\tfile_server
\t}}
}}
"""


def subscription(domain: str, username: str, password: str) -> str:
    cfg = {
        "outbounds": [{
            "type": "naive",
            "tag": "proxy",
            "server": domain,
            "server_port": 443,
            "username": username,
            "password": password,
            "tls": {"enabled": True, "server_name": domain},
        }]
    }
    return json.dumps(cfg, indent=2)

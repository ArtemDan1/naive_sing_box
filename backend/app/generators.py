import json


def singbox_config(users: list[dict]) -> str:
    cfg = {
        "log": {"level": "warn"},
        "inbounds": [{
            "type": "naive",
            "tag": "naive-in",
            "listen": "0.0.0.0",
            "listen_port": 1080,
            "network": "tcp",
            "users": users,
        }],
        "outbounds": [{"type": "direct"}],
    }
    return json.dumps(cfg, indent=2)


def caddyfile(domain: str) -> str:
    return f"""{domain} {{
\t@naive method CONNECT
\thandle @naive {{
\t\treverse_proxy h2c://singbox:1080
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

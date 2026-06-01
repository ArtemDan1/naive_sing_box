import json


def caddyfile(domain: str, users: list[dict]) -> str:
    """Caddyfile for a NaiveProxy server based on caddy-forwardproxy.

    Caddy itself is the naive endpoint: forward_proxy handles authenticated
    CONNECT (proxy) traffic, while non-proxy requests fall through to the
    reverse_proxy routes (/api, /sub, /admin) and finally the masking site.
    """
    auth_lines = "".join(
        f"\n\t\t\tbasic_auth {u['username']} {u['password']}" for u in users
    )
    return f"""{{
\tservers {{
\t\tprotocols h1 h2
\t}}
}}

{domain} {{
\troute {{
\t\tforward_proxy {{{auth_lines}
\t\t\thide_ip
\t\t\thide_via
\t\t}}
\t\thandle /api/* {{
\t\t\treverse_proxy fastapi:8000
\t\t}}
\t\thandle /sub/* {{
\t\t\treverse_proxy fastapi:8000
\t\t}}
\t\thandle_path /admin/* {{
\t\t\treverse_proxy frontend:80
\t\t}}
\t\thandle {{
\t\t\troot * /srv/fallback
\t\t\tfile_server
\t\t}}
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

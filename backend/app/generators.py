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
    # Caddy's forward_proxy requires authentication when probe_resistance is on,
    # so the proxy block is only emitted when there is at least one user.
    # Without users the site still serves the panel and masking fallback.
    forward_proxy_block = (
        f"""\t\tforward_proxy {{{auth_lines}
\t\t\thide_ip
\t\t\thide_via
\t\t\tprobe_resistance
\t\t}}
"""
        if users
        else ""
    )
    return f"""{{
\tdebug
\tservers {{
\t\tprotocols h1 h2
\t}}
}}

{domain} {{
\troute {{
{forward_proxy_block}\t\thandle /api/* {{
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


def subscription(domain: str, username: str, password: str, name: str = "") -> str:
    """Full sing-box client profile (log + mixed inbound + naive outbound + route).

    `name` is intentionally not embedded in the profile body — it is only used
    for the subscription response headers (profile title / filename).
    """
    cfg = {
        "log": {"level": "info"},
        "inbounds": [{
            "type": "mixed",
            "tag": "mixed-in",
            "listen": "127.0.0.1",
            "listen_port": 2082,
        }],
        "outbounds": [{
            "type": "naive",
            "tag": "proxy",
            "server": domain,
            "server_port": 443,
            "username": username,
            "password": password,
            "tls": {"enabled": True, "server_name": domain},
        }],
        "route": {"final": "proxy"},
    }
    return json.dumps(cfg, indent=2)

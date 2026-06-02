import json
from urllib.parse import quote


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

:443, {domain} {{
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


def _naive_outbound(domain: str, username: str, password: str) -> dict:
    return {
        "type": "naive",
        "tag": "proxy",
        "server": domain,
        "server_port": 443,
        "username": username,
        "password": password,
        "tls": {"enabled": True, "server_name": domain},
    }


def subscription(domain: str, username: str, password: str, compact: bool = False) -> str:
    """Full standalone sing-box profile (log + mixed inbound + naive outbound +
    route). For "bare" clients (sing-box CLI/app, Karing) that run the config
    verbatim and need an inbound to listen on.

    `compact=True` emits single-line JSON (used for Happ's custom-tunnel-config
    directive, which must occupy one line)."""
    cfg = {
        "log": {"level": "info"},
        "inbounds": [{
            "type": "mixed",
            "tag": "mixed-in",
            "listen": "127.0.0.1",
            "listen_port": 2082,
        }],
        "outbounds": [_naive_outbound(domain, username, password)],
        "route": {"final": "proxy"},
    }
    if compact:
        return json.dumps(cfg, separators=(",", ":"))
    return json.dumps(cfg, indent=2)


def happ_custom_tunnel(domain: str, username: str, password: str, name: str) -> str:
    """Subscription body for Happ Desktop: the `#custom-tunnel-config` directive
    (full sing-box profile, one line) followed by a placeholder share-link.

    Happ defaults to the Xray core and needs at least one ordinary share-link to
    create a profile entry; the directive then makes it use the sing-box core for
    the actual tunnel. The trojan:// link is a non-functional placeholder."""
    profile = subscription(domain, username, password, compact=True)
    label = quote(name) if name else "proxy"
    placeholder = (
        f"trojan://{quote(password)}@{domain}:443"
        f"?security=tls&sni={domain}&type=tcp#{label}"
    )
    return f"#custom-tunnel-config: {profile}\n{placeholder}"


def subscription_outbounds(domain: str, username: str, password: str) -> str:
    """Outbounds-only fragment for "managed" clients (Hiddify, Happ) that inject
    their own tun inbound + route/dns. An embedded inbound bound to a specific
    IP breaks them (Happ: "Listen on specific ip"; Hiddify: route conflict)."""
    return json.dumps({"outbounds": [_naive_outbound(domain, username, password)]}, indent=2)

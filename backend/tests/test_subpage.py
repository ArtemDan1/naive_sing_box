from app.subpage import is_browser, detect_platform, build_deeplinks


def test_is_browser_true_for_mozilla():
    assert is_browser("Mozilla/5.0 (Macintosh) Safari/605") is True


def test_is_browser_false_for_clients():
    assert is_browser("sing-box/1.8.0") is False
    assert is_browser("HiddifyNext/2.0.0") is False
    assert is_browser("") is False


def test_detect_platform():
    assert detect_platform("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)") == "mobile"
    assert detect_platform("Mozilla/5.0 (Linux; Android 14)") == "mobile"
    assert detect_platform("Mozilla/5.0 (Macintosh; Intel Mac OS X)") == "desktop"
    assert detect_platform("Mozilla/5.0 (Windows NT 10.0; Win64)") == "desktop"


def test_build_deeplinks_encodes_url():
    sub = "https://vpn.example.com/sub/abc"
    dl = build_deeplinks(sub)
    assert dl["singbox"] == (
        "sing-box://import-remote-profile?url="
        "https%3A%2F%2Fvpn.example.com%2Fsub%2Fabc"
    )
    assert dl["karing"] == (
        "karing://install-config?url="
        "https%3A%2F%2Fvpn.example.com%2Fsub%2Fabc"
    )
    assert dl["hiddify"] == (
        "hiddify://import/https%3A%2F%2Fvpn.example.com%2Fsub%2Fabc"
    )
    assert dl["copy"] == sub


def test_render_sub_page_contains_context_and_assets():
    from app.subpage import render_sub_page
    html = render_sub_page(
        label="My Phone",
        sub_url="https://vpn.example.com/sub/abc",
        platform="desktop",
    )
    assert "<!doctype html>" in html.lower()
    assert '/admin/assets/sub.js' in html
    assert '/admin/assets/sub.css' in html
    assert 'window.__SUB__' in html
    assert "My Phone" in html
    assert "https://vpn.example.com/sub/abc" in html
    assert '"platform": "desktop"' in html
    assert '"karing"' in html


def test_render_sub_page_escapes_label_for_script():
    from app.subpage import render_sub_page
    html = render_sub_page(
        label="</script><b>x", sub_url="https://h/sub/a", platform="mobile"
    )
    assert "</script><b>x" not in html


def test_render_sub_404_is_html():
    from app.subpage import render_sub_404
    html = render_sub_404()
    assert "<!doctype html>" in html.lower()
    assert "не найдена" in html.lower()

from app.security import hash_password, verify_password, create_token, decode_token


def test_password_roundtrip():
    h = hash_password("secret")
    assert h != "secret"
    assert verify_password("secret", h)
    assert not verify_password("wrong", h)


def test_jwt_roundtrip():
    token = create_token("admin")
    assert decode_token(token) == "admin"


def test_decode_invalid_returns_none():
    assert decode_token("garbage") is None

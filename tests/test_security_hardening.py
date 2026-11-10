def _sec():
    from superviseme.utils import security
    return security


def _bad_login(client, email, n):
    for _ in range(n):
        client.post("/login", data={"email": email, "password": "wrong"}, follow_redirects=True)


def test_login_is_throttled_after_repeated_failures(client, student_user):
    _bad_login(client, student_user.email, 5)
    # even the correct password is refused while locked out
    resp = client.post("/login", data={"email": student_user.email, "password": "password"},
                       follow_redirects=True)
    assert b"Too many failed attempts" in resp.data
    assert client.get("/student/dashboard").status_code in (301, 302, 401)


def test_successful_login_resets_counter(client, student_user):
    _bad_login(client, student_user.email, 3)
    client.post("/login", data={"email": student_user.email, "password": "password"})
    client.get("/logout")
    _bad_login(client, student_user.email, 3)
    with client.application.app_context():
        assert _sec().throttle_status(student_user.email, "127.0.0.1") == 0


def test_throttle_does_not_leak_between_accounts(client, student_user, supervisor_user):
    _bad_login(client, student_user.email, 5)
    resp = client.post("/login", data={"email": supervisor_user.email, "password": "password"},
                       follow_redirects=True)
    assert b"Too many failed attempts" not in resp.data


def test_password_policy():
    assert _sec().validate_password("short1") is not None
    assert _sec().validate_password("onlyletters") is not None
    assert _sec().validate_password("12345678") is not None
    assert _sec().validate_password("goodpass123") is None


def test_admin_create_user_rejects_weak_password(client, admin_user, app):
    from tests.test_ui_pages import login
    from superviseme.models import User_mgmt
    login(client, admin_user)
    client.post("/admin/create_user", data={
        "email": "weak@example.org", "username": "weak", "name": "W", "surname": "K",
        "password": "abc", "password2": "abc", "role": "student"}, headers={"Referer": "/admin/users"})
    with app.app_context():
        assert User_mgmt.query.filter_by(email="weak@example.org").first() is None


def test_security_headers_and_cookie_flags(client, app):
    resp = client.get("/login")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert "Referrer-Policy" in resp.headers
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["REMEMBER_COOKIE_HTTPONLY"] is True


def test_api_post_requires_same_origin_xhr(client, student_user):
    from tests.test_ui_pages import login
    login(client, student_user)
    bare = client.post("/api/v1/notifications/read-all")
    assert bare.status_code == 403
    cross = client.post("/api/v1/notifications/read-all",
                        headers={"X-Requested-With": "XMLHttpRequest", "Origin": "http://evil.example"})
    assert cross.status_code == 403
    ok = client.post("/api/v1/notifications/read-all",
                     headers={"X-Requested-With": "XMLHttpRequest", "Origin": "http://localhost"})
    assert ok.status_code == 200
    assert client.get("/api/v1/users/me").status_code == 200


def test_csp_header_modes(app):
    c = app.test_client()
    csp = c.get("/login").headers.get("Content-Security-Policy")
    assert csp and "default-src 'self'" in csp and "object-src 'none'" in csp
    assert "frame-ancestors 'self'" in csp
    app.config["CSP_MODE"] = "report-only"
    h = app.test_client().get("/login").headers
    assert "Content-Security-Policy" not in h and "Content-Security-Policy-Report-Only" in h
    app.config["CSP_MODE"] = "off"
    h = app.test_client().get("/login").headers
    assert "Content-Security-Policy" not in h and "Content-Security-Policy-Report-Only" not in h
    app.config.update(CSP_MODE="enforce", CSP_EXTRA_SOURCES="https://cdn.example", CSP_REPORT_URI="/csp")
    csp = app.test_client().get("/login").headers["Content-Security-Policy"]
    assert "https://cdn.example" in csp and "report-uri /csp" in csp

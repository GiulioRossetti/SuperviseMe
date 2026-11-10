from tests.test_ui_pages import login, _assign, _thesis


def test_admin_users_and_theses_pages(client, admin_user, supervisor_user, student_user):
    _assign(student_user, supervisor_user)
    login(client, admin_user)
    r = client.get("/admin/users")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "usGrid" in html and supervisor_user.email in html and "createUserModal" in html
    r = client.get("/admin/theses")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "thSection" in html and "createThesisModal" in html


def test_admin_dashboard_workload_is_accordion(client, admin_user, supervisor_user, student_user):
    _assign(student_user, supervisor_user)
    login(client, admin_user)
    html = client.get("/admin/dashboard").get_data(as_text=True)
    assert 'id="wlGrid"' in html and "wl-head" in html and "wl-detail" in html


def test_admin_can_disable_user_via_json(client, admin_user, student_user, app):
    login(client, admin_user)
    r = client.post("/admin/users_data", json={"id": student_user.id, "is_enabled": False})
    assert r.status_code == 200
    from superviseme.models import User_mgmt
    with app.app_context():
        assert User_mgmt.query.get(student_user.id).is_enabled is False


def test_admin_detail_pages(client, admin_user, supervisor_user, student_user, app):
    _assign(student_user, supervisor_user)
    from superviseme.models import Thesis
    with app.app_context():
        tid = Thesis.query.first().id
    login(client, admin_user)
    r = client.get("/admin/thesis/%d" % tid)
    html = r.get_data(as_text=True)
    assert r.status_code == 200 and "login.html" not in html and "Expressions of Interest" in html
    r = client.get("/admin/user/%d" % student_user.id)
    assert r.status_code == 200 and "login.html" not in r.get_data(as_text=True)
    r = client.post("/admin/archive_thesis", data={"thesis_id": tid, "action": "archive", "next": "list"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/admin/theses")

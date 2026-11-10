from tests.test_ui_pages import login, _assign, _thesis


def test_admin_users_and_theses_pages(client, admin_user, supervisor_user, student_user):
    _assign(student_user, supervisor_user)
    login(client, admin_user)
    r = client.get("/admin/users")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "usSource" in html and supervisor_user.email in html and "createUserModal" in html
    r = client.get("/admin/theses")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "thSection" in html and "createThesisModal" in html


def test_admin_dashboard_workload_is_accordion(client, admin_user, supervisor_user, student_user):
    _assign(student_user, supervisor_user)
    login(client, admin_user)
    html = client.get("/admin/dashboard").get_data(as_text=True)
    assert 'id="wlSource"' in html and "wl-head" in html and "wl-detail" in html and "sm-carousel.js" in html


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
    for pane in ("tabOverview", "tabProgress", "tabActivity", "tabPeople", "tabAdmin"):
        assert 'id="%s"' % pane in html
    # every pane holds its own content
    assert html.index('id="tabProgress"') < html.index('id="milestones"') < html.index('id="tabActivity"')
    assert html.index('id="tabPeople"') < html.index('id="team"') < html.index('id="tabAdmin"')
    r = client.get("/admin/user/%d" % student_user.id)
    assert r.status_code == 200 and "login.html" not in r.get_data(as_text=True)
    r = client.post("/admin/archive_thesis", data={"thesis_id": tid, "action": "archive", "next": "list"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/admin/theses")


def test_admin_user_detail_roles(client, admin_user, supervisor_user, student_user, researcher_user):
    _assign(student_user, supervisor_user)
    login(client, admin_user)
    for u in (student_user, supervisor_user, researcher_user, admin_user):
        r = client.get("/admin/user/%d" % u.id)
        html = r.get_data(as_text=True)
        assert r.status_code == 200 and "sp-banner" in html and u.email in html
    sup = client.get("/admin/user/%d" % supervisor_user.id).get_data(as_text=True)
    assert "Supervised Theses" in sup


def test_users_board_offers_supervisor_toggle_for_researchers(client, admin_user, researcher_user, app):
    from superviseme.models import Supervisor_Role
    login(client, admin_user)
    page = client.get("/admin/users").get_data(as_text=True)
    assert "Grant supervisor privileges" in page or "Concedi privilegi" in page
    client.post("/admin/grant_supervisor_role", data={"researcher_id": researcher_user.id},
                headers={"Referer": "/admin/users"})
    with app.app_context():
        assert Supervisor_Role.query.filter_by(researcher_id=researcher_user.id, active=True).count() == 1
    page = client.get("/admin/users").get_data(as_text=True)
    assert "Revoke supervisor privileges" in page or "Revoca privilegi" in page

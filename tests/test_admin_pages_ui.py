from tests.test_ui_pages import login, _assign, _thesis


def test_admin_users_and_theses_pages(client, admin_user, supervisor_user, student_user):
    _assign(student_user, supervisor_user)
    login(client, admin_user)
    r = client.get("/admin/users")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "usSection" in html and "createUserModal" in html and "admin/users/cards" in html
    assert supervisor_user.email in client.get("/admin/users/cards").get_json()["html"]
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
    page = client.get("/admin/users/cards").get_json()["html"]
    assert "Grant supervisor privileges" in page or "Concedi privilegi" in page
    client.post("/admin/grant_supervisor_role", data={"researcher_id": researcher_user.id},
                headers={"Referer": "/admin/users"})
    with app.app_context():
        assert Supervisor_Role.query.filter_by(researcher_id=researcher_user.id, active=True).count() == 1
    page = client.get("/admin/users/cards").get_json()["html"]
    assert "Revoke supervisor privileges" in page or "Revoca privilegi" in page


def test_users_cards_endpoint_paginates_and_filters_server_side(client, admin_user, supervisor_user, student_user):
    login(client, admin_user)
    d = client.get("/admin/users/cards?per=2&page=1").get_json()
    assert d["total"] == 3 and d["pages"] == 2 and d["html"].count("us-item") == 2
    d2 = client.get("/admin/users/cards?per=2&page=2").get_json()
    assert d2["html"].count("us-item") == 1
    assert client.get("/admin/users/cards?role=student").get_json()["total"] == 1
    assert client.get("/admin/users/cards?q=zzzz-none").get_json()["total"] == 0
    assert client.get("/admin/users/cards?q=%25").get_json()["total"] == 0  # LIKE wildcard is escaped
    assert client.get("/admin/users/cards?status=0").get_json()["total"] == 0
    # page out of range is clamped
    assert client.get("/admin/users/cards?per=2&page=99").get_json()["page"] == 2


def test_users_cards_requires_admin(client, student_user):
    login(client, student_user)
    assert client.get("/admin/users/cards").status_code in (302, 403)

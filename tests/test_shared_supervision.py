import time

from tests.test_ui_pages import login, _assign, _thesis


def _updates(thesis_id, app):
    from superviseme.models import Thesis_Update
    with app.app_context():
        return Thesis_Update.query.filter_by(thesis_id=thesis_id, update_type="supervisor_update").count()


def _grant(app, researcher, admin):
    from superviseme import db
    from superviseme.models import Supervisor_Role
    with app.app_context():
        db.session.add(Supervisor_Role(researcher_id=researcher.id, granted_by=admin.id,
                                       granted_at=int(time.time()), active=True,
                                       created_at=int(time.time()), updated_at=int(time.time())))
        db.session.commit()


def test_supervisor_posts_update_and_is_redirected(client, supervisor_user, student_user, app):
    t = _assign(student_user, supervisor_user)
    tid = t.id
    login(client, supervisor_user)
    r = client.post("/supervisor/post_update", data={"thesis_id": tid, "content": "hello"})
    assert r.status_code == 302 and f"/supervisor/thesis/{tid}" in r.headers["Location"]
    assert _updates(tid, app) == 1


def test_post_update_requires_supervising_the_thesis(client, supervisor_user, student_user, app):
    from superviseme.models import User_mgmt
    from tests.conftest import _make_user
    t = _assign(student_user, supervisor_user)
    tid = t.id
    other = _make_user("supervisor", "othersup", "othersup@test.com")
    client.post("/login", data={"email": other.email, "password": "password"})
    client.post("/supervisor/post_update", data={"thesis_id": tid, "content": "intruder"})
    assert _updates(tid, app) == 0


def test_student_cannot_post_supervisor_update(client, supervisor_user, student_user, app):
    t = _assign(student_user, supervisor_user)
    tid = t.id
    login(client, student_user)
    client.post("/supervisor/post_update", data={"thesis_id": tid, "content": "forged"})
    assert _updates(tid, app) == 0


def test_researcher_uses_shared_view_under_researcher_urls(client, researcher_user, student_user, admin_user, app):
    t = _assign(student_user, researcher_user)
    tid = t.id
    _grant(app, researcher_user, admin_user)
    login(client, researcher_user)
    r = client.post("/researcher/supervisor/post_update", data={"thesis_id": tid, "content": "from researcher"})
    assert r.status_code == 302
    assert f"/researcher/supervisor/thesis/{tid}" in r.headers["Location"]
    assert _updates(tid, app) == 1
    ok = client.post("/researcher/supervisor/add_objective", data={"thesis_id": tid, "title": "O", "description": "d"})
    assert ok.status_code == 302 and "/researcher/" in ok.headers["Location"]


def test_researcher_without_supervisor_role_is_refused(client, researcher_user, student_user, app):
    t = _assign(student_user, researcher_user)
    tid = t.id
    login(client, researcher_user)
    r = client.post("/researcher/supervisor/post_update", data={"thesis_id": tid, "content": "x"})
    assert r.status_code == 302 and "/researcher/dashboard" in r.headers["Location"]
    assert _updates(tid, app) == 0

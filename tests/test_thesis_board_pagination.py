"""Thesis boards: server-side filtering, sorting and pagination."""
import time

from tests.conftest import _make_user


def _login(client, email):
    return client.post("/login", data={"email": email, "password": "password"}, follow_redirects=True)


def _seed(app, supervisor, n=10):
    from superviseme import db
    from superviseme.models import Thesis, Thesis_Status, Thesis_Supervisor, Thesis_Tag, Thesis_Interest, Todo
    out = []
    with app.app_context():
        student = _make_user("student", "stu_board", "stu_board@test.com")
        stu2 = _make_user("student", "stu_two", "stu_two@test.com")
        now = int(time.time())
        for i in range(n):
            t = Thesis(title=f"Thesis {i:02d}", description="d", publisher_id=supervisor.id, created_at=now + i,
                       level="master" if i % 2 else "bachelor", topic="graphs" if i < 3 else "vision",
                       is_public=bool(i % 2), frozen=(i == n - 1))
            if i == 0:
                t.author_id = student.id
            db.session.add(t)
            db.session.flush()
            db.session.add(Thesis_Supervisor(thesis_id=t.id, supervisor_id=supervisor.id, assigned_at=now))
            out.append(t.id)
        db.session.add(Thesis_Tag(thesis_id=out[2], tag="networks"))
        db.session.add(Thesis_Status(thesis_id=out[1], status="writing", updated_at=now))
        db.session.add(Thesis_Status(thesis_id=out[1], status="review", updated_at=now + 5))
        db.session.add(Thesis_Interest(thesis_id=out[3], student_id=stu2.id, status="pending", created_at=now) if hasattr(Thesis_Interest, "created_at")
                       else Thesis_Interest(thesis_id=out[3], student_id=stu2.id, status="pending"))
        db.session.add(Todo(thesis_id=out[0], author_id=supervisor.id, title="a", status="completed", created_at=now, updated_at=now))
        db.session.add(Todo(thesis_id=out[0], author_id=supervisor.id, title="b", status="pending", created_at=now, updated_at=now))
        db.session.commit()
    return out


def test_supervisor_board_pagination_and_filters(client, app, supervisor_user):
    _seed(app, supervisor_user)
    _login(client, supervisor_user.email)
    d = client.get("/supervisor/theses/cards?per=4&page=1").get_json()
    assert d["total"] == 9 and d["pages"] == 3 and d["html"].count('class="sv-item"') == 4   # frozen one excluded
    assert client.get("/supervisor/theses/cards?per=4&page=99").get_json()["page"] == 3
    # newest first by default, title sort ascending
    h = client.get("/supervisor/theses/cards?per=2&sort=title").get_json()["html"]
    assert h.index("Thesis 00") < h.index("Thesis 01")
    assert "Thesis 00" in client.get("/supervisor/theses/cards?per=1&sort=title").get_json()["html"]
    assert "Thesis 08" in client.get("/supervisor/theses/cards?per=1").get_json()["html"]
    f = lambda qs: client.get("/supervisor/theses/cards?per=48&" + qs).get_json()
    assert f("q=networks")["total"] == 1                       # tag match
    assert f("q=graphs")["total"] == 3                         # topic match
    assert f("q=stu_board")["total"] == 1 and f("student=stu_board")["total"] == 1   # student match
    assert f("state=assigned")["total"] == 1 and f("state=open")["total"] == 8
    assert f("level=master")["total"] == 4
    assert f("visibility=1")["total"] == 4 and f("visibility=0")["total"] == 5
    assert f("status=review")["total"] == 1 and f("status=writing")["total"] == 0
    assert f("status=__none")["total"] == 8
    assert f("interest=pending")["total"] == 1
    assert "Thesis 00" in f("sort=progress")["html"]
    assert f("q=%25")["total"] == 0                             # LIKE wildcards are escaped


def test_board_page_stats_and_archived(client, app, supervisor_user):
    _seed(app, supervisor_user)
    _login(client, supervisor_user.email)
    page = client.get("/supervisor/theses").data
    assert b"thArchived" in page and b"Thesis 09" in page      # frozen thesis listed in the archive table
    assert b"review" in page                                    # status filter option


def test_board_access_control(client, app, supervisor_user, admin_user, student_user):
    ids = _seed(app, supervisor_user)
    other = _make_user("supervisor", "other_sup", "other_sup@test.com")
    # not logged in
    assert client.get("/supervisor/theses/cards").status_code in (302, 401)
    # another supervisor sees none of them
    _login(client, other.email)
    assert client.get("/supervisor/theses/cards").get_json()["total"] == 0
    assert client.get("/admin/theses/cards").status_code != 200 or "total" not in (client.get("/admin/theses/cards").get_json(silent=True) or {})
    client.get("/logout")
    adm = app.test_client()
    _login(adm, admin_user.email)
    d = adm.get("/admin/theses/cards?per=48").get_json()
    assert d["total"] == 9
    assert adm.get("/admin/theses?x=1").status_code == 200
    stu = app.test_client()
    _login(stu, student_user.email)
    assert stu.get("/admin/theses/cards").get_json(silent=True) is None
    assert ids  # seeded


def test_researcher_board_cards(client, app, researcher_user):
    from superviseme import db
    from superviseme.models import Supervisor_Role
    _seed(app, researcher_user, n=5)
    _login(client, researcher_user.email)
    assert client.get("/researcher/supervisor/theses/cards").status_code in (302, 403)   # no supervisor role yet
    with app.app_context():
        now = int(time.time())
        db.session.add(Supervisor_Role(researcher_id=researcher_user.id, granted_by=researcher_user.id,
                                       granted_at=now, created_at=now, updated_at=now, active=True))
        db.session.commit()
    d = client.get("/researcher/supervisor/theses/cards").get_json()
    assert d["total"] == 4 and "/researcher/supervisor/thesis/" in d["html"]

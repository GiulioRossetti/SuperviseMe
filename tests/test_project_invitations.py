"""Project collaboration invitations: pending until accepted."""
from tests.conftest import _make_user


def login(client, email):
    return client.post("/login", data={"email": email, "password": "password"}, follow_redirects=True)


def _setup(app):
    from superviseme import db
    from superviseme.models import ResearchProject
    import time
    with app.app_context():
        owner = _make_user("researcher", "own", "own@x.it")
        guest = _make_user("researcher", "gst", "gst@x.it")
        p = ResearchProject(title="Prog", description="d", researcher_id=owner.id, created_at=int(time.time()))
        db.session.add(p)
        db.session.commit()
        return p.id, owner.id, guest.id


def _status(app, pid, uid):
    from superviseme.models import ResearchProject_Collaborator as C
    with app.app_context():
        c = C.query.filter_by(project_id=pid, collaborator_id=uid).first()
        return c.status if c else None


def test_invite_pending_then_accept(app):
    pid, oid, gid = _setup(app)
    c = app.test_client()
    login(c, "own@x.it")
    c.post("/researcher/add_collaborator", data={"project_id": pid, "collaborator_email": "gst@x.it", "role": "collaborator"})
    assert _status(app, pid, gid) == "pending"
    g = app.test_client()
    login(g, "gst@x.it")
    assert g.get(f"/researcher/project/{pid}").status_code == 403
    from superviseme.models import ResearchProject_Collaborator as C, Notification
    with app.app_context():
        inv = C.query.filter_by(project_id=pid, collaborator_id=gid).first().id
        assert Notification.query.filter_by(recipient_id=gid, notification_type="project_invitation").count() == 1
    assert b"Prog" in g.get("/researcher/dashboard").data
    assert g.post(f"/researcher/invitations/{inv}/accept").status_code == 302
    assert _status(app, pid, gid) == "accepted"
    assert g.get(f"/researcher/project/{pid}").status_code == 200


def test_decline_removes_and_others_cannot_answer(app):
    pid, oid, gid = _setup(app)
    from superviseme import db
    from superviseme.models import ResearchProject_Collaborator as C
    import time
    with app.app_context():
        inv = C(project_id=pid, collaborator_id=gid, role="viewer", status="pending", added_at=int(time.time()))
        db.session.add(inv)
        db.session.commit()
        iid = inv.id
    o = app.test_client()
    login(o, "own@x.it")
    assert o.post(f"/researcher/invitations/{iid}/accept").status_code == 404
    g = app.test_client()
    login(g, "gst@x.it")
    g.post(f"/researcher/invitations/{iid}/decline")
    assert _status(app, pid, gid) is None

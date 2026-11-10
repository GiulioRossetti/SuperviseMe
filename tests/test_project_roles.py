import time

from tests.test_ui_pages import login
from tests.conftest import _make_user


def _project_with_collab(app, owner, collab, role):
    from superviseme import db
    from superviseme.models import ResearchProject, ResearchProject_Collaborator
    with app.app_context():
        p = ResearchProject(title="P", description="d", researcher_id=owner.id, level="research",
                            created_at=int(time.time()))
        db.session.add(p)
        db.session.commit()
        db.session.add(ResearchProject_Collaborator(project_id=p.id, collaborator_id=collab.id,
                                                    role=role, added_at=int(time.time())))
        db.session.commit()
        return p.id


def test_viewer_can_read_but_not_write(client, app, researcher_user):
    with app.app_context():
        other = _make_user("researcher", "viewer1", "viewer1@test.com")
        other_id = other.id
    class U:  # light stand-in carrying id/email for login()
        pass
    pid = _project_with_collab(app, researcher_user, type("X", (), {"id": other_id})(), "viewer")
    from superviseme.models import User_mgmt, ResearchProject_Update
    with app.app_context():
        viewer = User_mgmt.query.get(other_id)
        email = viewer.email
    client.post("/login", data={"email": email, "password": "password"})
    assert client.get(f"/researcher/project/{pid}").status_code == 200
    resp = client.post(f"/researcher/project/{pid}/add_update", data={"content": "hello"})
    assert resp.status_code in (302, 403)
    with app.app_context():
        assert ResearchProject_Update.query.filter_by(project_id=pid).count() == 0


def test_editor_collaborator_can_write(client, app, researcher_user):
    with app.app_context():
        other = _make_user("researcher", "editor1", "editor1@test.com")
        other_id, email = other.id, other.email
    pid = _project_with_collab(app, researcher_user, type("X", (), {"id": other_id})(), "co-investigator")
    client.post("/login", data={"email": email, "password": "password"})
    resp = client.post(f"/researcher/project/{pid}/add_update", data={"content": "hello", "update_type": "progress"})
    assert resp.status_code in (200, 302)
    assert client.get(f"/researcher/project/{pid}").status_code == 200

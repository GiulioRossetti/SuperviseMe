"""Project templates, internal review and ORCID import for research projects."""
import json
import time

from tests.conftest import _make_user


def _login(c, email):
    return c.post("/login", data={"email": email, "password": "password"}, follow_redirects=True)


def _setup(app, owner):
    from superviseme import db
    from superviseme.models import ResearchProject, ResearchProject_Collaborator, ResearchProject_Resource
    rev = _make_user("researcher", "rev_x", "rev_x@test.com")
    now = int(time.time())
    p = ResearchProject(title="Base", description="d", researcher_id=owner.id, level="research", created_at=now)
    db.session.add(p); db.session.commit()
    db.session.add(ResearchProject_Collaborator(project_id=p.id, collaborator_id=rev.id, role="collaborator", status="accepted", added_at=now))
    res = ResearchProject_Resource(project_id=p.id, resource_type="link", resource_url="https://example.org/draft", description="Draft v1", created_at=now)
    db.session.add(res); db.session.commit()
    return p.id, rev.id, res.id


def test_review_flow(client, app, researcher_user):
    pid, rid, resid = _setup(app, researcher_user)
    _login(client, researcher_user.email)
    client.post(f"/researcher/project/{pid}/reviews/request", data={"resource_id": resid, "reviewer_id": researcher_user.id})  # self: refused
    client.post(f"/researcher/project/{pid}/reviews/request", data={"resource_id": resid, "reviewer_id": rid, "note": "please"})
    client.post(f"/researcher/project/{pid}/reviews/request", data={"resource_id": resid, "reviewer_id": rid})  # duplicate
    from superviseme.models import ResearchProject_Review as R, Notification
    assert R.query.filter_by(project_id=pid).count() == 1
    assert Notification.query.filter_by(recipient_id=rid, notification_type="project_review_request").count() == 1
    review = R.query.filter_by(project_id=pid).one()
    assert client.post(f"/researcher/project/{pid}/reviews/{review.id}/decide", data={"decision": "approved"}).status_code == 403
    r = app.test_client(); _login(r, "rev_x@test.com")
    assert b"Draft v1" in r.get(f"/researcher/project/{pid}/output").data
    r.post(f"/researcher/project/{pid}/reviews/{review.id}/decide", data={"decision": "changes_requested", "comment": "fix intro"})
    from superviseme import db
    db.session.expire_all()
    review = db.session.get(R, review.id)
    assert (review.status, review.comment) == ("changes_requested", "fix intro")
    assert Notification.query.filter_by(recipient_id=researcher_user.id, notification_type="project_review_done").count() == 1
    r.post(f"/researcher/project/{pid}/reviews/{review.id}/decide", data={"decision": "approved"})   # already decided
    db.session.expire_all()
    assert db.session.get(R, review.id).status == "changes_requested"


def test_duplicate_project(client, app, researcher_user):
    from superviseme import db
    from superviseme.models import (ResearchProject, ResearchProject_Objective, ResearchProject_Todo, ResearchProject_Milestone)
    pid, rid, _ = _setup(app, researcher_user)
    now = int(time.time())
    p = db.session.get(ResearchProject, pid)
    p.start_date = "2026-01-01"
    db.session.add(ResearchProject_Objective(project_id=pid, author_id=researcher_user.id, title="Obj", description="x", created_at=now))
    db.session.add(ResearchProject_Todo(project_id=pid, author_id=researcher_user.id, title="T1", status="pending", created_at=now, updated_at=now))
    db.session.add(ResearchProject_Todo(project_id=pid, author_id=researcher_user.id, title="T2", status="completed", created_at=now, updated_at=now))
    db.session.add(ResearchProject_Milestone(project_id=pid, title="M1", due_date=1767268800 + 30 * 86400, created_at=now))
    db.session.commit()
    _login(client, researcher_user.email)
    client.post(f"/researcher/project/{pid}/duplicate", data={"title": "Next edition", "start_date": "2027-01-01"})
    copy = ResearchProject.query.filter_by(title="Next edition").one()
    assert copy.researcher_id == researcher_user.id and copy.start_date == "2027-01-01"
    assert [o.title for o in ResearchProject_Objective.query.filter_by(project_id=copy.id)] == ["Obj"]
    assert [t.title for t in ResearchProject_Todo.query.filter_by(project_id=copy.id)] == ["T1"]
    m = ResearchProject_Milestone.query.filter_by(project_id=copy.id).one()
    assert m.due_date == 1767268800 + 30 * 86400 + 365 * 86400
    # collaborators of the original are not copied
    from superviseme.models import ResearchProject_Collaborator as C
    assert C.query.filter_by(project_id=copy.id).count() == 0
    # an outsider cannot copy it
    out = _make_user("researcher", "out_x", "out_x@test.com")
    o = app.test_client(); _login(o, out.email)
    assert o.post(f"/researcher/project/{pid}/duplicate", data={}).status_code == 403


def test_orcid_import(client, app, researcher_user):
    from superviseme import db
    from superviseme.models import OrcidActivity, ResearchProject, ResearchProject_Publication as P
    pid, _, _ = _setup(app, researcher_user)
    researcher_user.orcid_id = "0000-0002-1825-0097"
    now = int(time.time())
    work = OrcidActivity(user_id=researcher_user.id, title="Imported paper", type="journal-article", publication_date="2022",
                         external_ids=json.dumps([{"type": "doi", "value": "10.1234/abcd", "url": None}]), created_at=now, updated_at=now)
    fund = OrcidActivity(user_id=researcher_user.id, title="Big grant", type="funding", organization="EU", publication_date="2024",
                         external_ids=json.dumps([{"type": "grant_number", "value": "GA-42", "url": None}]), created_at=now, updated_at=now)
    job = OrcidActivity(user_id=researcher_user.id, title="Researcher", type="employment", organization="CNR", publication_date="2023",
                        created_at=now, updated_at=now)
    db.session.add_all([work, fund, job]); db.session.commit()
    _login(client, researcher_user.email)
    page = client.get(f"/researcher/project/{pid}/output").get_data(as_text=True)
    assert "Imported paper" in page and "Big grant" in page and "CNR" in page   # candidates + affiliation in the team card
    assert "Researcher</label>" not in page                                      # affiliations are not offered as publications
    client.post(f"/researcher/project/{pid}/publications/import_orcid", data={"activity_id": [work.id, job.id]})
    pub = P.query.filter_by(project_id=pid).one()
    assert (pub.title, pub.doi, pub.year, pub.pub_type) == ("Imported paper", "10.1234/abcd", 2022, "article")
    assert "Imported paper</label>" not in client.get(f"/researcher/project/{pid}/output").get_data(as_text=True)  # no longer offered
    client.post(f"/researcher/project/{pid}/funding/from_orcid", data={"activity_id": fund.id})
    db.session.expire_all()
    p = db.session.get(ResearchProject, pid)
    assert (p.funder, p.grant_id, p.start_date) == ("EU", "GA-42", "2024-01-01")


def test_software_and_outputs_pages(client, app, researcher_user, admin_user):
    from superviseme import db
    from superviseme.models import ResearchProject, ResearchProject_Software as S
    p = ResearchProject(title="Tools", description="d", researcher_id=researcher_user.id, created_at=int(time.time()), is_public=True)
    db.session.add(p); db.session.commit()
    _login(client, researcher_user.email)
    client.post(f"/researcher/project/{p.id}/software/add", data={"title": "graphkit", "version": "1.0", "license": "MIT", "language": "Python",
                                                                 "repo_url": "javascript:alert(1)", "doi": "https://doi.org/10.5281/zenodo.9"})
    client.post(f"/researcher/project/{p.id}/software/add", data={"title": "", "version": "x"})  # title required
    client.post(f"/researcher/project/{p.id}/software/add", data={"title": "viz", "repo_url": "https://github.com/x/viz"})
    sw = S.query.filter_by(project_id=p.id).order_by(S.id).all()
    assert [s.title for s in sw] == ["graphkit", "viz"] and sw[0].repo_url is None and sw[0].doi == "10.5281/zenodo.9"
    assert b"graphkit" in client.get(f"/researcher/project/{p.id}/output").data
    page = client.get("/researcher/software").data
    assert b"graphkit" in page and b"viz" in page
    bib = client.get("/researcher/software?format=bib").data
    assert b"@software{graphkit" in bib and b"version = {1.0}" in bib
    assert client.get("/researcher/datasets").status_code == 200
    pub = client.get(f"/projects/{p.id}").data
    assert b"graphkit" in pub
    client.post(f"/researcher/project/{p.id}/software/{sw[0].id}/delete")
    assert S.query.filter_by(project_id=p.id).count() == 1
    client.post("/logout")
    _login(client, admin_user.email)
    assert b"viz" in client.get("/admin/research/software").data
    assert b"viz" not in client.get("/admin/research/software?q=zzz").data
    assert b"@software{viz" in client.get("/admin/research/software?format=bib").data
    assert client.get("/admin/research/datasets").status_code == 200
    assert b"/admin/research/software" in client.get("/admin/research").data
    from superviseme.utils.projects import delete_project_cascade
    delete_project_cascade(db.session.get(ResearchProject, p.id))
    assert S.query.count() == 0


def test_researcher_edits_datasets_and_software(client, researcher_user, supervisor_user):
    from superviseme import db
    from superviseme.models import ResearchProject, ResearchProject_Software as S, ResearchProject_Dataset as D
    p = ResearchProject(title="Editable", description="d", researcher_id=researcher_user.id, created_at=int(time.time()))
    other = ResearchProject(title="Not mine", description="d", researcher_id=supervisor_user.id, created_at=int(time.time()))
    db.session.add_all([p, other]); db.session.commit()
    _login(client, researcher_user.email)
    client.post(f"/researcher/project/{p.id}/software/add", data={"title": "tool", "version": "1"})
    client.post(f"/researcher/project/{p.id}/datasets/add", data={"title": "ds", "fair_findable": "on"})
    sw, ds = S.query.filter_by(project_id=p.id).one(), D.query.filter_by(project_id=p.id).one()
    client.post(f"/researcher/project/{p.id}/software/{sw.id}/edit", data={"title": "tool2", "version": "2", "license": "MIT", "repo_url": "https://github.com/a/b"})
    client.post(f"/researcher/project/{p.id}/datasets/{ds.id}/edit", data={"title": "ds2", "doi": "10.1234/x", "fair_findable": "on", "fair_accessible": "on"})
    db.session.refresh(sw); db.session.refresh(ds)
    assert (sw.title, sw.version, sw.license, sw.repo_url) == ("tool2", "2", "MIT", "https://github.com/a/b")
    assert ds.title == "ds2" and ds.doi == "10.1234/x" and ds.fair == "findable,accessible"
    client.post(f"/researcher/project/{p.id}/software/{sw.id}/edit", data={"title": ""})
    db.session.refresh(sw)
    assert sw.title == "tool2"
    page = client.get(f"/researcher/project/{p.id}/output").data.decode()
    assert f"editS{sw.id}" in page and f"editD{ds.id}" in page
    # not allowed on someone else's project
    assert client.post(f"/researcher/project/{other.id}/software/{sw.id}/edit", data={"title": "x"}).status_code in (302, 403, 404)
    db.session.refresh(sw)
    assert sw.title == "tool2"

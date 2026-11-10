"""Admin research area: overview, project management, publications catalog, sidebar."""
import time

from tests.conftest import _make_user


def _login(c, email):
    return c.post("/login", data={"email": email, "password": "password"}, follow_redirects=True)


def _data(app, owner):
    from superviseme import db
    from superviseme.models import (ResearchProject, ResearchProject_Collaborator, ResearchProject_Milestone,
                                    ResearchProject_Publication, ResearchProject_Review, ResearchProject_Resource)
    now = int(time.time())
    guest = _make_user("researcher", "gst_a", "gst_a@test.com")
    p = ResearchProject(title="Graph Mining", description="d", researcher_id=owner.id, level="research", area="Network Science",
                        funder="ERC", grant_id="G-1", created_at=now)
    db.session.add(p); db.session.commit()
    db.session.add(ResearchProject_Collaborator(project_id=p.id, collaborator_id=guest.id, role="viewer", status="pending", added_at=now))
    db.session.add(ResearchProject_Milestone(project_id=p.id, title="Late deliverable", due_date=now - 86400 * 3, created_at=now))
    db.session.add(ResearchProject_Publication(project_id=p.id, title="Community Detection Revisited", authors="Ada Lovelace", year=2024,
                                               venue="JNS", pub_type="article", created_at=now))
    res = ResearchProject_Resource(project_id=p.id, resource_type="link", resource_url="https://example.org/d", description="Draft", created_at=now)
    db.session.add(res); db.session.commit()
    db.session.add(ResearchProject_Review(project_id=p.id, resource_id=res.id, requested_by=owner.id, reviewer_id=guest.id,
                                          created_at=now, updated_at=now))
    db.session.commit()
    return p.id, guest.id


def test_admin_only(client, app, researcher_user, student_user):
    pid, _g = _data(app, researcher_user)
    for who in (researcher_user, student_user):
        c = app.test_client()
        _login(c, who.email)
        for url in ("/admin/research", f"/admin/research/projects/{pid}", "/admin/research/publications"):
            assert c.get(url).status_code != 200 or b"Graph Mining" not in c.get(url).data
        assert c.post(f"/admin/research/projects/{pid}/freeze").status_code != 200
    from superviseme.models import ResearchProject
    assert ResearchProject.query.get(pid).frozen in (False, None)


def test_overview_filters_and_detail(client, app, admin_user, researcher_user):
    pid, gid = _data(app, researcher_user)
    _login(client, admin_user.email)
    html = client.get("/admin/research").data.decode()
    assert "Graph Mining" in html and "Late deliverable" in html and "href=\"/admin/research/publications\"" in html
    assert "Graph Mining" in client.get("/admin/research?q=ERC").data.decode()
    assert "Graph Mining" in client.get("/admin/research?state=funded&area=Network+Science").data.decode()
    assert "No projects match" in client.get("/admin/research?state=frozen").data.decode()
    assert "No projects match" in client.get("/admin/research?q=zzzz").data.decode()
    detail = client.get(f"/admin/research/projects/{pid}")
    assert detail.status_code == 200
    body = detail.data.decode()
    assert "Community Detection Revisited" in body and "Invitation pending" in body and "overdue" in body
    assert client.get("/admin/research/projects/9999").status_code == 404
    assert "Graph Mining" in client.get("/admin").data.decode() or client.get("/admin/dashboard").status_code == 200


def test_manage_actions(client, app, admin_user, researcher_user):
    from superviseme import db
    from superviseme.models import ResearchProject, ResearchProject_Collaborator
    pid, gid = _data(app, researcher_user)
    _login(client, admin_user.email)
    client.post(f"/admin/research/projects/{pid}/freeze")
    client.post(f"/admin/research/projects/{pid}/visibility")
    db.session.expire_all()
    p = db.session.get(ResearchProject, pid)
    assert p.frozen is True and p.is_public is True
    client.post(f"/admin/research/projects/{pid}/owner", data={"new_owner_id": admin_user.id})  # not a researcher: refused
    db.session.expire_all()
    assert db.session.get(ResearchProject, pid).researcher_id == researcher_user.id
    client.post(f"/admin/research/projects/{pid}/owner", data={"new_owner_id": gid})
    db.session.expire_all()
    assert db.session.get(ResearchProject, pid).researcher_id == gid
    assert ResearchProject_Collaborator.query.filter_by(project_id=pid, collaborator_id=researcher_user.id, status="accepted").count() == 1
    assert ResearchProject_Collaborator.query.filter_by(project_id=pid, collaborator_id=gid).count() == 0
    r = client.post(f"/admin/research/projects/{pid}/delete")
    assert r.status_code == 302, r.data[:300]
    db.session.expire_all()
    assert db.session.get(ResearchProject, pid) is None


def test_publications_catalog_and_search(client, app, admin_user, researcher_user):
    _data(app, researcher_user)
    _login(client, admin_user.email)
    assert "Community Detection" in client.get("/admin/research/publications?year=2024&type=article").data.decode()
    assert "Community Detection" not in client.get("/admin/research/publications?year=1999").data.decode()
    bib = client.get("/admin/research/publications?format=bib&q=Community")
    assert bib.status_code == 200 and b"@article{Lovelace2024" in bib.data
    res = client.post("/admin/search", data={"search_term": "Graph"})
    assert b"Graph Mining" in res.data


def test_sidebar_sections(client, admin_user):
    _login(client, admin_user.email)
    html = client.get("/admin/research").data.decode()
    for needle in ("/admin/research", "/admin/research/publications", "/admin/users", "/admin/theses", "/agenda", "/admin/privacy"):
        assert needle in html


def test_publications_live_partial(client, app, admin_user, researcher_user):
    _data(app, researcher_user)
    _login(client, admin_user.email)
    r = client.get("/admin/research/publications?q=Community", headers={"X-Requested-With": "fetch"})
    body = r.data.decode()
    assert r.status_code == 200 and "Community Detection" in body and "<html" not in body and 'data-total="1"' in body
    assert "<html" in client.get("/admin/research/publications").data.decode()

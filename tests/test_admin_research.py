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


def test_live_search_suggest_and_regions(client, app, admin_user, researcher_user):
    _login(client, admin_user.email)
    r = client.get("/search/suggest?q=" + researcher_user.surname[:3])
    assert r.status_code == 200 and r.is_json and "items" in r.json
    assert any(i["group"] for i in r.json["items"]) or r.json["items"] == []
    assert client.get("/search/suggest?q=a").json["items"] == []
    page = client.get("/search?q=zz").data.decode()
    assert 'data-live-region="#searchResults"' in page and 'id="searchResults"' in page
    assert 'data-suggest-url="/search/suggest"' in page and "live-search.js" in page
    pub = client.get("/theses").data.decode() if client.get("/theses").status_code == 200 else ""
    assert not pub or 'id="thesesResults"' in pub


def test_suggest_requires_login(app):
    assert app.test_client().get("/search/suggest?q=abc").status_code == 302


def test_avatars_default_or_custom(client, app, admin_user, supervisor_user, student_user):
    from superviseme import db
    _login(client, admin_user.email)
    detail = f"/admin/user/{student_user.id}"
    html = client.get(detail).data.decode()
    if client.get(detail).status_code != 200:
        html = client.get(f"/admin/users/{student_user.id}").data.decode()
    assert "undraw_profile.svg" in html and 'class="sm-avatar sm-avatar-lg' in html
    student_user.profile_pic = "avatars/mine.png"
    db.session.commit()
    html = client.get(detail).data.decode() if client.get(detail).status_code == 200 else client.get(f"/admin/users/{student_user.id}").data.decode()
    assert "/media/avatar/mine.png" in html
    # an initials-only fallback must not exist any more
    assert 'class="sm-avatar">' not in html


def test_associate_outputs_with_users_and_theses(client, app, admin_user, researcher_user, supervisor_user, student_user):
    from superviseme import db
    from superviseme.models import ResearchOutput_Link, ResearchProject_Software, ResearchProject_Publication
    from tests.test_ui_pages import _assign
    pid, gid = _data(app, researcher_user)
    t = _assign(student_user, supervisor_user)
    _login(client, admin_user.email)
    # create software from the catalog, then associate a user and a thesis
    r = client.post("/admin/research/output/software/new", data={"title": "adm-tool", "project_id": pid, "version": "2.0", "url": "https://github.com/x/adm"})
    sw = ResearchProject_Software.query.filter_by(title="adm-tool").one()
    assert r.status_code == 302 and sw.repo_url == "https://github.com/x/adm" and sw.project_id == pid
    assert client.post("/admin/research/output/software/new", data={"title": "x", "project_id": 99999}).status_code == 302
    assert ResearchProject_Software.query.count() == 1
    client.post(f"/admin/research/output/software/{sw.id}/link", data={"user_id": student_user.id, "thesis_id": t.id})
    client.post(f"/admin/research/output/software/{sw.id}/link", data={"user_id": student_user.id})  # duplicate ignored
    assert ResearchOutput_Link.query.filter_by(kind="software", output_id=sw.id).count() == 2
    page = client.get(f"/admin/research/output/software/{sw.id}").data.decode()
    assert "adm-tool" in page and student_user.surname in page
    assert "adm-tool" in client.get("/admin/research/software").data.decode()
    assert "Manage associations" in client.get("/admin/research/software").data.decode()
    assert "adm-tool" in client.get(f"/admin/user/{student_user.id}").data.decode()
    assert "adm-tool" in client.get(f"/admin/thesis/{t.id}").data.decode()
    # search finds outputs by associated user or thesis (live partial too)
    hdr = {"X-Requested-With": "fetch"}
    assert "adm-tool" in client.get(f"/admin/research/software?q={student_user.surname}").data.decode()
    assert "adm-tool" in client.get(f"/admin/research/software?q={t.title[:12]}").data.decode()
    assert "adm-tool" not in client.get("/admin/research/software?q=zzzznomatch").data.decode()
    pub0 = ResearchProject_Publication.query.first()
    client.post(f"/admin/research/output/publication/{pub0.id}/link", data={"thesis_id": t.id})
    assert pub0.title in client.get(f"/admin/research/publications?q={t.title[:12]}", headers=hdr).data.decode()
    client.post(f"/admin/research/output/publication/{pub0.id}/link/{ResearchOutput_Link.query.filter_by(kind='publication', output_id=pub0.id, thesis_id=t.id).one().id}/remove")
    # an associated researcher sees it in their own list even outside their projects
    client.post(f"/admin/research/output/software/{sw.id}/link", data={"user_id": supervisor_user.id})
    other = ResearchProject_Software.query.get(sw.id)
    from superviseme.models import ResearchProject
    from superviseme.utils import research_output as ro
    assert [o.id for o in ro.linked_for_user(supervisor_user, "software")] == [sw.id]
    # publications: move to another project, unlink, delete
    pub = ResearchProject_Publication.query.first()
    link = ResearchOutput_Link.query.filter_by(kind="software", output_id=sw.id, thesis_id=t.id).one()
    client.post(f"/admin/research/output/software/{sw.id}/link/{link.id}/remove")
    assert ResearchOutput_Link.query.filter_by(id=link.id).count() == 0
    client.post(f"/admin/research/output/publication/{pub.id}/link", data={"user_id": researcher_user.id})
    assert "Manage associations" in client.get("/admin/research/publications").data.decode()
    client.post(f"/admin/research/output/software/{sw.id}/delete")
    assert ResearchProject_Software.query.count() == 0 and ResearchOutput_Link.query.filter_by(kind="software").count() == 0
    assert client.get("/admin/research/output/bogus/1").status_code == 404
    # deleting the thesis removes its links
    client.post(f"/admin/research/output/publication/{pub.id}/link", data={"thesis_id": t.id})
    from superviseme.utils.thesis_management import delete_thesis_with_dependencies
    assert delete_thesis_with_dependencies(t.id)[0]
    assert ResearchOutput_Link.query.filter_by(thesis_id=t.id).count() == 0


def test_admin_sets_supervisor_capacity(client, admin_user, supervisor_user):
    _login(client, admin_user.email)
    base = {"user_id": supervisor_user.id, "name": supervisor_user.name, "surname": supervisor_user.surname,
            "email": supervisor_user.email, "username": supervisor_user.username, "user_type": "supervisor"}
    client.post("/admin/update_user", data={**base, "max_students": "3"})
    from superviseme import db
    db.session.refresh(supervisor_user)
    assert supervisor_user.max_students == 3
    client.post("/admin/update_user", data={**base, "max_students": "500"})
    db.session.refresh(supervisor_user)
    assert supervisor_user.max_students == 3
    client.post("/admin/update_user", data={**base, "max_students": ""})
    db.session.refresh(supervisor_user)
    assert supervisor_user.max_students is None

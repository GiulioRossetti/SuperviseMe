"""Research output: publications, funding, milestones, datasets, thesis links, public page, portfolio, digest."""
import time

from tests.conftest import _make_user


def _login(c, email):
    return c.post("/login", data={"email": email, "password": "password"}, follow_redirects=True)


def _project(app, owner_id, **kw):
    from superviseme import db
    from superviseme.models import ResearchProject
    with app.app_context():
        p = ResearchProject(title="Graphs", description="About graphs", researcher_id=owner_id, level="research",
                            created_at=int(time.time()), **kw)
        db.session.add(p)
        db.session.commit()
        return p.id


def _collab(app, pid, uid, role, status="accepted"):
    from superviseme import db
    from superviseme.models import ResearchProject_Collaborator as C
    with app.app_context():
        db.session.add(C(project_id=pid, collaborator_id=uid, role=role, status=status, added_at=int(time.time())))
        db.session.commit()


def test_publications_and_bibtex(client, app, researcher_user, monkeypatch):
    pid = _project(app, researcher_user.id)
    _login(client, researcher_user.email)
    client.post(f"/researcher/project/{pid}/publications/add", data={
        "title": "Graph {things}", "authors": "Ada Lovelace, Alan Turing", "year": "2024", "venue": "J. Graphs",
        "doi": "https://doi.org/10.1000/abc.1", "pub_type": "article"})
    client.post(f"/researcher/project/{pid}/publications/add", data={"title": "Dup", "doi": "10.1000/abc.1"})
    import superviseme.utils.academic_apis as aa
    monkeypatch.setattr(aa, "get_crossref_doi", lambda d: {"doi": d, "title": "From Crossref", "authors": ["Bob Ross"],
                                                            "year": 2020, "venue": "Conf", "type": "proceedings-article", "url": "https://doi.org/" + d})
    client.post(f"/researcher/project/{pid}/publications/add", data={"doi": "10.5555/xyz"})
    client.post(f"/researcher/project/{pid}/publications/add", data={"doi": "not-a-doi"})
    from superviseme.models import ResearchProject_Publication as P
    with app.app_context():
        titles = sorted(p.title for p in P.query.filter_by(project_id=pid))
    assert titles == ["From Crossref", "Graph {things}"]
    bib = client.get(f"/researcher/project/{pid}/publications.bib").get_data(as_text=True)
    assert "@article{Lovelace2024" in bib and "Ada Lovelace and Alan Turing" in bib and "Graph \\{things\\}" in bib
    assert "@inproceedings{" in bib
    assert "From Crossref" in client.get("/researcher/publications").get_data(as_text=True)
    assert client.get(f"/researcher/project/{pid}/output").status_code == 200


def test_permissions_viewer_and_pending(client, app, researcher_user):
    viewer = _make_user("researcher", "viewer_o", "viewer_o@test.com")
    pending = _make_user("researcher", "pend_o", "pend_o@test.com")
    pid = _project(app, researcher_user.id)
    _collab(app, pid, viewer.id, "viewer")
    _collab(app, pid, pending.id, "collaborator", "pending")
    v = app.test_client(); _login(v, "viewer_o@test.com")
    assert v.get(f"/researcher/project/{pid}/output").status_code == 200
    assert v.post(f"/researcher/project/{pid}/milestones/add", data={"title": "x", "due_date": "2030-01-01"}).status_code == 403
    assert v.post(f"/researcher/project/{pid}/visibility", data={"is_public": "on"}).status_code == 403
    p = app.test_client(); _login(p, "pend_o@test.com")
    assert p.get(f"/researcher/project/{pid}/output").status_code == 403


def test_funding_milestones_datasets_and_agenda(client, app, researcher_user):
    pid = _project(app, researcher_user.id)
    _login(client, researcher_user.email)
    client.post(f"/researcher/project/{pid}/funding", data={"funder": "ERC", "grant_id": "G-1", "start_date": "2025-01-01", "end_date": "2026-01-01"})
    client.post(f"/researcher/project/{pid}/funding", data={"funder": "BAD", "start_date": "2026-01-01", "end_date": "2025-01-01"})
    client.post(f"/researcher/project/{pid}/milestones/add", data={"title": "D1.1 report", "due_date": __import__("datetime").date.fromtimestamp(time.time() + 30 * 86400).isoformat()})
    client.post(f"/researcher/project/{pid}/milestones/add", data={"title": "bad", "due_date": "nope"})
    client.post(f"/researcher/project/{pid}/datasets/add", data={"title": "Corpus", "doi": "10.5281/zenodo.1", "license": "CC-BY",
                                                                 "fair_findable": "on", "fair_reusable": "on", "url": "javascript:alert(1)"})
    from superviseme.models import ResearchProject, ResearchProject_Milestone as M, ResearchProject_Dataset as D
    with app.app_context():
        p = db_get(ResearchProject, pid)
        assert (p.funder, p.grant_id, p.start_date) == ("ERC", "G-1", "2025-01-01")
        assert M.query.filter_by(project_id=pid).count() == 1
        d = D.query.filter_by(project_id=pid).one()
        assert d.fair == "findable,reusable" and d.url is None
        mid = M.query.filter_by(project_id=pid).one().id
    client.post(f"/researcher/project/{pid}/milestones/{mid}/toggle")
    with app.app_context():
        assert db_get(M, mid).status == "done"
    client.post(f"/researcher/project/{pid}/milestones/{mid}/toggle")
    assert "D1.1 report" in client.get("/agenda").get_data(as_text=True)
    from superviseme import db
    researcher_user.agenda_token = "t" * 32
    db.session.commit()
    ics = client.get("/agenda/feed/" + "t" * 32 + ".ics")
    assert ics.status_code == 200 and "Milestone: D1.1 report" in ics.get_data(as_text=True)


def db_get(model, pk):
    from superviseme import db
    return db.session.get(model, pk)


def test_thesis_link_public_page_transfer_portfolio_and_digest(client, app, researcher_user, supervisor_user):
    from superviseme import db
    from superviseme.models import Thesis, Thesis_Supervisor, ResearchProject_Thesis, ResearchProject
    co = _make_user("researcher", "co_o", "co_o@test.com")
    pid = _project(app, researcher_user.id)
    _collab(app, pid, co.id, "collaborator")
    with app.app_context():
        t = Thesis(title="Thesis on graphs", description="d", publisher_id=researcher_user.id, created_at=int(time.time()))
        other = Thesis(title="Foreign", description="d", publisher_id=supervisor_user.id, created_at=int(time.time()))
        db.session.add_all([t, other]); db.session.commit()
        tid, oid = t.id, other.id
    _login(client, researcher_user.email)
    client.post(f"/researcher/project/{pid}/theses/link", data={"thesis_id": tid})
    client.post(f"/researcher/project/{pid}/theses/link", data={"thesis_id": oid})   # not managed: refused
    with app.app_context():
        assert [l.thesis_id for l in ResearchProject_Thesis.query.filter_by(project_id=pid)] == [tid]
    # public page: off by default, then on with chosen fields
    anon = app.test_client()
    assert anon.get(f"/projects/{pid}").status_code == 404
    client.post(f"/researcher/project/{pid}/visibility", data={"is_public": "on", "show_description": "on"})
    page = anon.get(f"/projects/{pid}")
    assert page.status_code == 200 and b"About graphs" in page.data and b"Team" not in page.data
    # portfolio
    pf = client.get("/researcher/portfolio")
    assert pf.status_code == 200 and b"Graphs" not in b"" and b"Portfolio" in pf.data
    # digest
    from superviseme.utils.research_output import researcher_digest
    with app.app_context():
        d = researcher_digest(db_get(__import__("superviseme.models", fromlist=["x"]).User_mgmt, researcher_user.id))
        assert d and "weekly research summary" in d["text"]
    # transfer to the collaborator
    client.post(f"/researcher/project/{pid}/transfer", data={"new_owner_id": researcher_user.id})   # self: not a collaborator
    client.post(f"/researcher/project/{pid}/transfer", data={"new_owner_id": co.id})
    from superviseme.models import ResearchProject_Collaborator as C
    with app.app_context():
        assert db_get(ResearchProject, pid).researcher_id == co.id
        assert C.query.filter_by(project_id=pid, collaborator_id=researcher_user.id, status="accepted").count() == 1
    assert client.post(f"/researcher/project/{pid}/visibility", data={}).status_code == 403   # no longer the owner

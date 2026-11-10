from tests.test_ui_pages import login


def test_researcher_projects_page(client, researcher_user, app):
    from superviseme.models import ResearchProject
    from superviseme import db
    with app.app_context():
        db.session.add(ResearchProject(title="Graph \"Q\" study", description="desc 'x'", level="pilot", researcher_id=researcher_user.id, created_at=1700000000))
        db.session.commit()
    login(client, researcher_user)
    r = client.get("/researcher/projects")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "pj-grid" in html and "Graph" in html


def test_researcher_projects_empty(client, researcher_user):
    login(client, researcher_user)
    r = client.get("/researcher/projects")
    assert r.status_code == 200


import io

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def _create(client, **kw):
    data = {"title": "P", "description": "d", "level": "", "area": "", "tags": "", "parent_id": ""}
    data.update(kw)
    return client.post("/researcher/create_project", data=data, content_type="multipart/form-data", follow_redirects=False)


def _get(app, title):
    from superviseme.models import ResearchProject
    with app.app_context():
        return ResearchProject.query.filter_by(title=title).first().id


def test_create_project_with_metadata_and_image(client, researcher_user, app, tmp_path):
    app.config["UPLOAD_FOLDER"] = str(tmp_path)
    login(client, researcher_user)
    r = _create(client, title="Root", level="programme", area="Network science", tags="Graphs, NLP,, graphs")
    assert r.status_code == 302
    rid = _get(app, "Root")
    r = _create(client, title="Paper A", level="paper", parent_id=str(rid), tags="x",
                images=(io.BytesIO(PNG), "cover.png"))
    assert r.status_code == 302
    from superviseme.models import ResearchProject
    with app.app_context():
        root = ResearchProject.query.get(rid)
        assert root.tag_list == ["graphs", "nlp"] and root.area == "Network science"
        child = ResearchProject.query.filter_by(title="Paper A").first()
        assert child.parent_id == rid and child.level == "paper" and len(child.images) == 1
        fname = child.images[0].filename
    page = client.get("/researcher/projects").get_data(as_text=True)
    assert "/media/" + fname in page and "#graphs" in page and "Paper" in page
    assert client.get("/media/" + fname).status_code == 200
    detail = client.get("/researcher/project/%d" % rid)
    assert detail.status_code == 200 and "Paper A" in detail.get_data(as_text=True)


def test_parent_cycle_rejected(client, researcher_user, app):
    login(client, researcher_user)
    _create(client, title="A1")
    a = _get(app, "A1")
    _create(client, title="B1", parent_id=str(a))
    b = _get(app, "B1")
    client.post("/researcher/update_project", data={"project_id": a, "parent_id": str(b)})
    from superviseme.models import ResearchProject
    with app.app_context():
        assert ResearchProject.query.get(a).parent_id is None


def test_links_report_and_delete(client, researcher_user, app):
    login(client, researcher_user)
    _create(client, title="L1")
    _create(client, title="L2", parent_id=str(_get(app, "L1")))
    a, b = _get(app, "L1"), _get(app, "L2")
    client.post("/researcher/project/%d/links" % a, data={"linked_id": b, "relation": "extends"})
    client.post("/researcher/project/%d/links" % a, data={"linked_id": b, "relation": "extends"})
    from superviseme.models import ResearchProject_Link
    with app.app_context():
        assert ResearchProject_Link.query.count() == 1
    pdf = client.get("/researcher/project/%d/report" % a)
    assert pdf.status_code == 200 and pdf.data.startswith(b"%PDF")
    md = client.get("/researcher/project/%d/report?format=md" % a)
    assert md.status_code == 200 and b"# L1" in md.data and b"L2" in md.data
    other = client.get("/researcher/project/%d" % b).get_data(as_text=True)
    assert "L1" in other
    r = client.delete("/researcher/delete_project/%d" % a)
    assert r.status_code == 200
    from superviseme.models import ResearchProject
    with app.app_context():
        assert ResearchProject_Link.query.count() == 0
        assert ResearchProject.query.get(b).parent_id is None


def test_other_researcher_cannot_access(client, researcher_user, app):
    from tests.conftest import _make_user
    login(client, researcher_user)
    _create(client, title="Private")
    pid = _get(app, "Private")
    intruder = _make_user("researcher", "intruder", "intruder@test.com")
    client.get("/logout")
    login(client, intruder)
    assert client.get("/researcher/project/%d/report" % pid).status_code == 403
    assert client.post("/researcher/project/%d/links" % pid, data={}).status_code == 403

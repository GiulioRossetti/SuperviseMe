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

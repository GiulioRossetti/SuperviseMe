from tests.test_ui_pages import login


def test_add_view_and_delete_web_links(client, supervisor_user, student_user, app):
    login(client, supervisor_user)
    client.post("/profile/links", data={"url": "linkedin.com/in/someone", "label": ""})
    client.post("/profile/links", data={"url": "https://example.org/~me", "label": "My site"})
    client.post("/profile/links", data={"url": "https://example.org/~me/", "label": "dup"})
    client.post("/profile/links", data={"url": "javascript:alert(1)", "label": "x"})
    client.post("/profile/links", data={"url": "ftp://example.org", "label": "x"})
    from superviseme.models import User_Link
    with app.app_context():
        links = User_Link.query.filter_by(user_id=supervisor_user.id).all()
        assert [l.url for l in links] == ["https://linkedin.com/in/someone", "https://example.org/~me"]
        sup_id, lid = supervisor_user.id, links[0].id
    page = client.get("/profile").get_data(as_text=True)
    assert "LinkedIn" in page and "My site" in page and "javascript:" not in page
    client.get("/logout")
    login(client, student_user)
    pub = client.get("/users/%d" % sup_id)
    assert pub.status_code == 200 and "https://example.org/~me" in pub.get_data(as_text=True)
    client.post("/profile/links/%d/delete" % lid)  # not the owner: ignored
    with app.app_context():
        assert User_Link.query.count() == 2
    client.get("/logout")
    login(client, supervisor_user)
    client.post("/profile/links/%d/delete" % lid)
    with app.app_context():
        assert User_Link.query.count() == 1


def test_link_limit(client, researcher_user, app):
    login(client, researcher_user)
    for i in range(12):
        client.post("/profile/links", data={"url": "https://example.org/%d" % i})
    from superviseme.models import User_Link
    with app.app_context():
        assert User_Link.query.count() == 10

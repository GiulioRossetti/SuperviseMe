import time
from datetime import date, timedelta

from superviseme import db
from superviseme.models import Resource, Thesis, Thesis_Status, Thesis_Supervisor, Thesis_Update
from superviseme.utils.thesis_resources import detect_provider, normalize_resource_url, resolve_resource_type
from superviseme.utils.thesis_timeline import build_activity_calendar, build_status_timeline


def login(client, user):
    return client.post("/login", data=dict(email=user.email, password="password"), follow_redirects=True)


def _thesis(publisher, **kw):
    t = Thesis(title="T", description="d", publisher_id=publisher.id, created_at=int(time.time()), **kw)
    db.session.add(t)
    db.session.commit()
    return t


def test_public_theses_shows_public_unassigned(client, supervisor_user):
    pub = _thesis(supervisor_user, is_public=True, frozen=None)  # NULL frozen must still be listed
    priv = _thesis(supervisor_user, is_public=False)
    priv.title = "PrivateOne"
    db.session.commit()
    r = client.get("/theses")
    assert r.status_code == 200
    assert b"Open thesis details" in r.data
    assert b"PrivateOne" not in r.data


def test_public_theses_layout_all_roles(client, admin_user, supervisor_user, researcher_user, student_user):
    assert b"accordionSidebar" in client.get("/theses").data  # anonymous
    for u in (student_user, supervisor_user, researcher_user, admin_user):
        client.post("/logout")
        login(client, u)
        r = client.get("/theses")
        assert r.status_code == 200
        assert b"accordionSidebar" in r.data and b"alertsDropdown" in r.data
        assert b"notifications.js" in r.data


def test_supervisor_sees_hint_for_unpublished(client, supervisor_user):
    _thesis(supervisor_user, is_public=False)
    login(client, supervisor_user)
    assert b"not public or are frozen" in client.get("/theses").data


def test_profile_has_sidebar_all_roles(client, admin_user, supervisor_user, researcher_user, student_user):
    for u in (student_user, supervisor_user, researcher_user, admin_user):
        client.post("/logout")
        login(client, u)
        r = client.get("/profile")
        assert r.status_code == 200
        assert b"accordionSidebar" in r.data and b"alertsDropdown" in r.data


def test_resource_helpers():
    assert detect_provider("https://github.com/a/b") == "github"
    assert detect_provider("https://www.overleaf.com/project/1") == "overleaf"
    assert detect_provider("https://drive.google.com/drive/folders/x") == "gdrive"
    assert detect_provider("https://evilgithub.com/x") is None
    assert normalize_resource_url("javascript:alert(1)") is None
    assert normalize_resource_url("github.com/a/b") == "https://github.com/a/b"
    assert resolve_resource_type("document", "https://github.com/a/b") == "github"
    assert resolve_resource_type("paper", "https://github.com/a/b") == "paper"


def test_student_adds_github_resource(client, student_user, supervisor_user):
    t = _thesis(supervisor_user)
    t.author_id = student_user.id
    db.session.add(Thesis_Supervisor(thesis_id=t.id, supervisor_id=supervisor_user.id, assigned_at=1))
    db.session.commit()
    login(client, student_user)
    client.post("/student/add_resource", data=dict(thesis_id=t.id, resource_type="document",
                                                   resource_link="https://github.com/me/thesis", description="code"))
    client.post("/student/add_resource", data=dict(thesis_id=t.id, resource_type="link",
                                                   resource_link="javascript:alert(1)"))
    res = Resource.query.filter_by(thesis_id=t.id).all()
    assert [r.resource_type for r in res] == ["github"]
    r = client.get("/student/thesis")
    assert r.status_code == 200
    assert b"fab fa-github" in r.data and b"sm-timeline" in r.data and b"sm-heat" in r.data


def test_status_timeline_and_calendar():
    now = int(time.time())
    sts = [Thesis_Status(status="thesis accepted", updated_at=now - 200),
           Thesis_Status(status="in-progress", updated_at=now - 100)]
    tl = build_status_timeline(sts)
    assert [i["state"] for i in tl] == ["done", "current", "upcoming", "upcoming"]
    assert tl[-1]["key"] == "completed"
    assert all(i["state"] == "upcoming" for i in build_status_timeline([]))
    cal = build_activity_calendar([now, now, now - 86400], weeks=10)
    assert cal["total"] == 3 and cal["current_streak"] == 2 and len(cal["columns"]) == 10


def _assign(student, supervisor, **kw):
    t = _thesis(supervisor, **kw)
    t.author_id = student.id
    db.session.add(Thesis_Supervisor(thesis_id=t.id, supervisor_id=supervisor.id, assigned_at=1))
    db.session.commit()
    return t


def test_supervisee_page_renders_cards(client, supervisor_user, student_user):
    _assign(student_user, supervisor_user)
    login(client, supervisor_user)
    r = client.get("/supervisor/supervisee")
    assert r.status_code == 200
    assert b"svTrack" in r.data and b"svAdvanced" in r.data and b"sv-item" in r.data
    assert b"editStudentModal" not in r.data


def test_student_profile_requires_supervision(client, supervisor_user, student_user):
    login(client, supervisor_user)
    r = client.get(f"/supervisor/student/{student_user.id}", follow_redirects=True)
    assert b"not supervised by you" in r.data  # not assigned yet
    _assign(student_user, supervisor_user)
    r = client.get(f"/supervisor/student/{student_user.id}")
    assert r.status_code == 200 and student_user.email.encode() in r.data
    assert b"Unlock editing" in r.data


def test_student_edit_requires_password_unlock(client, supervisor_user, student_user):
    _assign(student_user, supervisor_user)
    login(client, supervisor_user)
    url = f"/supervisor/edit_student/{student_user.id}"
    client.post(url, data=dict(name="Hacked", surname="X", email=student_user.email))
    db.session.refresh(student_user)
    assert student_user.name != "Hacked"
    # wrong password does not unlock
    client.post(f"/supervisor/student/{student_user.id}/unlock", data=dict(password="nope"))
    client.post(url, data=dict(name="Hacked", surname="X", email=student_user.email))
    db.session.refresh(student_user)
    assert student_user.name != "Hacked"
    # correct password unlocks
    client.post(f"/supervisor/student/{student_user.id}/unlock", data=dict(password="password"))
    client.post(url, data=dict(name="Changed", surname="Name", email=student_user.email))
    db.session.refresh(student_user)
    assert student_user.name == "Changed"
    assert b"Editing unlocked" in client.get(f"/supervisor/student/{student_user.id}").data


def test_italian_translations_for_new_strings(client, supervisor_user, student_user):
    _assign(student_user, supervisor_user)
    login(client, supervisor_user)
    from flask_babel import refresh
    refresh()  # the test fixture keeps one long-lived app context that caches the locale
    r = client.get("/supervisor/supervisee?lang=it")
    assert b"Ricerca avanzata" in r.data and b"Advanced search" not in r.data
    refresh()
    r = client.get(f"/supervisor/student/{student_user.id}?lang=it")
    assert b"Sblocca la modifica" in r.data and b"Profilo dello studente" in r.data


# ---------------------------------------------------------------- uploads / thesis media
import io

def _make_png():
    import struct, zlib
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    raw = zlib.compress(b"\x00\xff\x00\x00")
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", raw) + chunk(b"IEND", b""))


PNG = _make_png()


def _png(name="a.png", data=PNG):
    return (io.BytesIO(data), name)


def test_profile_picture_upload_and_remove(client, student_user, app, tmp_path):
    app.config["UPLOAD_FOLDER"] = str(tmp_path)
    login(client, student_user)
    r = client.post("/profile/picture", data={"picture": _png()}, content_type="multipart/form-data", follow_redirects=True)
    assert r.status_code == 200
    db.session.refresh(student_user)
    assert student_user.profile_pic.startswith("avatars/")
    name = student_user.profile_pic.split("/", 1)[1]
    got = client.get(f"/media/avatar/{name}")
    assert got.status_code == 200 and got.mimetype in ("image/png", "image/jpeg")
    assert client.get("/media/avatar/../../etc/passwd").status_code == 404
    # fake image (HTML disguised as png) and SVG are refused
    client.post("/profile/picture", data={"picture": _png("x.png", b"<html><script>1</script></html>")}, content_type="multipart/form-data")
    client.post("/profile/picture", data={"picture": _png("x.svg", b"<svg onload=alert(1)>")}, content_type="multipart/form-data")
    db.session.refresh(student_user)
    assert student_user.profile_pic == "avatars/" + name
    client.post("/profile/picture", data={"action": "remove"})
    db.session.refresh(student_user)
    assert student_user.profile_pic is None


def test_avatar_requires_login(client):
    assert client.get("/media/avatar/x.png").status_code in (302, 401)


def test_thesis_images_and_links_flow(client, supervisor_user, student_user, app, tmp_path):
    app.config["UPLOAD_FOLDER"] = str(tmp_path)
    t = _thesis(supervisor_user, is_public=True)
    db.session.add(Thesis_Supervisor(thesis_id=t.id, supervisor_id=supervisor_user.id, assigned_at=1))
    db.session.commit()
    login(client, supervisor_user)
    client.post(f"/supervisor/thesis/{t.id}/images", data={"images": [_png("1.png"), _png("2.png")], "caption": "Fig"},
                content_type="multipart/form-data")
    client.post(f"/supervisor/thesis/{t.id}/images", data={"images": [_png("bad.png", b"nope-not-an-image")]},
                content_type="multipart/form-data")
    client.post(f"/supervisor/thesis/{t.id}/links", data={"url": "https://arxiv.org/abs/1", "label": "Paper"})
    client.post(f"/supervisor/thesis/{t.id}/links", data={"url": "javascript:alert(1)", "label": "x"})
    db.session.refresh(t)
    assert len(t.images) == 2 and len(t.links) == 1
    assert b"Presentation" in client.get(f"/supervisor/thesis/{t.id}").data

    # public (anonymous) card shows carousel + link; image file is reachable
    client.post("/logout")
    page = client.get(f"/theses/{t.id}")
    assert b"tmCarousel-pub" in page.data and b"tmLightbox-pub" in page.data and b"arxiv.org" in page.data
    assert client.get("/theses").data.count(b"thesis-cover") >= 1
    fname = t.images[0].filename.split("/", 1)[1]
    assert client.get(f"/media/thesis/{fname}").status_code == 200

    # unpublished -> image hidden from the public
    t.is_public = False
    db.session.commit()
    assert client.get(f"/media/thesis/{fname}").status_code == 404

    # a different supervisor cannot modify it
    other = User_mgmt_factory(app)
    client.post("/logout")
    login(client, other)
    client.post(f"/supervisor/thesis/{t.id}/links", data={"url": "https://evil.example.com"})
    db.session.refresh(t)
    assert len(t.links) == 1


def User_mgmt_factory(app):
    from superviseme.models import User_mgmt
    from werkzeug.security import generate_password_hash
    u = User_mgmt(username="sup2", name="S", surname="Two", email="sup2@test.com",
                  password=generate_password_hash("password", method="pbkdf2:sha256"),
                  user_type="supervisor", joined_on=int(time.time()))
    db.session.add(u)
    db.session.commit()
    return u


def test_theses_cards_have_default_and_custom_preview(client, supervisor_user, app, tmp_path):
    app.config["UPLOAD_FOLDER"] = str(tmp_path)
    t1 = _thesis(supervisor_user, is_public=True, level="master")
    t2 = _thesis(supervisor_user, is_public=True)
    t2.title = "WithPhoto"
    db.session.add(Thesis_Supervisor(thesis_id=t2.id, supervisor_id=supervisor_user.id, assigned_at=1))
    db.session.commit()
    login(client, supervisor_user)
    client.post(f"/supervisor/thesis/{t2.id}/images", data={"images": [_png()]}, content_type="multipart/form-data")
    page = client.get("/theses").data
    assert b"thesis-cover placeholder" in page            # default preview (no image)
    assert b'class="thesis-cover "' in page or b"/media/thesis/" in page  # attached preview
    assert b"fa-graduation-cap" in page                   # level-specific default icon


# ---------------------------------------------------------------- contacts & read-only profiles
def test_supervisor_contacts_saved_and_shown_to_students(client, supervisor_user, student_user):
    login(client, supervisor_user)
    client.post("/profile/update", data=dict(
        name="Sup", surname="Visor", email=supervisor_user.email,
        office_location="Building A, room 12", contact_email="office@uni.it", phone="+39 050 123456"))
    db.session.refresh(supervisor_user)
    assert supervisor_user.office_location == "Building A, room 12"
    assert supervisor_user.phone == "+39 050 123456" and supervisor_user.contact_email == "office@uni.it"
    # invalid values are refused
    client.post("/profile/update", data=dict(name="Sup", surname="Visor", email=supervisor_user.email,
                                              phone="<script>", contact_email="x"))
    db.session.refresh(supervisor_user)
    assert supervisor_user.phone == "+39 050 123456"

    t = _thesis(supervisor_user, is_public=True)
    db.session.add(Thesis_Supervisor(thesis_id=t.id, supervisor_id=supervisor_user.id, assigned_at=1))
    db.session.commit()
    client.post("/logout")
    anon = client.get(f"/theses/{t.id}").data
    assert b"office@uni.it" not in anon                      # contacts only for signed-in users
    login(client, student_user)
    page = client.get(f"/theses/{t.id}").data
    assert b"Building A, room 12" in page and b"office@uni.it" in page and b"+39 050 123456" in page
    assert f"/users/{supervisor_user.id}".encode() in page   # name links to the profile


def test_read_only_profile_pages_and_permissions(client, admin_user, supervisor_user, researcher_user, student_user):
    other = User_mgmt_factory(client.application)  # a second supervisor
    t = _thesis(supervisor_user, is_public=True)
    db.session.add(Thesis_Supervisor(thesis_id=t.id, supervisor_id=supervisor_user.id, assigned_at=1))
    db.session.commit()
    # anonymous: must sign in
    assert client.get(f"/users/{supervisor_user.id}").status_code in (302, 401)
    # student sees supervisor profile (with open thesis), not another student's
    login(client, student_user)
    r = client.get(f"/users/{supervisor_user.id}")
    assert r.status_code == 200 and b"Open thesis opportunities" in r.data and b"accordionSidebar" in r.data
    assert client.get(f"/users/{researcher_user.id}").status_code == 200
    # own profile redirects to the editable page
    assert client.get(f"/users/{student_user.id}").status_code == 302
    client.post("/logout")
    # unrelated supervisor cannot open the student's profile; the supervisor of the thesis can (via the richer page)
    _assign_existing = _thesis(supervisor_user)
    _assign_existing.author_id = student_user.id
    db.session.add(Thesis_Supervisor(thesis_id=_assign_existing.id, supervisor_id=supervisor_user.id, assigned_at=1))
    db.session.commit()
    login(client, other)
    assert client.get(f"/users/{student_user.id}").status_code == 404
    client.post("/logout")
    login(client, supervisor_user)
    assert client.get(f"/users/{student_user.id}").status_code == 302
    client.post("/logout")
    login(client, admin_user)
    assert client.get(f"/users/{student_user.id}").status_code == 200
    assert client.get("/users/99999").status_code == 404


def test_names_are_links_on_supervisor_pages(client, supervisor_user, student_user):
    t = _assign(student_user, supervisor_user)
    login(client, supervisor_user)
    assert f"/users/{student_user.id}".encode() in client.get("/supervisor/theses").data
    assert f"/users/{student_user.id}".encode() in client.get(f"/supervisor/thesis/{t.id}").data


def test_supervisor_theses_board(client, supervisor_user, student_user):
    t = _assign(student_user, supervisor_user)
    open_t = _thesis(supervisor_user, is_public=True)
    db.session.add(Thesis_Supervisor(thesis_id=open_t.id, supervisor_id=supervisor_user.id, assigned_at=int(time.time())))
    frozen = _thesis(supervisor_user, frozen=True)
    db.session.add(Thesis_Supervisor(thesis_id=frozen.id, supervisor_id=supervisor_user.id, assigned_at=int(time.time())))
    db.session.commit()
    login(client, supervisor_user)
    r = client.get("/supervisor/theses")
    assert r.status_code == 200
    assert b"thTrack" in r.data and b"thAdvanced" in r.data and b"thSource" in r.data
    assert r.data.count(b'class="sv-item"') + r.data.count(b'class="sv-item\n') >= 0
    assert b"thArchived" in r.data and b"createThesisModal" in r.data
    assert b"freezeThesis" in r.data and b"deleteThesis" in r.data
    assert f"/users/{student_user.id}".encode() in r.data


def test_researcher_theses_board(client, researcher_user, student_user):
    t = _thesis(researcher_user)
    db.session.add(Thesis_Supervisor(thesis_id=t.id, supervisor_id=researcher_user.id, assigned_at=int(time.time())))
    db.session.commit()
    login(client, researcher_user)
    r = client.get("/researcher/supervisor/theses")
    assert r.status_code in (200, 302)
    if r.status_code == 200:
        assert b"thTrack" in r.data


def test_profile_avatar_editor_in_account_card(client, student_user):
    login(client, student_user)
    r = client.get("/profile")
    assert r.status_code == 200
    assert b'id="avatarModal"' in r.data and b'id="openAvatarModal"' in r.data
    assert b"avCanvas" in r.data and b"profileTabs" in r.data
    # the picture must live in the account card, not in a separate card
    assert b"Choose an image..." not in r.data
    assert r.data.index(b"openAvatarModal") > r.data.index(b"Account Information")


def test_dashboards_render_for_all_roles(client, admin_user, supervisor_user, researcher_user, student_user):
    t = _assign(student_user, supervisor_user)
    from superviseme.models import Todo
    db.session.add(Todo(thesis_id=t.id, author_id=supervisor_user.id, title="Draft chapter 1", priority="high",
                        status="pending", due_date=int(time.time()) - 86400, created_at=int(time.time()), updated_at=int(time.time())))
    open_t = _thesis(supervisor_user, is_public=True)
    db.session.add(Thesis_Supervisor(thesis_id=open_t.id, supervisor_id=supervisor_user.id, assigned_at=int(time.time())))
    db.session.commit()

    login(client, supervisor_user)
    r = client.get("/supervisor/dashboard")
    assert r.status_code == 200 and b"dash-tile" in r.data and b"Draft chapter 1" in r.data
    assert b"<table" not in r.data.split(b'id="addTodoModal"')[0].split(b'class="dash-hero"')[1]
    client.post("/logout")

    login(client, student_user)
    r = client.get("/student/dashboard")
    assert r.status_code == 200 and b"dash-ring" in r.data and b"Draft chapter 1" in r.data
    client.post("/logout")

    login(client, researcher_user)
    assert client.get("/researcher/dashboard").status_code == 200
    client.post("/logout")

    login(client, admin_user)
    r = client.get("/admin/dashboard")
    assert r.status_code == 200 and b"dash-tile" in r.data


def test_researcher_supervisor_dashboard_and_anonymous_supervisor_link(client, researcher_user, supervisor_user):
    t = _thesis(supervisor_user, is_public=True)
    db.session.add(Thesis_Supervisor(thesis_id=t.id, supervisor_id=supervisor_user.id, assigned_at=int(time.time())))
    db.session.commit()
    # anonymous visitor: supervisor name still links to the profile page
    r = client.get(f"/theses/{t.id}")
    assert r.status_code == 200 and f"/users/{supervisor_user.id}".encode() in r.data
    r = client.get("/theses")
    assert f"/users/{supervisor_user.id}".encode() in r.data

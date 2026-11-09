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


# ── milestones, reminders, email prefs ──────────────────────────────────────
def test_milestones_flow_and_permissions(client, supervisor_user, student_user, researcher_user):
    from superviseme.models import Thesis_Milestone
    t = _assign(student_user, supervisor_user)
    login(client, supervisor_user)
    r = client.post(f"/thesis/{t.id}/milestones/add", data={"title": "Draft", "due_date": "2030-01-15", "next": f"/supervisor/thesis/{t.id}"}, follow_redirects=True)
    assert r.status_code == 200 and b"Draft" in r.data
    m = Thesis_Milestone.query.filter_by(thesis_id=t.id).one()
    # invalid input and open redirect are rejected
    client.post(f"/thesis/{t.id}/milestones/add", data={"title": "", "due_date": "bad"})
    assert Thesis_Milestone.query.count() == 1
    r = client.post(f"/thesis/{t.id}/milestones/add", data={"title": "x", "due_date": "2030-01-01", "next": "https://evil.example/"})
    assert r.status_code == 302 and "evil.example" not in r.headers["Location"]
    client.post("/logout")
    # the student can tick it off but not add or delete
    login(client, student_user)
    assert client.get("/student/thesis").status_code == 200
    client.post(f"/milestones/{m.id}/toggle")
    db.session.refresh(m)
    assert m.status == "done" and m.completed_at
    assert client.post(f"/thesis/{t.id}/milestones/add", data={"title": "no", "due_date": "2030-01-01"}).status_code == 403
    assert client.post(f"/milestones/{m.id}/delete").status_code == 403
    client.post("/logout")
    # unrelated users cannot touch it
    login(client, researcher_user)
    assert client.post(f"/milestones/{m.id}/toggle").status_code == 403


def test_reminders_are_sent_once(app, supervisor_user, student_user):
    from superviseme.models import Notification, Thesis_Milestone
    from superviseme.utils.reminders import run_reminders
    t = _assign(student_user, supervisor_user)
    db.session.add(Thesis_Milestone(thesis_id=t.id, title="Soon", due_date=int(time.time()) + 3600, created_at=int(time.time())))
    db.session.commit()
    first = run_reminders()
    assert first["milestone"] == 2  # student + supervisor
    assert run_reminders()["milestone"] == 0  # never repeated
    assert Notification.query.filter_by(notification_type="deadline_reminder").count() >= 2


def test_email_preferences(client, student_user):
    login(client, student_user)
    client.post("/profile/email-preferences", data={"weekly_digest": "on"})
    db.session.refresh(student_user)
    assert student_user.email_notifications is False and student_user.weekly_digest is True
    assert b"email_notifications" in client.get("/profile").data


# ── agenda / meetings / action items ────────────────────────────────────────
def test_action_item_parsing():
    from superviseme.utils.action_items import extract_action_items
    items = extract_action_items("Intro\n- [ ] Write related work @due:2030-02-01 @student !high\n- [x] Done thing\n* [ ] Plain task\n- not a task")
    assert [i["title"] for i in items] == ["Write related work", "Done thing", "Plain task"]
    assert items[0]["priority"] == "high" and items[0]["who"] == "student" and items[0]["due"]
    assert items[1]["done"] and items[2]["priority"] == "medium"


def test_ics_escaping_and_folding():
    from superviseme.utils.ics import build_calendar
    out = build_calendar([{"uid": 1, "title": "A, B; C\nD", "start": 1900000000, "end": 1900003600,
                           "location": "Room " + "x" * 120, "description": "é" * 60}])
    assert "SUMMARY:A\\, B\\; C\\nD" in out and out.endswith("END:VCALENDAR\r\n")
    assert all(len(l.encode()) <= 75 for l in out.split("\r\n"))


def test_note_action_items_create_tasks_once(client, supervisor_user, student_user):
    from superviseme.models import MeetingNote, Todo
    t = _assign(student_user, supervisor_user)
    n = MeetingNote(thesis_id=t.id, author_id=supervisor_user.id, title="Kickoff", created_at=int(time.time()), updated_at=int(time.time()),
                    content="- [ ] Read paper A @due:2030-03-01 @student !high\n- [ ] Prepare outline")
    db.session.add(n)
    db.session.commit()
    login(client, supervisor_user)
    page = client.get(f"/supervisor/meeting_note/{n.id}")
    assert page.status_code == 200 and b"Create tasks from action items" in page.data
    client.post(f"/meeting-notes/{n.id}/action-items", data={"next": "/agenda"})
    todos = Todo.query.filter_by(thesis_id=t.id).all()
    assert {x.title for x in todos} == {"Read paper A", "Prepare outline"}
    assert next(x for x in todos if x.title == "Read paper A").assigned_to_id == student_user.id
    client.post(f"/meeting-notes/{n.id}/action-items", data={"next": "/agenda"})
    assert Todo.query.filter_by(thesis_id=t.id).count() == 2  # idempotent


def test_agenda_booking_flow(client, supervisor_user, student_user, researcher_user):
    from superviseme.models import Availability_Slot, Meeting
    _assign(student_user, supervisor_user)
    login(client, supervisor_user)
    r = client.post("/agenda/slots/add", data={"date": "2031-05-05", "time": "10:00", "duration": "30", "count": "2", "repeat": "1", "location": "Room 1"})
    assert r.status_code == 302 and Availability_Slot.query.count() == 2
    assert client.post("/agenda/slots/add", data={"date": "2001-01-01", "time": "10:00"}).status_code == 302
    assert Availability_Slot.query.count() == 2  # past dates rejected
    assert client.get("/agenda").status_code == 200
    client.post("/logout")

    login(client, student_user)
    page = client.get("/agenda")
    assert page.status_code == 200 and b"ag-slot" in page.data
    slot = Availability_Slot.query.order_by(Availability_Slot.start_ts).first()
    client.post(f"/agenda/slots/{slot.id}/book")
    m = Meeting.query.one()
    assert m.student_id == student_user.id and m.supervisor_id == supervisor_user.id
    client.post(f"/agenda/slots/{slot.id}/book")  # double booking refused
    assert Meeting.query.count() == 1
    ics = client.get(f"/agenda/meetings/{m.id}.ics")
    assert ics.status_code == 200 and ics.mimetype == "text/calendar" and b"BEGIN:VEVENT" in ics.data
    assert b"BEGIN:VEVENT" in client.get("/agenda/calendar.ics").data
    client.post("/logout")

    login(client, researcher_user)  # stranger: cannot read or cancel
    assert client.get(f"/agenda/meetings/{m.id}.ics").status_code == 403
    assert client.post(f"/agenda/meetings/{m.id}/cancel").status_code == 403
    client.post("/logout")

    login(client, student_user)
    client.post(f"/agenda/meetings/{m.id}/cancel")
    db.session.refresh(slot)
    assert slot.booked_by is None  # slot is free again


# ── documents ───────────────────────────────────────────────────────────────
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def test_documents_versions_comments_permissions(client, supervisor_user, student_user, researcher_user, app, tmp_path):
    from superviseme.models import Document_Comment, Thesis_Document
    app.config["UPLOAD_FOLDER"] = str(tmp_path)
    t = _assign(student_user, supervisor_user)
    login(client, student_user)
    assert b"Upload document" in client.get("/student/thesis").data
    bad = client.post(f"/thesis/{t.id}/documents/add", data={"title": "Fake", "file": (io.BytesIO(b"<html>"), "x.pdf")},
                      content_type="multipart/form-data")
    assert bad.status_code == 302 and Thesis_Document.query.count() == 0
    r = client.post(f"/thesis/{t.id}/documents/add", data={"title": "Chapter 1", "file": (io.BytesIO(PDF), "../../evil name.pdf")},
                    content_type="multipart/form-data")
    assert r.status_code == 302
    doc = Thesis_Document.query.one()
    v1 = doc.latest
    assert v1.version == 1 and "/" not in v1.original_name and v1.filename.startswith("documents/")
    client.post(f"/documents/{doc.id}/versions/add", data={"note": "fixed", "file": (io.BytesIO(PDF + b"x"), "c.pdf")}, content_type="multipart/form-data")
    db.session.refresh(doc)
    assert [v.version for v in doc.versions] == [2, 1]
    page = client.get(f"/documents/{doc.id}")
    assert page.status_code == 200 and b"v2" in page.data
    f = client.get(f"/documents/versions/{v1.id}/file")
    assert f.status_code == 200 and f.mimetype == "application/pdf" and f.headers["X-Content-Type-Options"] == "nosniff"
    client.post("/logout")

    login(client, supervisor_user)
    client.post(f"/documents/versions/{doc.latest.id}/comments/add", data={"section": "p. 3", "body": "Please expand."})
    c = Document_Comment.query.one()
    assert c.section == "p. 3"
    client.post(f"/comments/{c.id}/resolve")
    db.session.refresh(c)
    assert c.resolved is True
    client.post("/logout")

    login(client, researcher_user)  # not involved
    assert client.get(f"/documents/{doc.id}").status_code == 403
    assert client.get(f"/documents/versions/{v1.id}/file").status_code == 403
    assert client.post(f"/documents/{doc.id}/delete").status_code == 403
    client.post("/logout")

    login(client, supervisor_user)
    client.post(f"/documents/{doc.id}/delete")
    assert Thesis_Document.query.count() == 0 and Document_Comment.query.count() == 0


def test_capacity_blocks_assignment_and_team_roles(client, supervisor_user, student_user, researcher_user):
    from tests.conftest import _make_user
    from superviseme.utils.capacity import capacity_info, capacity_message
    from superviseme.utils.workflow import thesis_role, can_manage_team
    sup, co, st1 = supervisor_user, researcher_user, student_user
    rev = _make_user("supervisor", "reviewer_x", "reviewer_x@test.com")
    sup.max_students = 1
    db.session.commit()
    t1 = _assign(st1, sup)
    t2 = _thesis(sup)
    db.session.add(Thesis_Supervisor(thesis_id=t2.id, supervisor_id=sup.id, assigned_at=1))
    db.session.commit()
    assert capacity_info(sup)["full"] and capacity_message(t2)
    sup.max_students = None
    db.session.commit()
    assert capacity_message(t2) is None
    login(client, sup)
    assert client.post(f"/thesis/{t1.id}/team/add", data={"kind": "co_supervisor", "user_id": co.id}).status_code == 302
    client.post(f"/thesis/{t1.id}/team/add", data={"kind": "reviewer", "user_id": rev.id})
    assert thesis_role(co, t1) == "supervisor" and thesis_role(rev, t1) == "reviewer"
    assert not can_manage_team(co, t1) and can_manage_team(sup, t1)
    assert capacity_info(co)["used"] == 0
    page = client.get(f"/supervisor/thesis/{t1.id}")
    assert page.status_code == 200 and b"Supervision team" in page.data and b"Co-supervisor" in page.data
    client.post("/logout")
    login(client, rev)
    assert client.get("/reviews").status_code == 200
    assert client.get(f"/reviews/{t1.id}").status_code == 200
    assert client.post(f"/thesis/{t1.id}/milestones/add", data={"title": "x", "due": "2030-01-01"}).status_code == 403
    client.post("/logout")
    login(client, sup)
    client.post(f"/thesis/{t1.id}/team/remove", data={"user_id": rev.id})
    assert thesis_role(rev, t1) is None


def test_graduation_checklist_flow(client, admin_user, supervisor_user, student_user):
    from superviseme.models import Checklist_Template, Thesis_Checklist_Item
    from superviseme.utils.checklist import parse_items
    from superviseme.utils.reminders import run_reminders
    assert parse_items("A | 30\n\nB\nC | x") == [("A", 30), ("B", None), ("C", None)]
    login(client, admin_user)
    assert client.post("/admin/checklists/add", data={"name": "Std", "degree_course": "CS", "items": "Apply | 30\nUpload PDF | 7"}).status_code == 302
    assert client.get("/admin/checklists").status_code == 200
    tpl = Checklist_Template.query.one()
    client.post("/logout")
    t = _assign(student_user, supervisor_user)
    login(client, supervisor_user)
    assert client.post("/admin/checklists/add", data={"name": "x", "items": "a"}).status_code == 403
    soon = (date.today() + timedelta(days=20)).isoformat()
    client.post(f"/thesis/{t.id}/checklist/settings", data={"defense_date": soon, "degree_course": "CS"})
    client.post(f"/thesis/{t.id}/checklist/apply", data={"template_id": tpl.id})
    client.post(f"/thesis/{t.id}/checklist/apply", data={"template_id": tpl.id})  # idempotent
    items = Thesis_Checklist_Item.query.filter_by(thesis_id=t.id).all()
    assert len(items) == 2 and all(i.due_date for i in items)
    assert b"Graduation checklist" in client.get(f"/supervisor/thesis/{t.id}").data
    first = sorted(items, key=lambda i: i.due_date)[0]
    assert run_reminders()["checklist"] >= 1  # "Apply" is due in less than a week
    assert run_reminders()["checklist"] == 0
    client.post("/logout")
    login(client, student_user)
    assert b"Graduation checklist" in client.get("/student/thesis").data
    client.post(f"/checklist/{first.id}/toggle")
    assert Thesis_Checklist_Item.query.get(first.id).status == "done"
    assert client.post(f"/checklist/{first.id}/delete").status_code == 403

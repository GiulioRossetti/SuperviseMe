import os
import time

import pytest


def _login(client, email):
    from superviseme.models import User_mgmt
    from tests.test_ui_pages import login
    client.post("/logout")
    login(client, User_mgmt.query.filter_by(email=email).one())


@pytest.fixture
def dirs(app, tmp_path, monkeypatch):
    app.config["BACKUP_DIR"] = str(tmp_path / "backups")
    app.config["UPLOAD_FOLDER"] = str(tmp_path / "uploads")
    os.makedirs(app.config["UPLOAD_FOLDER"] + "/avatars")
    with open(app.config["UPLOAD_FOLDER"] + "/avatars/a.png", "wb") as f:
        f.write(b"orig-bytes")
    return tmp_path


def test_backup_roundtrip_restores_data_and_uploads(client, app, dirs, admin_user, researcher_user):
    from superviseme import db
    from superviseme.models import ResearchProject, ResearchProject_Software
    from superviseme.utils import backup as bk
    now = int(time.time())
    p = ResearchProject(title="Before", description="d", researcher_id=researcher_user.id, created_at=now)
    db.session.add(p); db.session.commit()
    db.session.add(ResearchProject_Software(project_id=p.id, title="keepme", created_at=now)); db.session.commit()
    name = bk.create_backup("manual", note="first")
    info = [b for b in bk.list_backups() if b["name"] == name][0]
    assert info["valid"] and info["rows"] > 2 and info["uploads"] == 1 and info["note"] == "first"
    assert oct(os.stat(os.path.join(bk.backup_dir(), name)).st_mode)[-3:] == "600"
    # change everything after the backup
    ResearchProject_Software.query.delete(); p.title = "After"
    db.session.add(ResearchProject(title="Extra", description="d", researcher_id=researcher_user.id, created_at=now)); db.session.commit()
    with open(app.config["UPLOAD_FOLDER"] + "/avatars/a.png", "wb") as f:
        f.write(b"changed")
    with open(app.config["UPLOAD_FOLDER"] + "/avatars/new.png", "wb") as f:
        f.write(b"new")
    res = bk.restore_backup(bk.backup_path(name))
    assert res["safety"].startswith("pre-restore-") and res["uploads"] == 1
    db.session.expire_all()
    assert ResearchProject.query.filter_by(title="Before").count() == 1 and ResearchProject.query.filter_by(title="Extra").count() == 0
    assert ResearchProject_Software.query.filter_by(title="keepme").count() == 1
    assert open(app.config["UPLOAD_FOLDER"] + "/avatars/a.png", "rb").read() == b"orig-bytes"
    assert not os.path.exists(app.config["UPLOAD_FOLDER"] + "/avatars/new.png")
    # the safety backup holds the pre-restore state and can undo the restore
    bk.restore_backup(bk.backup_path(res["safety"]))
    db.session.expire_all()
    assert ResearchProject.query.filter_by(title="Extra").count() == 1


def test_backup_validation_and_names(app, dirs, tmp_path):
    from superviseme.utils import backup as bk
    for bad in ("../x.zip", "manual-1.zip", "/etc/passwd", "", "manual-20200101-000000.zip"):
        with pytest.raises(bk.BackupError):
            bk.backup_path(bad)
    junk = tmp_path / "junk.zip"
    junk.write_bytes(b"not a zip")
    with pytest.raises(bk.BackupError):
        bk.validate(str(junk))
    name = bk.create_backup("manual")
    import json, zipfile
    src = os.path.join(bk.backup_dir(), name)
    # a backup from another schema revision is refused
    bk_rev = bk.schema_revision
    try:
        bk.schema_revision = lambda: "9999"
        m = bk.read_manifest(src); m["revision"] = "0001"
        forged = tmp_path / "forged.zip"
        with zipfile.ZipFile(src) as zin, zipfile.ZipFile(forged, "w") as zout:
            for it in zin.namelist():
                zout.writestr(it, json.dumps(m) if it == "manifest.json" else zin.read(it))
        with pytest.raises(bk.BackupError, match="schema revision"):
            bk.validate(str(forged))
    finally:
        bk.schema_revision = bk_rev
    # unsafe member names
    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(evil, "w") as zout:
        for it in zin.namelist():
            zout.writestr(it, zin.read(it))
        zout.writestr("uploads/../../escape.txt", "x")
    with pytest.raises(bk.BackupError, match="Unsafe"):
        bk.validate(str(evil))


def test_prune_and_scheduler_job(app, dirs, monkeypatch):
    import superviseme.utils.task_scheduler as ts
    from superviseme.utils import backup as bk
    monkeypatch.setattr(ts, "_flask_app", app)
    monkeypatch.delenv("BACKUP_AUTO", raising=False)
    ts._backup_job()
    assert bk.list_backups() == []
    monkeypatch.setenv("BACKUP_AUTO", "true"); monkeypatch.setenv("BACKUP_KEEP", "2")
    for i in range(4):
        d = bk.backup_dir()
        name = f"auto-2026010{i + 1}-000000.zip"
        import shutil
        shutil.copy(os.path.join(d, bk.create_backup("manual")), os.path.join(d, name))
    manual = [b for b in bk.list_backups() if b["kind"] == "manual"]
    ts._backup_job()
    autos = [b for b in bk.list_backups() if b["kind"] == "auto"]
    assert len(autos) == 2 and len([b for b in bk.list_backups() if b["kind"] == "manual"]) == len(manual)


def test_admin_backup_pages(client, app, dirs, admin_user, researcher_user):
    from superviseme.utils import backup as bk
    _login(client, researcher_user.email)
    assert client.get("/admin/backup").status_code in (302, 403)
    assert client.post("/admin/backup/create").status_code in (302, 403)
    assert bk.list_backups() == []
    _login(client, admin_user.email)
    assert b"Backup and restore" in client.get("/admin/backup").data
    client.post("/admin/backup/create", data={"note": "via ui"})
    (b,) = bk.list_backups()
    page = client.get("/admin/backup").data.decode()
    assert b["name"] in page and "via ui" in page
    dl = client.get(f"/admin/backup/{b['name']}/download")
    assert dl.status_code == 200 and dl.data[:2] == b"PK"
    assert client.get("/admin/backup/..%2Fx.zip/download").status_code == 404
    # restore needs the typed confirmation
    client.post("/admin/backup/restore", data={"name": b["name"]})
    assert len(bk.list_backups()) == 1  # no safety backup was taken: nothing happened
    client.post("/admin/backup/restore", data={"name": b["name"], "confirm": "RESTORE"})
    assert any(x["kind"] == "pre-restore" for x in bk.list_backups())
    assert client.get("/admin/backup").status_code == 302  # restore signs the user out
    _login(client, admin_user.email)
    # upload restore with garbage is rejected gracefully
    import io
    r = client.post("/admin/backup/restore", data={"confirm": "RESTORE", "file": (io.BytesIO(b"nope"), "x.zip")}, content_type="multipart/form-data")
    assert r.status_code == 302
    client.post(f"/admin/backup/{b['name']}/delete")
    assert all(x["name"] != b["name"] for x in bk.list_backups())

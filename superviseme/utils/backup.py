"""Portable backups: every table as JSON lines plus the uploaded files, in one zip.

The dump is database-independent (SQLite and PostgreSQL), so a backup can be restored on either. It is tied to the
schema revision it was taken at: a restore is refused when the application has been migrated since.
Backups contain password hashes and tokens: keep the backup directory private.
"""
import base64
import datetime as _dt
import decimal
import io
import json
import logging
import os
import re
import shutil
import tempfile
import time
import zipfile

from flask import current_app
from sqlalchemy import text

from superviseme import db

logger = logging.getLogger(__name__)
FORMAT = 1
NAME_RE = re.compile(r"^(auto|manual|pre-restore)-\d{8}-\d{6}\.zip$")


class BackupError(ValueError):
    pass


def backup_dir():
    root = current_app.config.get("BACKUP_DIR") or os.environ.get("BACKUP_DIR") or os.path.join(current_app.root_path, "db", "backups")
    os.makedirs(root, exist_ok=True)
    return root


def upload_root():
    from superviseme.utils.uploads import upload_root as _root
    return _root()


def schema_revision():
    try:
        return db.session.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except Exception:
        db.session.rollback()
        return None


# ---- value (de)serialisation ---------------------------------------------------------------------------------

def _encode(v):
    if isinstance(v, _dt.datetime):
        return {"$dt": v.isoformat()}
    if isinstance(v, _dt.date):
        return {"$d": v.isoformat()}
    if isinstance(v, _dt.time):
        return {"$t": v.isoformat()}
    if isinstance(v, (bytes, bytearray, memoryview)):
        return {"$b": base64.b64encode(bytes(v)).decode()}
    if isinstance(v, decimal.Decimal):
        return {"$n": str(v)}
    return v


def _decode(v):
    if isinstance(v, dict) and len(v) == 1:
        (k, x), = v.items()
        if k == "$dt":
            return _dt.datetime.fromisoformat(x)
        if k == "$d":
            return _dt.date.fromisoformat(x)
        if k == "$t":
            return _dt.time.fromisoformat(x)
        if k == "$b":
            return base64.b64decode(x)
        if k == "$n":
            return decimal.Decimal(x)
    return v


def _tables():
    return list(db.metadata.sorted_tables)


# ---- create ---------------------------------------------------------------------------------------------------

def _stamp(now=None):
    return time.strftime("%Y%m%d-%H%M%S", time.gmtime(now or time.time()))


def create_backup(kind="manual", note=None):
    """Write a new backup zip; returns its file name."""
    if kind not in ("auto", "manual", "pre-restore"):
        raise BackupError("unknown backup kind")
    directory = backup_dir()
    name = f"{kind}-{_stamp()}.zip"
    n = 1
    while os.path.exists(os.path.join(directory, name)):
        n += 1
        name = f"{kind}-{_stamp(time.time() + n - 1)}.zip"
    counts = {}
    fd, tmp = tempfile.mkstemp(suffix=".tmp", dir=directory)
    os.close(fd)
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
            for table in _tables():
                pk = list(table.primary_key.columns)
                stmt = table.select().order_by(*pk) if pk else table.select()
                buf, n_rows = io.StringIO(), 0
                for row in db.session.execute(stmt).mappings():
                    buf.write(json.dumps({k: _encode(v) for k, v in row.items()}, ensure_ascii=False) + "\n")
                    n_rows += 1
                z.writestr(f"data/{table.name}.jsonl", buf.getvalue())
                counts[table.name] = n_rows
            root, bdir = os.path.realpath(upload_root()), os.path.realpath(directory)
            files = 0
            for base, dirs, names in os.walk(root):
                if os.path.realpath(base).startswith(bdir):
                    dirs[:] = []
                    continue
                for fn in names:
                    full = os.path.join(base, fn)
                    if os.path.islink(full):
                        continue
                    z.write(full, "uploads/" + os.path.relpath(full, root).replace(os.sep, "/"))
                    files += 1
            manifest = {"format": FORMAT, "created_at": int(time.time()), "kind": kind, "note": (note or "")[:200],
                        "revision": schema_revision(), "dialect": db.engine.dialect.name, "tables": counts, "uploads": files}
            z.writestr("manifest.json", json.dumps(manifest, indent=2))
        os.chmod(tmp, 0o600)
        os.replace(tmp, os.path.join(directory, name))
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return name


def read_manifest(path):
    try:
        with zipfile.ZipFile(path) as z:
            m = json.loads(z.read("manifest.json"))
    except (zipfile.BadZipFile, KeyError, ValueError, OSError):
        raise BackupError("Not a valid SuperviseMe backup")
    if not isinstance(m, dict) or m.get("format") != FORMAT or not isinstance(m.get("tables"), dict):
        raise BackupError("Not a valid SuperviseMe backup")
    return m


def list_backups():
    out = []
    for fn in sorted(os.listdir(backup_dir()), reverse=True):
        if not NAME_RE.match(fn):
            continue
        path = os.path.join(backup_dir(), fn)
        try:
            m = read_manifest(path)
        except BackupError:
            m = {}
        out.append({"name": fn, "size": os.path.getsize(path), "created_at": m.get("created_at") or int(os.path.getmtime(path)),
                    "kind": fn.split("-")[0] if not fn.startswith("pre-restore") else "pre-restore", "revision": m.get("revision"),
                    "note": m.get("note"), "rows": sum((m.get("tables") or {}).values()), "uploads": m.get("uploads"), "valid": bool(m)})
    out.sort(key=lambda b: b["created_at"], reverse=True)
    return out


def backup_path(name):
    """Absolute path of a listed backup; BackupError for anything else (no path traversal possible)."""
    if not NAME_RE.match(name or ""):
        raise BackupError("Unknown backup")
    path = os.path.join(backup_dir(), name)
    if not os.path.isfile(path):
        raise BackupError("Unknown backup")
    return path


def prune_auto(keep):
    """Keep only the newest ``keep`` automatic backups."""
    autos = [b for b in list_backups() if b["kind"] == "auto"]
    for b in autos[max(1, keep):]:
        try:
            os.unlink(os.path.join(backup_dir(), b["name"]))
        except OSError:
            logger.exception("Could not remove old backup %s", b["name"])
    return max(0, len(autos) - max(1, keep))


# ---- restore --------------------------------------------------------------------------------------------------

def _safe_upload_target(root, member):
    rel = member[len("uploads/"):]
    target = os.path.realpath(os.path.join(root, rel))
    if not rel or not target.startswith(os.path.realpath(root) + os.sep):
        return None
    return target


def validate(path):
    """Manifest of a backup that this installation can restore; BackupError otherwise."""
    m = read_manifest(path)
    current = schema_revision()
    if current and m.get("revision") and current != m["revision"]:
        raise BackupError(f"The backup was taken at schema revision {m['revision']} but the application is at {current}: "
                          "restore it on a matching version, or migrate first.")
    known = {t.name for t in _tables()}
    if not set(m["tables"]) & known:
        raise BackupError("The backup contains none of this application's tables")
    with zipfile.ZipFile(path) as z:
        for n in z.namelist():
            if n.startswith("/") or ".." in n.split("/"):
                raise BackupError("Unsafe file name in the backup")
    return m


def _reset_sequences():
    if db.engine.dialect.name != "postgresql":
        return
    for t in _tables():
        pk = list(t.primary_key.columns)
        if len(pk) == 1 and pk[0].name == "id" and pk[0].type.python_type is int:
            db.session.execute(text(
                f"SELECT setval(pg_get_serial_sequence('{t.name}', 'id'), COALESCE((SELECT MAX(id) FROM \"{t.name}\"), 1), "
                f"(SELECT MAX(id) FROM \"{t.name}\") IS NOT NULL)"))


def restore_backup(path):
    """Replace the database content and the uploads with the backup's. A safety backup is taken first.

    Returns {"safety": <file name>, "rows": n, "uploads": n}.
    """
    manifest = validate(path)
    safety = create_backup("pre-restore", note="automatic copy before a restore")
    tables = {t.name: t for t in _tables()}
    names = [t.name for t in _tables() if t.name in manifest["tables"]]
    rows = 0
    try:
        with zipfile.ZipFile(path) as z:
            for name in reversed(names):
                db.session.execute(tables[name].delete())
            for name in names:
                table = tables[name]
                cols = {c.name: c for c in table.columns}
                batch = []
                for line in io.TextIOWrapper(z.open(f"data/{name}.jsonl"), encoding="utf-8"):
                    if not line.strip():
                        continue
                    rec = json.loads(line)
                    batch.append({k: _decode(v) for k, v in rec.items() if k in cols})
                    if len(batch) >= 500:
                        db.session.execute(table.insert(), batch)
                        rows += len(batch)
                        batch = []
                if batch:
                    db.session.execute(table.insert(), batch)
                    rows += len(batch)
            _reset_sequences()
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("Restore failed: the database was left unchanged (safety backup %s)", safety)
        raise BackupError("The restore failed and the database was not changed")
    files = 0
    root = upload_root()
    bdir = os.path.realpath(backup_dir())
    for entry in os.listdir(root):
        full = os.path.join(root, entry)
        if os.path.realpath(full).startswith(bdir):
            continue
        shutil.rmtree(full) if os.path.isdir(full) and not os.path.islink(full) else os.unlink(full)
    with zipfile.ZipFile(path) as z:
        for member in z.namelist():
            if not member.startswith("uploads/") or member.endswith("/"):
                continue
            target = _safe_upload_target(root, member)
            if target is None:
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with z.open(member) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
            files += 1
    return {"safety": safety, "rows": rows, "uploads": files}

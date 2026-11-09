"""Images and external reference links shown on a thesis' public card."""
import time

from flask import flash
from flask_babel import gettext as _

from superviseme import db
from superviseme.models import Thesis_Image, Thesis_Link, Thesis_Supervisor
from superviseme.utils.thesis_resources import normalize_resource_url
from superviseme.utils.uploads import (
    MAX_THESIS_IMAGES, THESIS_IMAGE_MAX_BYTES, UploadError, delete_file, save_image,
)

MAX_LINKS = 20


def user_manages_thesis(user, thesis):
    if not user.is_authenticated:
        return False
    if user.user_type == "admin" or thesis.publisher_id == user.id:
        return True
    return Thesis_Supervisor.query.filter_by(thesis_id=thesis.id, supervisor_id=user.id).first() is not None


def can_view_media(user, thesis):
    """Public (unassigned, published, not frozen) theses are visible to everyone; otherwise only related users."""
    if thesis.is_public and thesis.author_id is None and not thesis.frozen:
        return True
    if not user.is_authenticated:
        return False
    return user_manages_thesis(user, thesis) or thesis.author_id == user.id


def add_images(thesis, files, caption=None):
    """Store uploaded images; returns (added_count, error_messages)."""
    errors, added = [], 0
    existing = len(thesis.images)
    next_pos = max([i.position for i in thesis.images], default=-1) + 1
    for f in files:
        if not f or not f.filename:
            continue
        if existing + added >= MAX_THESIS_IMAGES:
            errors.append(_("At most %(n)d images per thesis.", n=MAX_THESIS_IMAGES))
            break
        try:
            stored = save_image(f, "thesis", THESIS_IMAGE_MAX_BYTES)
        except UploadError as exc:
            errors.append("%s: %s" % (f.filename, exc))
            continue
        db.session.add(Thesis_Image(
            thesis_id=thesis.id, filename=stored, caption=((caption or "").strip()[:200] or None),
            position=next_pos, created_at=int(time.time())))
        next_pos += 1
        added += 1
    db.session.commit()
    return added, errors


def delete_image(thesis, image_id):
    img = Thesis_Image.query.filter_by(id=image_id, thesis_id=thesis.id).first()
    if not img:
        return False
    stored = img.filename
    db.session.delete(img)
    db.session.commit()
    delete_file(stored)
    return True


def add_link(thesis, url, label=None):
    """Returns an error message, or None on success."""
    clean = normalize_resource_url(url, max_len=500)
    if not clean:
        return _("Please provide a valid http(s) link.")
    if len(thesis.links) >= MAX_LINKS:
        return _("At most %(n)d links per thesis.", n=MAX_LINKS)
    db.session.add(Thesis_Link(
        thesis_id=thesis.id, url=clean, label=((label or "").strip()[:200] or None),
        position=max([l.position for l in thesis.links], default=-1) + 1, created_at=int(time.time())))
    db.session.commit()
    return None


def delete_link(thesis, link_id):
    link = Thesis_Link.query.filter_by(id=link_id, thesis_id=thesis.id).first()
    if not link:
        return False
    db.session.delete(link)
    db.session.commit()
    return True


def handle_images_request(thesis, request):
    added, errors = add_images(thesis, request.files.getlist("images"), request.form.get("caption"))
    if added:
        flash(_("%(n)d image(s) added.", n=added))
    for err in errors:
        flash(err)
    if not added and not errors:
        flash(_("No file selected."))


def handle_link_request(thesis, request):
    error = add_link(thesis, request.form.get("url"), request.form.get("label"))
    flash(error or _("Reference link added."))

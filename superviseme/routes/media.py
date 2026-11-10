from flask import Blueprint, abort, send_file
from flask_login import current_user, login_required

from superviseme.models import ResearchProject, ResearchProject_Image, Thesis, Thesis_Image
from superviseme.utils.thesis_media import can_view_media
from superviseme.utils.uploads import ALLOWED, resolve_path

media = Blueprint("media", __name__)


def _serve(relative):
    path = resolve_path(relative)
    if not path:
        abort(404)
    ext = path.rsplit(".", 1)[-1].lower()
    resp = send_file(path, mimetype=ALLOWED.get(ext, "application/octet-stream"), conditional=True, max_age=86400)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Content-Security-Policy"] = "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'"
    return resp


@media.route("/media/avatar/<path:filename>")
@login_required
def avatar(filename):
    return _serve("avatars/" + filename)


@media.route("/media/thesis/<path:filename>")
def thesis_image(filename):
    image = Thesis_Image.query.filter_by(filename="thesis/" + filename).first_or_404()
    thesis = Thesis.query.get_or_404(image.thesis_id)
    if not can_view_media(current_user, thesis):
        abort(404)
    return _serve(image.filename)


@media.route("/media/project/<path:filename>")
@login_required
def project_image(filename):
    from superviseme.utils.projects import user_can_access
    image = ResearchProject_Image.query.filter_by(filename="project/" + filename).first_or_404()
    project = ResearchProject.query.get_or_404(image.project_id)
    if not user_can_access(current_user, project):
        abort(404)
    return _serve(image.filename)

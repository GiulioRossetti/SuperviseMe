"""Safe image upload helpers (avatars and thesis illustrations).

* Only raster formats are accepted (PNG, JPEG, GIF, WEBP): the type is detected from the file's
  magic bytes, never from the client-supplied name/mimetype. SVG is deliberately refused (XSS).
* Files are stored under a persistent directory (``UPLOAD_FOLDER``) with random names.
"""
import os
import secrets

from flask import current_app
from flask_babel import gettext as _

ALLOWED = {"png": "image/png", "jpg": "image/jpeg", "gif": "image/gif", "webp": "image/webp"}
AVATAR_MAX_BYTES = 2 * 1024 * 1024
THESIS_IMAGE_MAX_BYTES = 5 * 1024 * 1024
MAX_THESIS_IMAGES = 10


class UploadError(ValueError):
    pass


def upload_root():
    root = current_app.config.get("UPLOAD_FOLDER") or os.path.join(current_app.root_path, "db", "uploads")
    os.makedirs(root, exist_ok=True)
    return root


def sniff_image_type(head):
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    return None


def save_image(file_storage, subdir, max_bytes, avatar_size=None):
    """Validate and store an uploaded image; return the relative filename (``subdir/name.ext``)."""
    if not file_storage or not getattr(file_storage, "filename", ""):
        raise UploadError(_("No file selected."))
    data = file_storage.read(max_bytes + 1)
    if not data:
        raise UploadError(_("The file is empty."))
    if len(data) > max_bytes:
        raise UploadError(_("The image is too large (max %(mb)d MB).", mb=max_bytes // (1024 * 1024)))
    ext = sniff_image_type(data[:16])
    if not ext:
        raise UploadError(_("Unsupported image format. Use PNG, JPEG, GIF or WEBP."))

    if avatar_size:
        try:  # optional: normalise avatars (square crop, strip metadata) when Pillow is available
            import io
            from PIL import Image, ImageOps
            img = ImageOps.fit(Image.open(io.BytesIO(data)).convert("RGB"), (avatar_size, avatar_size))
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=88)
            data, ext = buf.getvalue(), "jpg"
        except ImportError:
            pass
        except Exception:
            raise UploadError(_("The image could not be processed."))

    folder = os.path.join(upload_root(), subdir)
    os.makedirs(folder, exist_ok=True)
    name = "%s.%s" % (secrets.token_hex(16), ext)
    with open(os.path.join(folder, name), "wb") as fh:
        fh.write(data)
    return "%s/%s" % (subdir, name)


def resolve_path(relative):
    """Absolute path of a stored file, or None if it would escape the upload root."""
    root = os.path.realpath(upload_root())
    path = os.path.realpath(os.path.join(root, relative))
    if not path.startswith(root + os.sep) or not os.path.isfile(path):
        return None
    return path


def delete_file(relative):
    try:
        path = resolve_path(relative)
        if path:
            os.remove(path)
    except OSError:
        pass

"""PDF document storage, version bookkeeping and (optional) text comparison."""
import difflib
import os
import re
import secrets

from flask_babel import gettext as _

from superviseme.utils.uploads import UploadError, upload_root

PDF_MAX_BYTES = 15 * 1024 * 1024
MAX_DOCUMENTS = 30
MAX_VERSIONS = 20


def save_pdf(file_storage):
    """Validate (magic bytes, size) and store a PDF; returns (relative_name, original_name, size)."""
    if not file_storage or not getattr(file_storage, "filename", ""):
        raise UploadError(_("No file selected."))
    data = file_storage.read(PDF_MAX_BYTES + 1)
    if not data:
        raise UploadError(_("The file is empty."))
    if len(data) > PDF_MAX_BYTES:
        raise UploadError(_("The file is too large (max %(mb)d MB).", mb=PDF_MAX_BYTES // (1024 * 1024)))
    if not data.startswith(b"%PDF-"):
        raise UploadError(_("Only PDF files are accepted."))
    folder = os.path.join(upload_root(), "documents")
    os.makedirs(folder, exist_ok=True)
    name = "%s.pdf" % secrets.token_hex(16)
    with open(os.path.join(folder, name), "wb") as fh:
        fh.write(data)
    original = re.sub(r"[^\w.\- ]", "_", os.path.basename(file_storage.filename))[:200] or "document.pdf"
    return "documents/" + name, original, len(data)


def extract_text(path):
    """Text of a PDF via pypdf when installed; None otherwise (comparison then falls back to metadata)."""
    try:
        from pypdf import PdfReader
    except ImportError:
        return None
    try:
        reader = PdfReader(path)
        return "\n".join((page.extract_text() or "") for page in reader.pages[:200])
    except Exception:
        return None


def compare_versions(old_path, new_path, max_lines=60):
    """Line-level diff summary of two PDFs: dict(added, removed, lines) or None when text is unavailable."""
    a, b = extract_text(old_path), extract_text(new_path)
    if a is None or b is None:
        return None
    la = [l.strip() for l in a.splitlines() if l.strip()]
    lb = [l.strip() for l in b.splitlines() if l.strip()]
    lines, added, removed = [], 0, 0
    for l in difflib.unified_diff(la, lb, lineterm="", n=0):
        if l.startswith(("---", "+++", "@@")):
            continue
        if l.startswith("+"):
            added += 1
        elif l.startswith("-"):
            removed += 1
        if len(lines) < max_lines:
            lines.append((l[0], l[1:][:300]))
    return {"added": added, "removed": removed, "lines": lines}

"""Helpers for external resources linked to a thesis (GitHub, Overleaf, Google Drive, ...)."""
import re
from urllib.parse import urlparse

_HOST_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$", re.I)

# key -> (label, font-awesome icon classes, bootstrap colour)
PROVIDERS = {
    "github": ("GitHub", "fab fa-github", "dark"),
    "gitlab": ("GitLab", "fab fa-gitlab", "warning"),
    "overleaf": ("Overleaf", "fas fa-leaf", "success"),
    "gdrive": ("Google Drive", "fab fa-google-drive", "primary"),
    "dropbox": ("Dropbox", "fab fa-dropbox", "info"),
    "onedrive": ("OneDrive", "fas fa-cloud", "primary"),
    "notion": ("Notion", "fas fa-sticky-note", "secondary"),
    "hf": ("Hugging Face", "fas fa-smile", "warning"),
}
GENERIC = {
    "document": ("Document", "fas fa-file-alt", "secondary"),
    "link": ("Link", "fas fa-link", "secondary"),
    "paper": ("Paper", "fas fa-scroll", "secondary"),
    "book": ("Book", "fas fa-book", "secondary"),
    "dataset": ("Dataset", "fas fa-database", "secondary"),
    "tool": ("Tool", "fas fa-wrench", "secondary"),
    "video": ("Video", "fas fa-video", "secondary"),
    "other": ("Other", "fas fa-paperclip", "secondary"),
}
_HOSTS = {
    "github.com": "github", "gitlab.com": "gitlab", "overleaf.com": "overleaf",
    "drive.google.com": "gdrive", "docs.google.com": "gdrive",
    "dropbox.com": "dropbox", "onedrive.live.com": "onedrive", "1drv.ms": "onedrive",
    "sharepoint.com": "onedrive", "notion.so": "notion", "notion.site": "notion",
    "huggingface.co": "hf",
}


def normalize_resource_url(raw, max_len=255):
    """Return a safe http(s) URL or None. Adds https:// when the scheme is missing."""
    url = (raw or "").strip()
    if not url or len(url) > max_len:
        return None
    if "://" not in url:
        url = "https://" + url
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return None
    if not _HOST_RE.match(parsed.hostname):
        return None
    return url


def detect_provider(url):
    host = (urlparse(url or "").hostname or "").lower()
    for domain, key in _HOSTS.items():
        if host == domain or host.endswith("." + domain):
            return key
    return None


def resolve_resource_type(resource_type, url):
    """Auto-detect the provider from the URL when the type is generic/empty."""
    rtype = (resource_type or "").strip().lower()
    detected = detect_provider(url)
    if rtype in PROVIDERS:
        return rtype
    if detected and rtype in ("", "link", "document", "other", "auto"):
        return detected
    return rtype if rtype in GENERIC else "link"


def resource_meta(resource_type):
    key = (resource_type or "").lower()
    return PROVIDERS.get(key) or GENERIC.get(key) or (key.title() or "Link", "fas fa-link", "secondary")


def is_workspace(resource_type):
    return (resource_type or "").lower() in PROVIDERS

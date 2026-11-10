"""Web links (personal site, LinkedIn, ...) shown on user profiles."""
import time
from urllib.parse import urlparse

from flask_babel import gettext as _

from superviseme import db
from superviseme.models import User_Link
from superviseme.utils.thesis_resources import normalize_resource_url

MAX_USER_LINKS = 10

# host suffix -> (label, font-awesome classes)
KNOWN = {
    "linkedin.com": ("LinkedIn", "fab fa-linkedin"),
    "github.com": ("GitHub", "fab fa-github"),
    "gitlab.com": ("GitLab", "fab fa-gitlab"),
    "scholar.google.com": ("Google Scholar", "fas fa-graduation-cap"),
    "orcid.org": ("ORCID", "fab fa-orcid"),
    "researchgate.net": ("ResearchGate", "fab fa-researchgate"),
    "x.com": ("X", "fab fa-x-twitter"),
    "twitter.com": ("Twitter", "fab fa-twitter"),
    "mastodon.social": ("Mastodon", "fab fa-mastodon"),
    "bsky.app": ("Bluesky", "fas fa-cloud"),
    "dblp.org": ("DBLP", "fas fa-book"),
    "youtube.com": ("YouTube", "fab fa-youtube"),
    "semanticscholar.org": ("Semantic Scholar", "fas fa-graduation-cap"),
}


def _host(url):
    host = (urlparse(url or "").hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def link_meta(link):
    """(display label, icon classes) for a stored link."""
    host = _host(link.url)
    for dom, (label, icon) in KNOWN.items():
        if host == dom or host.endswith("." + dom):
            return (link.label or label), icon
    return (link.label or host), "fas fa-globe"


def add_link(user, url, label=None):
    """Returns an error message, or None on success."""
    clean = normalize_resource_url(url, max_len=500)
    if not clean:
        return _("Please provide a valid http(s) link.")
    if len(user.web_links) >= MAX_USER_LINKS:
        return _("At most %(n)d links.", n=MAX_USER_LINKS)
    if any(l.url.rstrip("/") == clean.rstrip("/") for l in user.web_links):
        return _("This link is already in your profile.")
    db.session.add(User_Link(
        user_id=user.id, url=clean, label=((label or "").strip()[:100] or None),
        position=max([l.position for l in user.web_links], default=-1) + 1, created_at=int(time.time())))
    db.session.commit()
    return None


def delete_link(user, link_id):
    link = User_Link.query.filter_by(id=link_id, user_id=user.id).first()
    if not link:
        return False
    db.session.delete(link)
    db.session.commit()
    return True

"""
superviseme/utils/academic_apis.py
------------------------------------
Lightweight wrappers around publicly available academic metadata APIs.

Currently integrated:
  • CrossRef  — https://api.crossref.org  (DOI metadata, citation data)
  • OpenAlex  — https://api.openalex.org  (open scholarly graph, works/authors)

All functions are **best-effort**: they return an empty list / None on any
network or parsing error, so callers never need to guard against exceptions.
Results are plain Python dicts so they can be JSON-serialised directly.

Usage::

    from superviseme.utils.academic_apis import search_crossref, search_openalex, enrich_thesis

    # Find papers matching a query
    papers = search_crossref("graph neural networks thesis supervision")
    works   = search_openalex("federated learning privacy")

    # Try to enrich a thesis with related published works
    enriched = enrich_thesis("Deep Learning for Biomedical Image Segmentation")
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared HTTP helpers
# ---------------------------------------------------------------------------

_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": "SuperviseMe/1.0 (thesis management; contact: admin@superviseme.local)",
})

_DEFAULT_TIMEOUT = 8   # seconds
_CROSSREF_BASE   = "https://api.crossref.org"
_OPENALEX_BASE   = "https://api.openalex.org"

# Simple in-process request cache to avoid hammering APIs during a single
# page render.  Maps (url, frozen_params) → (timestamp, result).
_cache: Dict[tuple, tuple] = {}
_CACHE_TTL = 300  # seconds


def _get(url: str, params: Optional[Dict[str, Any]] = None, timeout: int = _DEFAULT_TIMEOUT) -> Optional[dict]:
    """GET *url* with *params*, return parsed JSON or None on failure.

    Results are cached for _CACHE_TTL seconds.
    """
    cache_key = (url, tuple(sorted((params or {}).items())))
    now = time.monotonic()
    if cache_key in _cache:
        ts, result = _cache[cache_key]
        if now - ts < _CACHE_TTL:
            return result

    try:
        resp = _SESSION.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        result = resp.json()
        _cache[cache_key] = (now, result)
        return result
    except requests.exceptions.RequestException as exc:
        logger.warning("Academic API request failed (%s): %s", url, exc)
        return None


# ---------------------------------------------------------------------------
# CrossRef
# ---------------------------------------------------------------------------

def search_crossref(query: str, rows: int = 5, offset: int = 0) -> List[Dict[str, Any]]:
    """Search CrossRef for works matching *query*.

    Returns a list of simplified work dicts with keys:
        doi, title, authors, year, venue, type, url, abstract (may be absent)

    Args:
        query:  Free-text search string.
        rows:   Maximum number of results to return (1–100).
        offset: Pagination offset.
    """
    rows = max(1, min(100, rows))
    data = _get(
        f"{_CROSSREF_BASE}/works",
        params={
            "query": query,
            "rows": rows,
            "offset": offset,
            "select": "DOI,title,author,published-print,published-online,container-title,type,URL,abstract",
        },
    )
    if not data:
        return []

    items = data.get("message", {}).get("items", [])
    results: List[Dict[str, Any]] = []
    for item in items:
        # Title is a list of strings in CrossRef
        raw_title = item.get("title") or []
        title = raw_title[0] if raw_title else ""

        # Authors
        authors = [
            f"{a.get('given', '')} {a.get('family', '')}".strip()
            for a in (item.get("author") or [])
        ]

        # Published year — prefer print over online
        year: Optional[int] = None
        for date_field in ("published-print", "published-online"):
            dp = (item.get(date_field) or {}).get("date-parts")
            if dp and dp[0]:
                year = dp[0][0]
                break

        # Venue (journal / book title)
        venue_list = item.get("container-title") or []
        venue = venue_list[0] if venue_list else None

        results.append({
            "doi": item.get("DOI"),
            "title": title,
            "authors": authors,
            "year": year,
            "venue": venue,
            "type": item.get("type"),
            "url": item.get("URL") or (f"https://doi.org/{item['DOI']}" if item.get("DOI") else None),
            "abstract": item.get("abstract"),
            "source": "crossref",
        })

    return results


def get_crossref_doi(doi: str) -> Optional[Dict[str, Any]]:
    """Fetch metadata for a single DOI from CrossRef.

    Returns a simplified work dict (same schema as *search_crossref*) or None.
    """
    doi_clean = doi.strip().lstrip("https://doi.org/").lstrip("doi:")
    data = _get(f"{_CROSSREF_BASE}/works/{doi_clean}")
    if not data:
        return None

    item = data.get("message", {})
    raw_title = item.get("title") or []
    title = raw_title[0] if raw_title else ""
    authors = [
        f"{a.get('given', '')} {a.get('family', '')}".strip()
        for a in (item.get("author") or [])
    ]
    year = None
    for date_field in ("published-print", "published-online"):
        dp = (item.get(date_field) or {}).get("date-parts")
        if dp and dp[0]:
            year = dp[0][0]
            break
    venue_list = item.get("container-title") or []
    return {
        "doi": item.get("DOI"),
        "title": title,
        "authors": authors,
        "year": year,
        "venue": venue_list[0] if venue_list else None,
        "type": item.get("type"),
        "url": item.get("URL") or f"https://doi.org/{doi_clean}",
        "abstract": item.get("abstract"),
        "source": "crossref",
    }


# ---------------------------------------------------------------------------
# OpenAlex
# ---------------------------------------------------------------------------

def search_openalex(query: str, per_page: int = 5, page: int = 1) -> List[Dict[str, Any]]:
    """Search OpenAlex for works matching *query*.

    Returns a list of simplified work dicts with keys:
        openalex_id, doi, title, authors, year, venue, cited_by_count, url,
        open_access, abstract_index (inverted index — reconstruct with _reconstruct_abstract)

    Args:
        query:    Free-text search string.
        per_page: Results per page (1–200).
        page:     Page number (1-based).
    """
    per_page = max(1, min(200, per_page))
    data = _get(
        f"{_OPENALEX_BASE}/works",
        params={
            "search": query,
            "per-page": per_page,
            "page": page,
            "select": "id,doi,title,authorships,publication_year,primary_location,cited_by_count,open_access,abstract_inverted_index",
        },
    )
    if not data:
        return []

    results: List[Dict[str, Any]] = []
    for item in (data.get("results") or []):
        # Authors
        authors = [
            a.get("author", {}).get("display_name", "")
            for a in (item.get("authorships") or [])
        ]

        # Venue
        primary = item.get("primary_location") or {}
        source = primary.get("source") or {}
        venue = source.get("display_name")
        landing_url = primary.get("landing_page_url")

        # Abstract reconstruction
        abstract_index = item.get("abstract_inverted_index")
        abstract = _reconstruct_abstract(abstract_index) if abstract_index else None

        doi = (item.get("doi") or "").replace("https://doi.org/", "") or None
        url = landing_url or (f"https://doi.org/{doi}" if doi else item.get("id"))

        results.append({
            "openalex_id": item.get("id"),
            "doi": doi,
            "title": item.get("title"),
            "authors": authors,
            "year": item.get("publication_year"),
            "venue": venue,
            "cited_by_count": item.get("cited_by_count", 0),
            "url": url,
            "open_access": (item.get("open_access") or {}).get("is_oa", False),
            "abstract": abstract,
            "source": "openalex",
        })

    return results


def _reconstruct_abstract(inverted_index: Dict[str, List[int]]) -> str:
    """Reconstruct a plain-text abstract from OpenAlex's inverted index format.

    OpenAlex stores abstracts as ``{word: [position, ...], ...}``; this
    reverses the mapping back to a readable string.
    """
    if not inverted_index:
        return ""
    positions: Dict[int, str] = {}
    for word, pos_list in inverted_index.items():
        for pos in pos_list:
            positions[pos] = word
    return " ".join(positions[p] for p in sorted(positions))


def get_openalex_work(openalex_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a single work from OpenAlex by its OpenAlex ID or DOI.

    *openalex_id* can be an OpenAlex URL (``https://openalex.org/W…``),
    a bare work ID (``W1234567890``), or a DOI (``10.xxxx/xxxx``).
    """
    if openalex_id.startswith("10."):
        # DOI lookup
        url = f"{_OPENALEX_BASE}/works/https://doi.org/{openalex_id}"
    elif openalex_id.startswith("https://openalex.org/"):
        url = f"{_OPENALEX_BASE}/works/{openalex_id.split('/')[-1]}"
    else:
        url = f"{_OPENALEX_BASE}/works/{openalex_id}"

    data = _get(url)
    if not data:
        return None

    authors = [
        a.get("author", {}).get("display_name", "")
        for a in (data.get("authorships") or [])
    ]
    primary = data.get("primary_location") or {}
    source = (primary.get("source") or {})
    abstract_index = data.get("abstract_inverted_index")
    doi = (data.get("doi") or "").replace("https://doi.org/", "") or None
    return {
        "openalex_id": data.get("id"),
        "doi": doi,
        "title": data.get("title"),
        "authors": authors,
        "year": data.get("publication_year"),
        "venue": source.get("display_name"),
        "cited_by_count": data.get("cited_by_count", 0),
        "url": primary.get("landing_page_url") or (f"https://doi.org/{doi}" if doi else data.get("id")),
        "open_access": (data.get("open_access") or {}).get("is_oa", False),
        "abstract": _reconstruct_abstract(abstract_index) if abstract_index else None,
        "source": "openalex",
    }


# ---------------------------------------------------------------------------
# Convenience: enrich a thesis title
# ---------------------------------------------------------------------------

def enrich_thesis(title: str, max_results: int = 3) -> Dict[str, Any]:
    """Find related published works for a thesis *title*.

    Queries both CrossRef and OpenAlex and merges the results, de-duplicated
    by DOI.  Returns a dict::

        {
          "title":    <input title>,
          "crossref": [...],     # up to max_results CrossRef works
          "openalex": [...],     # up to max_results OpenAlex works
          "combined": [...],     # merged list, DOI-deduplicated, sorted by year desc
        }
    """
    crossref_results = search_crossref(title, rows=max_results)
    openalex_results = search_openalex(title, per_page=max_results)

    # Merge and deduplicate by DOI
    seen_dois: set = set()
    combined: List[Dict[str, Any]] = []
    for item in crossref_results + openalex_results:
        doi = item.get("doi")
        if doi and doi in seen_dois:
            continue
        if doi:
            seen_dois.add(doi)
        combined.append(item)

    # Sort by year descending (None last)
    combined.sort(key=lambda x: x.get("year") or 0, reverse=True)

    return {
        "title": title,
        "crossref": crossref_results,
        "openalex": openalex_results,
        "combined": combined,
    }

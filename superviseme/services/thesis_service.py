"""
superviseme/services/thesis_service.py
----------------------------------------
Service layer for thesis-related business logic.

Centralises queries that are duplicated across researcher.py, supervisor.py
and student.py so that routes become thin dispatchers.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import or_

from superviseme import db
from superviseme.models import (
    Thesis,
    Thesis_Supervisor,
    Thesis_Status,
    Thesis_Interest,
    User_mgmt,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pagination default
# ---------------------------------------------------------------------------
DEFAULT_PAGE_SIZE = 20


# ---------------------------------------------------------------------------
# Thesis listing queries
# ---------------------------------------------------------------------------

def get_public_theses(
    page: int = 1,
    per_page: int = DEFAULT_PAGE_SIZE,
    keyword: Optional[str] = None,
    level: Optional[str] = None,
):
    """Return a SQLAlchemy Pagination object of public available theses.

    Parameters
    ----------
    page:      1-based page number.
    per_page:  items per page.
    keyword:   optional free-text filter on title / description / topic.
    level:     optional filter on ``Thesis.level``.
    """
    query = Thesis.query.filter_by(is_public=True, frozen=False)

    if keyword:
        kw = f"%{keyword}%"
        query = query.filter(
            or_(
                Thesis.title.ilike(kw),
                Thesis.description.ilike(kw),
                Thesis.topic.ilike(kw),
            )
        )
    if level:
        query = query.filter(Thesis.level == level)

    return query.order_by(Thesis.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )


def get_supervisor_theses(
    supervisor_id: int,
    page: int = 1,
    per_page: int = DEFAULT_PAGE_SIZE,
):
    """Return paginated theses supervised by *supervisor_id*."""
    query = (
        Thesis.query.join(
            Thesis_Supervisor, Thesis_Supervisor.thesis_id == Thesis.id
        )
        .filter(Thesis_Supervisor.supervisor_id == supervisor_id)
        .order_by(Thesis.created_at.desc())
    )
    return query.paginate(page=page, per_page=per_page, error_out=False)


def get_student_theses(student_id: int):
    """Return all theses where the student is the author (usually 0 or 1)."""
    return Thesis.query.filter_by(author_id=student_id).all()


# ---------------------------------------------------------------------------
# Single-thesis queries
# ---------------------------------------------------------------------------

def get_thesis_or_404(thesis_id: int) -> Thesis:
    """Fetch a thesis by id or abort with 404."""
    from flask import abort
    thesis = Thesis.query.get(thesis_id)
    if thesis is None:
        abort(404)
    return thesis


def assert_supervisor_owns_thesis(supervisor_id: int, thesis_id: int) -> Thesis_Supervisor:
    """Return the Thesis_Supervisor row or abort with 403."""
    from flask import abort
    ts = Thesis_Supervisor.query.filter_by(
        thesis_id=thesis_id, supervisor_id=supervisor_id
    ).first()
    if ts is None:
        logger.warning(
            "403: supervisor %s tried to access thesis %s without ownership",
            supervisor_id,
            thesis_id,
        )
        abort(403)
    return ts


# ---------------------------------------------------------------------------
# Thesis status helpers
# ---------------------------------------------------------------------------

def get_thesis_status(thesis_id: int) -> Optional[Thesis_Status]:
    """Return the most recent status record for a thesis."""
    return (
        Thesis_Status.query.filter_by(thesis_id=thesis_id)
        .order_by(Thesis_Status.updated_at.desc())
        .first()
    )


# ---------------------------------------------------------------------------
# Interest helpers
# ---------------------------------------------------------------------------

def get_pending_interests(thesis_id: int):
    """Return open (pending) interests for a thesis."""
    return Thesis_Interest.query.filter_by(
        thesis_id=thesis_id, status="pending"
    ).all()


def get_student_interest(student_id: int, thesis_id: int) -> Optional[Thesis_Interest]:
    """Return a student's interest record for a given thesis, or None."""
    return Thesis_Interest.query.filter_by(
        student_id=student_id, thesis_id=thesis_id
    ).first()

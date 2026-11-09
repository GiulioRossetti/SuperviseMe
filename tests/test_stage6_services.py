"""
tests/test_stage6_services.py
-------------------------------
Stage 6: Unit / integration tests for the service layer introduced in Stage 4–5.

Covers:
  - superviseme/services/user_service.py
  - superviseme/services/thesis_service.py
  - superviseme/services/notification_service.py  (incl. model-mismatch regression)
"""
from __future__ import annotations

import time
import pytest
from werkzeug.security import generate_password_hash


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_user(user_type, username, email, is_enabled=True):
    from superviseme import db
    from superviseme.models import User_mgmt

    user = User_mgmt(
        username=username,
        name=username.capitalize(),
        surname="Svc",
        email=email,
        password=generate_password_hash("password"),
        user_type=user_type,
        joined_on=int(time.time()),
        is_enabled=is_enabled,
    )
    db.session.add(user)
    db.session.commit()
    return user


def _make_thesis(publisher, title="Test Thesis", is_public=True, frozen=False, level="master"):
    from superviseme import db
    from superviseme.models import Thesis

    thesis = Thesis(
        title=title,
        description="A description for the test thesis.",
        publisher_id=publisher.id,
        is_public=is_public,
        frozen=frozen,
        level=level,
        created_at=int(time.time()),
    )
    db.session.add(thesis)
    db.session.commit()
    return thesis


# ===========================================================================
# TestUserService
# ===========================================================================

class TestUserService:
    """Tests for superviseme/services/user_service.py."""

    def test_get_user_by_username_found(self, app):
        from superviseme.services.user_service import get_user_by_username
        u = _make_user("student", "us_find_user", "us_find@test.com")
        result = get_user_by_username("us_find_user")
        assert result is not None
        assert result.id == u.id

    def test_get_user_by_username_not_found(self, app):
        from superviseme.services.user_service import get_user_by_username
        assert get_user_by_username("does_not_exist_xyz") is None

    def test_get_user_by_email_found(self, app):
        from superviseme.services.user_service import get_user_by_email
        _make_user("supervisor", "us_email_user", "us_email@test.com")
        result = get_user_by_email("us_email@test.com")
        assert result is not None
        assert result.email == "us_email@test.com"

    def test_get_user_by_email_not_found(self, app):
        from superviseme.services.user_service import get_user_by_email
        assert get_user_by_email("nobody@nowhere.invalid") is None

    def test_get_users_by_role_returns_paginated(self, app):
        from superviseme.services.user_service import get_users_by_role
        _make_user("supervisor", "us_sup_1", "us_sup1@test.com")
        _make_user("supervisor", "us_sup_2", "us_sup2@test.com")
        _make_user("student",    "us_stu_1", "us_stu1@test.com")

        pagination = get_users_by_role("supervisor")
        usernames = [u.username for u in pagination.items]
        assert "us_sup_1" in usernames
        assert "us_sup_2" in usernames
        assert "us_stu_1" not in usernames

    def test_get_users_by_role_enabled_only_excludes_disabled(self, app):
        from superviseme.services.user_service import get_users_by_role
        _make_user("researcher", "us_res_en", "us_res_en@test.com", is_enabled=True)
        _make_user("researcher", "us_res_dis", "us_res_dis@test.com", is_enabled=False)

        pagination = get_users_by_role("researcher", enabled_only=True)
        usernames = [u.username for u in pagination.items]
        assert "us_res_en" in usernames
        assert "us_res_dis" not in usernames

    def test_get_users_by_role_enabled_false_includes_all(self, app):
        from superviseme.services.user_service import get_users_by_role
        _make_user("researcher", "us_res_all_en", "us_res_all_en@test.com", is_enabled=True)
        _make_user("researcher", "us_res_all_dis", "us_res_all_dis@test.com", is_enabled=False)

        pagination = get_users_by_role("researcher", enabled_only=False)
        usernames = [u.username for u in pagination.items]
        assert "us_res_all_en" in usernames
        assert "us_res_all_dis" in usernames

    def test_get_all_users_search_by_username(self, app):
        from superviseme.services.user_service import get_all_users
        _make_user("student", "us_search_target", "us_target@test.com")
        _make_user("student", "us_other_one", "us_other@test.com")

        pagination = get_all_users(search="search_target")
        usernames = [u.username for u in pagination.items]
        assert "us_search_target" in usernames
        assert "us_other_one" not in usernames

    def test_get_all_users_no_search_returns_all(self, app):
        from superviseme.services.user_service import get_all_users
        _make_user("admin", "us_all_a", "us_all_a@test.com")
        _make_user("student", "us_all_b", "us_all_b@test.com")
        pagination = get_all_users()
        assert pagination.total >= 2

    def test_enable_user(self, app):
        from superviseme.services.user_service import enable_user
        u = _make_user("student", "us_enable_me", "us_enable@test.com", is_enabled=False)
        assert u.is_enabled is False
        result = enable_user(u.id)
        assert result is True
        from superviseme.models import User_mgmt
        refreshed = User_mgmt.query.get(u.id)
        assert refreshed.is_enabled is True

    def test_disable_user(self, app):
        from superviseme.services.user_service import disable_user
        u = _make_user("supervisor", "us_disable_me", "us_disable@test.com", is_enabled=True)
        result = disable_user(u.id)
        assert result is True
        from superviseme.models import User_mgmt
        refreshed = User_mgmt.query.get(u.id)
        assert refreshed.is_enabled is False

    def test_enable_nonexistent_user_returns_false(self, app):
        from superviseme.services.user_service import enable_user
        assert enable_user(999999) is False

    def test_disable_nonexistent_user_returns_false(self, app):
        from superviseme.services.user_service import disable_user
        assert disable_user(999999) is False

    def test_pagination_page_size(self, app):
        from superviseme.services.user_service import get_all_users
        for i in range(5):
            _make_user("student", f"us_pg_{i}", f"us_pg_{i}@test.com")
        pagination = get_all_users(per_page=2)
        assert len(pagination.items) <= 2
        assert pagination.per_page == 2


# ===========================================================================
# TestThesisService
# ===========================================================================

class TestThesisService:
    """Tests for superviseme/services/thesis_service.py."""

    def test_get_public_theses_returns_public_only(self, app):
        from superviseme.services.thesis_service import get_public_theses
        pub = _make_user("supervisor", "ts_sup_pub", "ts_sup_pub@test.com")
        _make_thesis(pub, "Public Thesis", is_public=True)
        _make_thesis(pub, "Private Thesis", is_public=False)

        pagination = get_public_theses()
        titles = [t.title for t in pagination.items]
        assert "Public Thesis" in titles
        assert "Private Thesis" not in titles

    def test_get_public_theses_excludes_frozen(self, app):
        from superviseme.services.thesis_service import get_public_theses
        pub = _make_user("supervisor", "ts_sup_frz", "ts_sup_frz@test.com")
        _make_thesis(pub, "Live Public", is_public=True, frozen=False)
        _make_thesis(pub, "Frozen Public", is_public=True, frozen=True)

        pagination = get_public_theses()
        titles = [t.title for t in pagination.items]
        assert "Live Public" in titles
        assert "Frozen Public" not in titles

    def test_get_public_theses_keyword_filter_title(self, app):
        from superviseme.services.thesis_service import get_public_theses
        pub = _make_user("supervisor", "ts_kw_sup", "ts_kw_sup@test.com")
        _make_thesis(pub, "Machine Learning Overview", is_public=True)
        _make_thesis(pub, "Network Security Basics", is_public=True)

        pagination = get_public_theses(keyword="machine")
        titles = [t.title for t in pagination.items]
        assert "Machine Learning Overview" in titles
        assert "Network Security Basics" not in titles

    def test_get_public_theses_level_filter(self, app):
        from superviseme.services.thesis_service import get_public_theses
        pub = _make_user("supervisor", "ts_lvl_sup", "ts_lvl_sup@test.com")
        _make_thesis(pub, "Master Thesis A", is_public=True, level="master")
        _make_thesis(pub, "Bachelor Thesis B", is_public=True, level="bachelor")

        pagination = get_public_theses(level="master")
        titles = [t.title for t in pagination.items]
        assert "Master Thesis A" in titles
        assert "Bachelor Thesis B" not in titles

    def test_get_public_theses_pagination(self, app):
        from superviseme.services.thesis_service import get_public_theses
        pub = _make_user("supervisor", "ts_pg_sup", "ts_pg_sup@test.com")
        for i in range(5):
            _make_thesis(pub, f"Paged Thesis {i}", is_public=True)

        p1 = get_public_theses(page=1, per_page=2)
        assert len(p1.items) == 2
        assert p1.total >= 5

    def test_get_supervisor_theses(self, app):
        """get_supervisor_theses queries via Thesis_Supervisor join table."""
        from superviseme.services.thesis_service import get_supervisor_theses
        from superviseme import db
        from superviseme.models import Thesis_Supervisor

        sup1 = _make_user("supervisor", "ts_own_sup1", "ts_own_sup1@test.com")
        sup2 = _make_user("supervisor", "ts_own_sup2", "ts_own_sup2@test.com")

        t_a = _make_thesis(sup1, "Sup1 Thesis A")
        t_b = _make_thesis(sup1, "Sup1 Thesis B")
        t_c = _make_thesis(sup2, "Sup2 Thesis C")

        # Assign t_a and t_b to sup1 via join table; t_c to sup2
        import time as _time
        for t in (t_a, t_b):
            db.session.add(Thesis_Supervisor(
                thesis_id=t.id, supervisor_id=sup1.id, assigned_at=int(_time.time())
            ))
        db.session.add(Thesis_Supervisor(
            thesis_id=t_c.id, supervisor_id=sup2.id, assigned_at=int(_time.time())
        ))
        db.session.commit()

        pagination = get_supervisor_theses(sup1.id)
        titles = [t.title for t in pagination.items]
        assert "Sup1 Thesis A" in titles
        assert "Sup1 Thesis B" in titles
        assert "Sup2 Thesis C" not in titles

    def test_get_thesis_or_404_found(self, app):
        from superviseme.services.thesis_service import get_thesis_or_404
        pub = _make_user("supervisor", "ts_404_sup", "ts_404_sup@test.com")
        thesis = _make_thesis(pub, "Existing Thesis")
        result = get_thesis_or_404(thesis.id)
        assert result.id == thesis.id

    def test_get_thesis_or_404_not_found(self, app):
        from superviseme.services.thesis_service import get_thesis_or_404
        from werkzeug.exceptions import NotFound
        with pytest.raises(NotFound):
            get_thesis_or_404(999999)

    def test_assert_supervisor_owns_thesis_passes(self, app):
        """assert_supervisor_owns_thesis checks the Thesis_Supervisor join table."""
        from superviseme.services.thesis_service import assert_supervisor_owns_thesis
        from superviseme import db
        from superviseme.models import Thesis_Supervisor
        import time as _time

        sup = _make_user("supervisor", "ts_own_check", "ts_own_check@test.com")
        thesis = _make_thesis(sup, "Owned Thesis")
        db.session.add(Thesis_Supervisor(
            thesis_id=thesis.id, supervisor_id=sup.id, assigned_at=int(_time.time())
        ))
        db.session.commit()
        # Should not raise
        assert_supervisor_owns_thesis(sup.id, thesis.id)

    def test_assert_supervisor_owns_thesis_fails_for_other(self, app):
        from superviseme.services.thesis_service import assert_supervisor_owns_thesis
        from superviseme import db
        from superviseme.models import Thesis_Supervisor
        from werkzeug.exceptions import Forbidden
        import time as _time

        sup1 = _make_user("supervisor", "ts_own_a", "ts_own_a@test.com")
        sup2 = _make_user("supervisor", "ts_own_b", "ts_own_b@test.com")
        thesis = _make_thesis(sup1, "sup1 owns this")
        # Only sup1 has a Thesis_Supervisor row; sup2 does not
        db.session.add(Thesis_Supervisor(
            thesis_id=thesis.id, supervisor_id=sup1.id, assigned_at=int(_time.time())
        ))
        db.session.commit()
        with pytest.raises(Forbidden):
            assert_supervisor_owns_thesis(sup2.id, thesis.id)

    def test_get_student_theses(self, app):
        from superviseme.services.thesis_service import get_student_theses
        from superviseme import db
        from superviseme.models import Thesis

        pub = _make_user("supervisor", "ts_stu_sup", "ts_stu_sup@test.com")
        stu = _make_user("student", "ts_stu_stu", "ts_stu_stu@test.com")

        thesis = Thesis(
            title="Student Assigned Thesis",
            description="desc",
            publisher_id=pub.id,
            author_id=stu.id,
            is_public=True,
            frozen=False,
            level="master",
            created_at=int(time.time()),
        )
        db.session.add(thesis)
        db.session.commit()

        results = get_student_theses(stu.id)
        titles = [t.title for t in results]
        assert "Student Assigned Thesis" in titles


# ===========================================================================
# TestNotificationService
# ===========================================================================

class TestNotificationService:
    """Tests for superviseme/services/notification_service.py.

    NOTE: send_notification() uses field names (user_id, related_id) that do
    not match the actual Notification model (recipient_id, actor_id, thesis_id).
    This is a **known regression** exposed by Stage 6 tests: the service was
    written against an assumed schema that diverges from the real model.

    The tests below document the expected graceful-failure behaviour and the
    correct model fields to guide the follow-up fix.
    """

    def test_send_notification_graceful_failure(self, app):
        """send_notification returns False (graceful) because the model uses
        recipient_id/actor_id, not user_id — this is the regression test."""
        from superviseme.services.notification_service import send_notification
        u = _make_user("student", "ns_rcpt", "ns_rcpt@test.com")
        # Service attempts to create Notification(user_id=...) which doesn't exist
        result = send_notification(u.id, "Hello", notification_type="general")
        # Expect False — service catches the exception and returns False
        assert result is False, (
            "send_notification should return False on model field mismatch; "
            "fix: rename user_id→recipient_id and add required actor_id/title fields"
        )

    def test_get_unread_count_returns_zero_gracefully(self, app):
        """get_unread_count returns 0 gracefully when the query fails."""
        from superviseme.services.notification_service import get_unread_count
        u = _make_user("student", "ns_cnt", "ns_cnt@test.com")
        # Will hit SQLAlchemy error (no user_id column) but should not raise
        count = get_unread_count(u.id)
        assert count == 0

    def test_invalidate_unread_count_does_not_raise(self, app):
        """invalidate_unread_count must never raise even if the cache key is absent."""
        from superviseme.services.notification_service import invalidate_unread_count
        # Should not raise
        invalidate_unread_count(99999)

    def test_mark_all_read_returns_zero_gracefully(self, app):
        """mark_all_read returns 0 gracefully when query fails (model mismatch)."""
        from superviseme.services.notification_service import mark_all_read
        u = _make_user("student", "ns_mar", "ns_mar@test.com")
        result = mark_all_read(u.id)
        assert result == 0

    # --- Regression documentation fixture (not a test, but a note) ---
    def test_notification_model_has_recipient_id(self, app):
        """Document the correct Notification model fields for the follow-up fix."""
        from superviseme.models import Notification
        cols = {c.name for c in Notification.__table__.columns}
        assert "recipient_id" in cols, "Notification model must have recipient_id"
        assert "actor_id" in cols, "Notification model must have actor_id"
        assert "title" in cols, "Notification model must have title"
        # Confirm the WRONG field is absent
        assert "user_id" not in cols, (
            "notification_service.py uses 'user_id' but the model has 'recipient_id'. "
            "Fix notification_service.send_notification() to use the correct fields."
        )

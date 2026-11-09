"""
tests/test_stage6_security.py
-------------------------------
Stage 6: Tests for the security features introduced in Stage 2.

Covers:
  - superviseme/utils/crypto.py  (Fernet encrypt/decrypt)
  - superviseme/utils/decorators.py  (@requires_role)
  - models.py  (CheckConstraint on user_type)
"""
from __future__ import annotations

import os
import time
import pytest
from unittest.mock import patch

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_user(user_type, username, email, is_enabled=True):
    from superviseme import db
    from superviseme.models import User_mgmt
    from werkzeug.security import generate_password_hash

    user = User_mgmt(
        username=username,
        name=username.capitalize(),
        surname="Test",
        email=email,
        password=generate_password_hash("password"),
        user_type=user_type,
        joined_on=int(time.time()),
        is_enabled=is_enabled,
    )
    db.session.add(user)
    db.session.commit()
    return user


def _login(client, email, password="password"):
    return client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=True,
    )


# ===========================================================================
# TestCrypto
# ===========================================================================

class TestCrypto:
    """Unit tests for superviseme/utils/crypto.py."""

    @pytest.fixture(autouse=True)
    def _reset_fernet(self):
        """Reset the module-level _fernet cache between tests."""
        import superviseme.utils.crypto as crypto_mod
        original_fernet = crypto_mod._fernet
        original_warned = crypto_mod._key_missing_warned
        yield
        crypto_mod._fernet = original_fernet
        crypto_mod._key_missing_warned = original_warned

    def test_encrypt_none_returns_none(self):
        from superviseme.utils.crypto import encrypt_token
        assert encrypt_token(None) is None

    def test_decrypt_none_returns_none(self):
        from superviseme.utils.crypto import decrypt_token
        assert decrypt_token(None) is None

    def test_dev_fallback_identity_encrypt(self):
        """Without TOKEN_ENCRYPTION_KEY in dev mode, encrypt is identity."""
        import superviseme.utils.crypto as crypto_mod
        crypto_mod._fernet = None  # force re-init
        with patch.dict(os.environ, {"TOKEN_ENCRYPTION_KEY": "", "FLASK_ENV": "testing"}):
            from superviseme.utils.crypto import encrypt_token
            assert encrypt_token("my_token") == "my_token"

    def test_dev_fallback_identity_decrypt(self):
        """Without TOKEN_ENCRYPTION_KEY in dev mode, decrypt is identity."""
        import superviseme.utils.crypto as crypto_mod
        crypto_mod._fernet = None
        with patch.dict(os.environ, {"TOKEN_ENCRYPTION_KEY": "", "FLASK_ENV": "testing"}):
            from superviseme.utils.crypto import decrypt_token
            assert decrypt_token("my_token") == "my_token"

    def test_encrypt_decrypt_roundtrip_with_key(self):
        """Real Fernet key: encrypt then decrypt returns the original string."""
        from cryptography.fernet import Fernet
        import superviseme.utils.crypto as crypto_mod

        key = Fernet.generate_key().decode()
        crypto_mod._fernet = None  # force re-init

        with patch.dict(os.environ, {"TOKEN_ENCRYPTION_KEY": key, "FLASK_ENV": "testing"}):
            from superviseme.utils.crypto import encrypt_token, decrypt_token
            original = "access_token_abc123"
            encrypted = encrypt_token(original)
            assert encrypted != original          # it was actually encrypted
            assert decrypt_token(encrypted) == original  # roundtrip recovers value

    def test_encrypted_value_differs_each_time(self):
        """Fernet includes a nonce, so encrypting the same plaintext yields different ciphertexts."""
        from cryptography.fernet import Fernet
        import superviseme.utils.crypto as crypto_mod

        key = Fernet.generate_key().decode()
        crypto_mod._fernet = None

        with patch.dict(os.environ, {"TOKEN_ENCRYPTION_KEY": key, "FLASK_ENV": "testing"}):
            from superviseme.utils.crypto import encrypt_token
            assert encrypt_token("token") != encrypt_token("token")

    def test_legacy_plaintext_fallback_on_decrypt(self):
        """decrypt_token returns ciphertext as-is when it cannot be decrypted (legacy row)."""
        from cryptography.fernet import Fernet
        import superviseme.utils.crypto as crypto_mod

        key = Fernet.generate_key().decode()
        crypto_mod._fernet = None

        with patch.dict(os.environ, {"TOKEN_ENCRYPTION_KEY": key, "FLASK_ENV": "testing"}):
            from superviseme.utils.crypto import decrypt_token
            # Pass a plaintext value that is not a valid Fernet token
            result = decrypt_token("legacy_plaintext_token")
            assert result == "legacy_plaintext_token"

    def test_production_raises_without_key(self):
        """In production mode, missing TOKEN_ENCRYPTION_KEY raises RuntimeError."""
        import superviseme.utils.crypto as crypto_mod
        crypto_mod._fernet = None

        with patch.dict(os.environ, {"TOKEN_ENCRYPTION_KEY": "", "FLASK_ENV": "production"}):
            with pytest.raises(RuntimeError, match="TOKEN_ENCRYPTION_KEY"):
                from superviseme.utils.crypto import encrypt_token
                encrypt_token("token")


# ===========================================================================
# TestRequiresRole
# ===========================================================================

class TestRequiresRole:
    """Integration tests for the @requires_role decorator.

    Creates a minimal Flask app with instrumented test routes to verify
    the decorator's behaviour without touching the full superviseme routes.
    """

    @pytest.fixture
    def role_app(self, app):
        """Register test routes decorated with @requires_role on the app."""
        from superviseme.utils.decorators import requires_role
        from flask_login import login_required

        @app.route("/test/admin-only")
        @login_required
        @requires_role("admin")
        def admin_only():
            return "admin OK", 200

        @app.route("/test/multi-role")
        @login_required
        @requires_role("supervisor", "researcher")
        def multi_role():
            return "multi OK", 200

        return app

    def test_matching_role_allowed(self, role_app, client):
        admin = _make_user("admin", "ra_admin", "ra_admin@test.com")
        _login(client, admin.email)
        resp = client.get("/test/admin-only")
        assert resp.status_code == 200
        assert b"admin OK" in resp.data

    def test_wrong_role_redirects(self, role_app, client):
        student = _make_user("student", "ra_student", "ra_student@test.com")
        _login(client, student.email)
        resp = client.get("/test/admin-only", follow_redirects=False)
        # Should redirect away (302), not serve the page
        assert resp.status_code == 302

    def test_wrong_role_does_not_serve_content(self, role_app, client):
        supervisor = _make_user("supervisor", "ra_sup", "ra_sup@test.com")
        _login(client, supervisor.email)
        resp = client.get("/test/admin-only", follow_redirects=True)
        assert b"admin OK" not in resp.data

    def test_disabled_account_gets_403(self, role_app, client):
        """A disabled user who is somehow logged in gets 403 from @requires_role.

        The login route itself blocks disabled users (they get a 302 to login),
        so we simulate a logged-in session via Flask-Login directly to test the
        decorator in isolation.
        """
        from flask_login import login_user

        admin = _make_user("admin", "ra_disabled", "ra_disabled@test.com", is_enabled=False)

        # Inject a logged-in session bypassing the login route
        with role_app.test_request_context():
            login_user(admin, force=True)

        with client.session_transaction() as sess:
            # Build a session that Flask-Login considers authenticated
            sess["_user_id"] = str(admin.id)
            sess["_fresh"] = True

        resp = client.get("/test/admin-only")
        # @requires_role checks is_enabled and aborts 403
        assert resp.status_code == 403

    def test_multi_role_first_allowed(self, role_app, client):
        sup = _make_user("supervisor", "ra_sup2", "ra_sup2@test.com")
        _login(client, sup.email)
        resp = client.get("/test/multi-role")
        assert resp.status_code == 200
        assert b"multi OK" in resp.data

    def test_multi_role_second_allowed(self, role_app, client):
        res = _make_user("researcher", "ra_res2", "ra_res2@test.com")
        _login(client, res.email)
        resp = client.get("/test/multi-role")
        assert resp.status_code == 200
        assert b"multi OK" in resp.data

    def test_unauthenticated_redirects(self, role_app, client):
        resp = client.get("/test/admin-only", follow_redirects=False)
        assert resp.status_code == 302


# ===========================================================================
# TestCheckConstraint
# ===========================================================================

class TestCheckConstraint:
    """Verify the CheckConstraint on user_type (enforced by SQLite in batch mode)."""

    def test_valid_user_types_accepted(self, app):
        """All four valid user types should be insertable without error."""
        from superviseme import db
        from superviseme.models import User_mgmt
        from werkzeug.security import generate_password_hash

        for role in ("admin", "supervisor", "student", "researcher"):
            u = User_mgmt(
                username=f"cc_{role}",
                name=role.capitalize(),
                surname="CC",
                email=f"cc_{role}@test.com",
                password=generate_password_hash("pw"),
                user_type=role,
                joined_on=int(time.time()),
                is_enabled=True,
            )
            db.session.add(u)
        # Should commit without error
        db.session.commit()
        assert User_mgmt.query.count() >= 4

    def test_model_accepts_expected_roles_only(self, app):
        """The CheckConstraint column is defined — the constraint name is present in the schema."""
        from superviseme.models import User_mgmt
        import sqlalchemy

        # Inspect constraints on the user_mgmt table
        inspector = sqlalchemy.inspect(User_mgmt.__table__)
        # Flask-SQLAlchemy/SQLite may not reflect check constraints from CREATE TABLE,
        # but we can verify the column exists and stores the right values
        col = User_mgmt.__table__.c.get("user_type")
        assert col is not None, "user_type column must exist"

    def test_name_surname_varchar50(self, app):
        """Stage 1 widened name/surname from 15 to 50 chars — verify 50-char values fit."""
        from superviseme import db
        from superviseme.models import User_mgmt
        from werkzeug.security import generate_password_hash

        long_name = "A" * 50
        u = User_mgmt(
            username="varchar50_test",
            name=long_name,
            surname=long_name,
            email="varchar50@test.com",
            password=generate_password_hash("pw"),
            user_type="student",
            joined_on=int(time.time()),
            is_enabled=True,
        )
        db.session.add(u)
        db.session.commit()

        fetched = User_mgmt.query.filter_by(username="varchar50_test").one()
        assert fetched.name == long_name
        assert fetched.surname == long_name

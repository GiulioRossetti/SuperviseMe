"""
superviseme/utils/crypto.py
---------------------------
Fernet symmetric encryption for OAuth tokens stored in the database.

Usage:
    from superviseme.utils.crypto import encrypt_token, decrypt_token

    encrypted = encrypt_token("raw_access_token")
    raw       = decrypt_token(encrypted)

Configuration:
    Set TOKEN_ENCRYPTION_KEY in your environment (.env or OS env).
    Generate a valid key with:
        python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

    If the key is absent (e.g. during development without .env), the functions
    fall back to identity (no encryption) and emit a warning.  In production
    an absent key raises RuntimeError so the app refuses to start with
    plaintext tokens.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_fernet = None
_key_missing_warned = False


def _get_fernet():
    """Return the cached Fernet instance, initialising it on first call."""
    global _fernet, _key_missing_warned

    if _fernet is not None:
        return _fernet

    raw_key = os.getenv("TOKEN_ENCRYPTION_KEY", "").strip()
    if not raw_key:
        env = os.getenv("FLASK_ENV", "production").lower()
        if env == "production":
            raise RuntimeError(
                "TOKEN_ENCRYPTION_KEY must be set in production to protect OAuth tokens. "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; "
                "print(Fernet.generate_key().decode())\""
            )
        if not _key_missing_warned:
            logger.warning(
                "TOKEN_ENCRYPTION_KEY is not set — OAuth tokens will be stored in plaintext. "
                "This is acceptable only in development."
            )
            _key_missing_warned = True
        return None

    try:
        from cryptography.fernet import Fernet
        _fernet = Fernet(raw_key.encode())
    except Exception as exc:
        raise RuntimeError(f"Invalid TOKEN_ENCRYPTION_KEY: {exc}") from exc

    return _fernet


def encrypt_token(plaintext: str | None) -> str | None:
    """Encrypt *plaintext* and return a URL-safe base64 string, or None."""
    if plaintext is None:
        return None
    f = _get_fernet()
    if f is None:
        return plaintext  # dev fallback: identity
    return f.encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str | None) -> str | None:
    """Decrypt *ciphertext* and return the original string, or None.

    Returns *ciphertext* unchanged if it cannot be decrypted (e.g. the value
    was stored before encryption was introduced) so that existing rows do not
    silently break the app.
    """
    if ciphertext is None:
        return None
    f = _get_fernet()
    if f is None:
        return ciphertext  # dev fallback: identity
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except Exception:
        # Token pre-dates encryption — return as-is and log a warning.
        logger.warning(
            "decrypt_token: could not decrypt value (may be a legacy plaintext token). "
            "Re-authenticate to refresh and re-encrypt."
        )
        return ciphertext

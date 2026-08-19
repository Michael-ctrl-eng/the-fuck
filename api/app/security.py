from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

_ph = PasswordHasher()


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError, ValueError):
        return False


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def constant_time_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def _fernet(secret_key: str) -> Fernet:
    key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"raqib-token-encryption",
        info=b"fernet-v1",
    ).derive(secret_key.encode("utf-8"))
    return Fernet(base64.urlsafe_b64encode(key))


class TokenCipher:
    """Encrypts/decrypts secrets (e.g. Meta access tokens) at rest.

    Uses an HKDF-derived Fernet key so a single SECRET_KEY drives all
    derived keys without storing additional secrets.
    """

    def __init__(self, secret_key: str) -> None:
        self._fernet = _fernet(secret_key)

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, token: str) -> str:
        return self._fernet.decrypt(token.encode("ascii")).decode("utf-8")

    @classmethod
    def from_secret(cls, secret_key: str) -> "TokenCipher":
        return cls(secret_key)

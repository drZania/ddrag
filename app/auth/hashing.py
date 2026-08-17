"""Password hashing and verification using Argon2id."""

from pwdlib import PasswordHash


password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Return an Argon2id hash for a plaintext password."""

    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str | None) -> bool:
    """Verify a password without accepting users with no stored hash."""

    return hashed_password is not None and password_hash.verify(password, hashed_password)
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets


SCRYPT_ALGORITHM = "scrypt"
SCRYPT_N = 2 ** 14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32
SALT_BYTES = 16
HASH_PARTS = 6


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
    )
    return "$".join((
        SCRYPT_ALGORITHM,
        str(SCRYPT_N),
        str(SCRYPT_R),
        str(SCRYPT_P),
        _encode_bytes(salt),
        _encode_bytes(digest),
    ))


def verify_password(password: str, stored_hash: str) -> bool:
    parts = str(stored_hash or "").split("$")
    if len(parts) != HASH_PARTS or parts[0] != SCRYPT_ALGORITHM:
        return False
    _, n_text, r_text, p_text, salt_text, digest_text = parts
    expected = _decode_bytes(digest_text)
    actual = hashlib.scrypt(
        password.encode("utf-8"),
        salt=_decode_bytes(salt_text),
        n=int(n_text),
        r=int(r_text),
        p=int(p_text),
        dklen=len(expected),
    )
    return hmac.compare_digest(actual, expected)


def _encode_bytes(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii")


def _decode_bytes(value: str) -> bytes:
    return base64.urlsafe_b64decode(value.encode("ascii"))

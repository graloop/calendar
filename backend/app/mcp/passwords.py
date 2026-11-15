# The connector's password, as a salted scrypt hash ("scrypt$N$r$p$salt$digest"),
# never stored in clear. Copied from the training app's security.py so both apps
# read the same format. Standard library only, no extra dependency.

import base64
import hashlib
import hmac
import secrets

_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**14, 8, 1


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def hash_password(password: str) -> str:
    """A new salted hash. The cost parameters are stored with it, so they can be
    raised later without breaking existing passwords."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32)
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${_b64(salt)}${_b64(digest)}"


# Checked against when no hash is set, so the answer takes the same time either way.
_DUMMY_HASH = hash_password(secrets.token_hex(16))


def verify_password(password: str, stored: str | None) -> bool:
    """True when `password` matches `stored`. With no stored hash it still does
    the work and returns False."""
    if not stored:
        stored, ok = _DUMMY_HASH, False
    else:
        ok = True
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        candidate = hashlib.scrypt(
            password.encode("utf-8"), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=32
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(candidate, base64.b64decode(digest)) and ok

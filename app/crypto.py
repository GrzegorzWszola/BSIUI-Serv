import base64
import re

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.serialization import load_der_public_key
from fastapi import HTTPException

# Canonical Base64 (RFC 4648 §4): only full-pad encodings accepted.
_BASE64_RE = re.compile(
    r"^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$"
)

IV_BYTES = 12
GCM_TAG_BYTES = 16


def decode_base64(value: str) -> bytes | None:
    """Strict Base64 decoding; returns *None* for anything non-canonical."""
    if not value or not _BASE64_RE.match(value):
        return None
    try:
        return base64.b64decode(value)
    except Exception:
        return None


def _import_p256_public_key(b64: str) -> ec.EllipticCurvePublicKey | None:
    """Import a Base64-encoded SPKI P-256 public key, or *None* if invalid."""
    der = decode_base64(b64)
    if der is None:
        return None
    try:
        key = load_der_public_key(der)
        if not isinstance(key, ec.EllipticCurvePublicKey):
            return None
        if not isinstance(key.curve, ec.SECP256R1):
            return None
        return key
    except Exception:
        return None


def is_public_key(value: str) -> bool:
    """Return *True* when *value* is a valid Base64 SPKI P-256 public key."""
    return _import_p256_public_key(value) is not None


def assert_public_keys(values: list[str]) -> None:
    """Raise ``HTTPException(400)`` if any value is not a valid P-256 key."""
    for v in values:
        if not is_public_key(v):
            raise HTTPException(
                status_code=400, detail="Nieprawidłowy klucz publiczny"
            )


def validate_bundle(
    ik_pub: str, spk_pub: str, sig: str, opk_pub: list[str]
) -> None:
    """Validate every key in a bundle and verify the SPK signature.

    Checks:
    1. ``ik_pub``, ``spk_pub`` and every ``opk_pub`` entry are valid P-256
       public keys in SPKI (DER) format, Base64-encoded.
    2. ``sig`` is a valid ECDSA-SHA256 signature of the raw SPKI bytes of
       ``spk_pub``, produced by the private half of ``ik_pub``.
    """
    assert_public_keys([ik_pub, spk_pub, *opk_pub])

    ik = _import_p256_public_key(ik_pub)
    if ik is None:
        raise HTTPException(
            status_code=400, detail="Nieprawidłowy klucz publiczny"
        )

    spk_bytes = decode_base64(spk_pub)
    sig_bytes = decode_base64(sig)
    if spk_bytes is None or sig_bytes is None:
        raise HTTPException(
            status_code=400, detail="Nieprawidłowy podpis klucza"
        )

    # The protocol sends raw r||s (64 bytes, Web Crypto's format), but
    # `cryptography` verifies DER-encoded signatures only, so convert first.
    if len(sig_bytes) != 64:
        raise HTTPException(
            status_code=400, detail="Nieprawidłowy podpis klucza"
        )
    der_sig = encode_dss_signature(
        int.from_bytes(sig_bytes[:32], "big"),
        int.from_bytes(sig_bytes[32:], "big"),
    )

    try:
        ik.verify(der_sig, spk_bytes, ec.ECDSA(SHA256()))
    except Exception:
        raise HTTPException(
            status_code=400, detail="Nieprawidłowy podpis klucza"
        )


def validate_ciphertext(msg: str) -> None:
    """Raise if *msg* is not valid Base64 or shorter than the GCM tag."""
    data = decode_base64(msg)
    if data is None or len(data) < GCM_TAG_BYTES:
        raise HTTPException(
            status_code=400, detail="Nieprawidłowy szyfrogram"
        )


def validate_iv(iv: str) -> None:
    """Raise if *iv* is not exactly 12 bytes after Base64 decoding."""
    data = decode_base64(iv)
    if data is None or len(data) != IV_BYTES:
        raise HTTPException(
            status_code=400, detail="Nieprawidłowy wektor IV"
        )

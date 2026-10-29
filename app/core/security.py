"""Cryptographic utilities: Argon2id hashing, API key tokens, HMAC signing."""

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Optional, Tuple
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from app.config import settings

# Argon2id hasher configured with OWASP recommendation for password hashing
ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MB
    parallelism=1,
    hash_len=32,
    salt_len=16,
)


def generate_api_key(prefix: str = "ocr_live_") -> Tuple[str, str, str]:
    """
    Generates a secure API key, its short prefix, and its Argon2id hash.
    Returns:
        (raw_secret_key, key_prefix, hashed_key)
    """
    random_bytes = secrets.token_hex(24)  # 48 hex chars
    raw_key = f"{prefix}{random_bytes}"
    key_prefix = raw_key[:16]  # e.g., 'ocr_live_ab12cd'
    hashed_key = ph.hash(raw_key)
    return raw_key, key_prefix, hashed_key


def verify_api_key(raw_key: str, hashed_key: str) -> bool:
    """Verifies a raw API key against its Argon2id hash in constant time."""
    try:
        return ph.verify(hashed_key, raw_key)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def hash_secret(secret: str) -> str:
    """Hashes a secret string using Argon2id."""
    return ph.hash(secret)


def verify_secret(secret: str, hashed_secret: str) -> bool:
    """Verifies a secret against an Argon2id hash."""
    try:
        return ph.verify(hashed_secret, secret)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def compute_webhook_signature(secret: str, timestamp: int, payload: bytes) -> str:
    """Computes HMAC-SHA256 signature for webhook payload verification."""
    data = f"t={timestamp}.".encode("utf-8") + payload
    return hmac.new(secret.encode("utf-8"), data, hashlib.sha256).hexdigest()


def verify_webhook_signature(
    secret: str,
    timestamp: int,
    payload: bytes,
    received_signature: str,
    tolerance_seconds: int = 300,
) -> bool:
    """Verifies HMAC-SHA256 signature with replay protection."""
    current_time = int(time.time())
    if abs(current_time - timestamp) > tolerance_seconds:
        return False

    expected_sig = compute_webhook_signature(secret, timestamp, payload)
    return hmac.compare_digest(expected_sig, received_signature)


def generate_download_token(document_id: str, tenant_id: str, ttl_seconds: int = 300) -> str:
    """Creates a short-lived HMAC-signed token for worker document retrieval."""
    expires_at = int(time.time()) + ttl_seconds
    payload_dict = {
        "doc_id": document_id,
        "tenant_id": tenant_id,
        "exp": expires_at,
    }
    payload_json = json.dumps(payload_dict, separators=(",", ":")).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_json).decode("utf-8").rstrip("=")
    sig = hmac.new(settings.secret_key.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"


def verify_download_token(token: str) -> Tuple[str, str]:
    """Verifies download token and returns (document_id, tenant_id) or raises ValueError."""
    parts = token.split(".")
    if len(parts) != 2:
        raise ValueError("Malformed download token")

    payload_b64, received_sig = parts
    expected_sig = hmac.new(settings.secret_key.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_sig, received_sig):
        raise ValueError("Invalid download token signature")

    # Pad base64 if needed
    padded_b64 = payload_b64 + "=" * (-len(payload_b64) % 4)
    payload_bytes = base64.urlsafe_b64decode(padded_b64.encode("utf-8"))
    data = json.loads(payload_bytes.decode("utf-8"))

    if int(time.time()) > data.get("exp", 0):
        raise ValueError("Download token has expired")

    return data["doc_id"], data["tenant_id"]

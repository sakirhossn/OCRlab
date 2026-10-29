"""Webhook signature verification helper for Python receivers."""

import hashlib
import hmac
import time
from typing import Dict, Union


def verify_webhook_signature(
    secret: str,
    headers: Dict[str, str],
    raw_payload: Union[str, bytes],
    tolerance_seconds: int = 300,
) -> bool:
    """
    Verifies that an incoming webhook was signed with the tenant's secret key.
    
    Expected Headers:
      - X-UnlimitedOCR-Signature: t=1730112345,v1=9f8a...
      - X-UnlimitedOCR-Timestamp: 1730112345
    """
    normalized_headers = {k.lower(): v for k, v in headers.items()}
    sig_header = normalized_headers.get("x-unlimitedocr-signature", "")
    ts_header = normalized_headers.get("x-unlimitedocr-timestamp", "")

    if not sig_header or not ts_header:
        return False

    try:
        timestamp = int(ts_header)
    except ValueError:
        return False

    # Check replay tolerance
    current_time = int(time.time())
    if abs(current_time - timestamp) > tolerance_seconds:
        return False

    # Parse signature string: "t=...,v1=..."
    received_hash = None
    for part in sig_header.split(","):
        if part.startswith("v1="):
            received_hash = part[3:]
            break

    if not received_hash:
        return False

    if isinstance(raw_payload, str):
        raw_bytes = raw_payload.encode("utf-8")
    else:
        raw_bytes = raw_payload

    data_to_sign = f"t={timestamp}.".encode("utf-8") + raw_bytes
    expected_hash = hmac.new(secret.encode("utf-8"), data_to_sign, hashlib.sha256).hexdigest()

    return hmac.compare_digest(expected_hash, received_hash)

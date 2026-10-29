"""Unit tests for cryptography, storage vault, and HMAC signatures."""

import os
import time
from pathlib import Path
import pytest
from cryptography.exceptions import InvalidTag
from app.core.security import (
    compute_webhook_signature,
    generate_api_key,
    verify_api_key,
    verify_webhook_signature,
)
from app.core.storage import EncryptedStorageVault


def test_argon2id_api_key_lifecycle():
    raw_key, prefix, hashed_key = generate_api_key()
    assert raw_key.startswith("ocr_live_")
    assert prefix == raw_key[:16]
    assert hashed_key.startswith("$argon2id$")

    # Positive verification
    assert verify_api_key(raw_key, hashed_key) is True

    # Negative verification
    assert verify_api_key(raw_key + "tampered", hashed_key) is False
    assert verify_api_key("ocr_live_completely_wrong_key", hashed_key) is False


def test_aes_gcm_storage_vault(tmp_path: Path):
    vault = EncryptedStorageVault(key_secret="test-secret-key-32-bytes-long!", base_dir=tmp_path)
    tenant_id = "test_tenant_1"
    file_id = "doc_abc123"
    original_data = b"Confidential document content for OCR processing."

    # 1. Encrypt and save
    saved_path = vault.encrypt_and_save(tenant_id, file_id, original_data)
    assert saved_path.is_file()

    # Raw file on disk must NOT contain plaintext
    with open(saved_path, "rb") as f:
        disk_bytes = f.read()
    assert original_data not in disk_bytes

    # 2. Read and decrypt
    decrypted = vault.read_and_decrypt(saved_path)
    assert decrypted == original_data

    # 3. Tampering detection
    tampered_bytes = bytearray(disk_bytes)
    tampered_bytes[-1] ^= 0x01  # Flip one bit in authentication tag
    with open(saved_path, "wb") as f:
        f.write(tampered_bytes)

    with pytest.raises(Exception):
        vault.read_and_decrypt(saved_path)

    # 4. Secure deletion
    assert vault.delete_file(saved_path) is True
    assert not saved_path.exists()


def test_webhook_hmac_signatures():
    secret = "whsec_test_secret_key_12345"
    timestamp = int(time.time())
    payload = b'{"event":"job.completed","job_id":"job_987"}'

    sig = compute_webhook_signature(secret, timestamp, payload)
    assert isinstance(sig, str)
    assert len(sig) == 64  # SHA256 hex string

    # Valid signature
    assert verify_webhook_signature(secret, timestamp, payload, sig) is True

    # Tampered payload
    assert verify_webhook_signature(secret, timestamp, b'{"event":"job.tampered"}', sig) is False

    # Wrong secret
    assert verify_webhook_signature("whsec_wrong_secret", timestamp, payload, sig) is False

    # Expired timestamp (replay attack prevention, > 300s)
    old_timestamp = timestamp - 400
    old_sig = compute_webhook_signature(secret, old_timestamp, payload)
    assert verify_webhook_signature(secret, old_timestamp, payload, old_sig) is False

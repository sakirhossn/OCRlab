"""Storage manager: AES-256-GCM encrypted vault for documents and results."""

import hashlib
import os
from pathlib import Path
from typing import Optional, Union
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.config import settings


class EncryptedStorageVault:
    """Manages encrypted document files and results on disk using AES-256-GCM."""

    def __init__(self, key_secret: Optional[str] = None, base_dir: Optional[Path] = None):
        raw_key = (key_secret or settings.storage_encryption_key).encode("utf-8")
        # Ensure exactly 32 bytes for AES-256
        self.key = hashlib.sha256(raw_key).digest()
        self.aesgcm = AESGCM(self.key)
        self.base_dir = base_dir or settings.storage_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_tenant_dir(self, tenant_id: str, subfolder: str = "docs") -> Path:
        tenant_path = self.base_dir / tenant_id / subfolder
        tenant_path.mkdir(parents=True, exist_ok=True)
        return tenant_path

    def encrypt_and_save(
        self,
        tenant_id: str,
        file_id: str,
        data: bytes,
        subfolder: str = "docs",
        extension: str = ".enc",
    ) -> Path:
        """
        Encrypts plaintext data with a fresh 96-bit random nonce and saves to disk.
        Disk layout: [12 bytes nonce] + [ciphertext with embedded tag]
        """
        nonce = os.urandom(12)  # 96-bit nonce
        ciphertext = self.aesgcm.encrypt(nonce, data, associated_data=None)

        folder = self._get_tenant_dir(tenant_id, subfolder)
        file_path = folder / f"{file_id}{extension}"

        with open(file_path, "wb") as f:
            f.write(nonce + ciphertext)

        return file_path

    def read_and_decrypt(self, file_path: Union[str, Path]) -> bytes:
        """Reads encrypted file from disk and decrypts using AES-256-GCM."""
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Encrypted file not found: {path}")

        with open(path, "rb") as f:
            raw = f.read()

        if len(raw) < 28:  # 12 nonce + 16 tag minimum
            raise ValueError("Corrupt encrypted payload: file too short")

        nonce = raw[:12]
        ciphertext = raw[12:]

        return self.aesgcm.decrypt(nonce, ciphertext, associated_data=None)

    def delete_file(self, file_path: Union[str, Path]) -> bool:
        """Cryptographically purges the file from disk (GDPR/Compliance)."""
        path = Path(file_path)
        if path.is_file():
            # Overwrite with random bytes before unlink for secure shredding
            size = path.stat().st_size
            try:
                with open(path, "wb") as f:
                    f.write(os.urandom(size))
            except Exception:
                pass
            path.unlink(missing_ok=True)
            return True
        return False


storage_vault = EncryptedStorageVault()

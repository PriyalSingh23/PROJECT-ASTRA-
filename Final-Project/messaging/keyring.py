"""Station Keyring Manager.

Persists station cryptographic identity keypairs (ML-KEM-768 and X25519)
to disk under Final-Project/data/keys/{station_id}.keyring with 0600 file permissions.
Supports atomic loading, key rotation, and secure zeroization.
"""

import os
import json
import base64
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple

from cryptography.hazmat.primitives.asymmetric import x25519

from messaging.mlkem768 import (
    mlkem768_keygen,
    MLKEM_EK_BYTES,
    MLKEM_DK_BYTES,
)

KEYRING_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../data/keys")
)


def compute_fingerprint(data: bytes) -> str:
    """Returns a truncated SHA-256 fingerprint formatted as SHA256:<hex[:16]>."""
    digest = hashlib.sha256(data).hexdigest()
    return f"SHA256:{digest[:16]}"


class StationKeyringManager:
    """Manages on-disk and in-memory cryptographic keyrings for tactical stations."""

    def __init__(self, keyring_dir: str = KEYRING_DIR):
        self.keyring_dir = os.path.abspath(keyring_dir)
        os.makedirs(self.keyring_dir, exist_ok=True)
        self._memory_cache: Dict[str, Dict[str, Any]] = {}

    def get_keyring_path(self, station_id: str) -> str:
        """Returns the canonical file path for a station's keyring."""
        safe_id = "".join(c for c in station_id if c.isalnum() or c in ("-", "_"))
        return os.path.join(self.keyring_dir, f"{safe_id}.keyring")

    def _generate_fresh_bundle(self, station_id: str) -> Dict[str, Any]:
        """Generates fresh ML-KEM-768 and X25519 keypairs and structures the bundle."""
        # 1. Generate X25519 identity keypair
        x_priv = x25519.X25519PrivateKey.generate()
        x_priv_bytes = x_priv.private_bytes_raw()
        x_pub_bytes = x_priv.public_key().public_bytes_raw()

        # 2. Generate ML-KEM-768 keypair
        ek, dk = mlkem768_keygen()

        now = datetime.now(timezone.utc).isoformat()
        bundle = {
            "station_id": station_id,
            "version": 1,
            "created_at": now,
            "x25519": {
                "private_key_b64": base64.b64encode(x_priv_bytes).decode("ascii"),
                "public_key_b64": base64.b64encode(x_pub_bytes).decode("ascii"),
                "fingerprint": compute_fingerprint(x_pub_bytes),
            },
            "mlkem768": {
                "encapsulation_key_b64": base64.b64encode(ek).decode("ascii"),
                "decapsulation_key_b64": base64.b64encode(dk).decode("ascii"),
                "fingerprint": compute_fingerprint(ek),
            },
        }
        return bundle

    def _save_bundle(self, station_id: str, bundle: Dict[str, Any]) -> None:
        """Atomically saves bundle to disk with 0600 permissions."""
        target_path = self.get_keyring_path(station_id)
        tmp_path = f"{target_path}.tmp"
        content = json.dumps(bundle, indent=2).encode("utf-8")

        with open(tmp_path, "wb") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())

        try:
            os.chmod(tmp_path, 0o600)
        except OSError:
            pass

        os.replace(tmp_path, target_path)
        self._memory_cache[station_id] = bundle

    def load_or_generate_keyring(self, station_id: str) -> Dict[str, Any]:
        """Loads an existing keyring from disk or generates a fresh one."""
        if station_id in self._memory_cache:
            return self._memory_cache[station_id]

        path = self.get_keyring_path(station_id)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    bundle = json.load(f)
                # Verify bundle has required fields
                if "x25519" in bundle and "mlkem768" in bundle:
                    self._memory_cache[station_id] = bundle
                    return bundle
            except Exception:
                pass

        # Generate and save fresh keyring
        bundle = self._generate_fresh_bundle(station_id)
        self._save_bundle(station_id, bundle)
        return bundle

    def rotate_keyring(self, station_id: str) -> Dict[str, Any]:
        """Generates fresh keypairs, updates disk file atomically, and updates cache."""
        bundle = self._generate_fresh_bundle(station_id)
        self._save_bundle(station_id, bundle)
        return bundle

    def zeroize_keyring(self, station_id: str) -> None:
        """Cryptographically overwrites and purges station keyring file and cache."""
        path = self.get_keyring_path(station_id)
        if os.path.exists(path):
            try:
                size = os.path.getsize(path)
                with open(path, "wb") as f:
                    # Multi-pass overwrite
                    f.write(os.urandom(size))
                    f.flush()
                    os.fsync(f.fileno())
                    f.seek(0)
                    f.write(b"\x00" * size)
                    f.flush()
                    os.fsync(f.fileno())
                os.remove(path)
            except Exception:
                try:
                    os.remove(path)
                except Exception:
                    pass

        if station_id in self._memory_cache:
            del self._memory_cache[station_id]

    def get_local_mlkem_sk(self, station_id: str) -> Optional[bytes]:
        """Returns raw ML-KEM-768 decapsulation key bytes for station."""
        bundle = self.load_or_generate_keyring(station_id)
        try:
            return base64.b64decode(bundle["mlkem768"]["decapsulation_key_b64"])
        except Exception:
            return None

    def get_local_mlkem_pk(self, station_id: str) -> Optional[bytes]:
        """Returns raw ML-KEM-768 encapsulation key bytes for station."""
        bundle = self.load_or_generate_keyring(station_id)
        try:
            return base64.b64decode(bundle["mlkem768"]["encapsulation_key_b64"])
        except Exception:
            return None

    def get_local_x25519_sk(self, station_id: str) -> Optional[bytes]:
        """Returns raw X25519 private key bytes for station."""
        bundle = self.load_or_generate_keyring(station_id)
        try:
            return base64.b64decode(bundle["x25519"]["private_key_b64"])
        except Exception:
            return None

    def get_local_x25519_pk(self, station_id: str) -> Optional[bytes]:
        """Returns raw X25519 public key bytes for station."""
        bundle = self.load_or_generate_keyring(station_id)
        try:
            return base64.b64decode(bundle["x25519"]["public_key_b64"])
        except Exception:
            return None

    def get_public_keys(self, station_id: str) -> Dict[str, Any]:
        """Returns public key metadata dictionary suitable for REST responses."""
        bundle = self.load_or_generate_keyring(station_id)
        return {
            "endpoint_id": station_id,
            "pqc_algorithm": "ML-KEM-768",
            "public_key_pqc": bundle["mlkem768"]["encapsulation_key_b64"],
            "public_key_x25519": bundle["x25519"]["public_key_b64"],
            "pqc_fingerprint": bundle["mlkem768"]["fingerprint"],
            "x25519_fingerprint": bundle["x25519"]["fingerprint"],
            "keyring_status": "READY",
        }


# Process-wide default keyring manager singleton
keyring_manager = StationKeyringManager()

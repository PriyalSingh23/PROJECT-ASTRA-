"""Hybrid Post-Quantum Cryptographic Subsystem (ML-KEM-768 + Ephemeral X25519 + AES-256-GCM).

Implements NIST FIPS 203 ML-KEM-768 combined with Ephemeral X25519 ECDH for
Envelope v3 framing, strict anti-replay AAD binding, dual-stack legacy v2
fallback auto-negotiation, and tamper rejection.
"""

import os
import secrets
import hashlib
from typing import Tuple, Dict, Any, Optional, Union

from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from Crypto.Cipher import AES

from messaging.crypto_v2 import (
    CryptoError,
    AuthenticationError,
    InvalidEnvelopeError,
    decrypt_v2_gcm,
    encrypt_v2_gcm,
    ENVELOPE_VERSION_V2_GCM,
)
from messaging.mlkem768 import (
    mlkem768_keygen,
    mlkem768_encaps,
    mlkem768_decaps,
    MLKEM_EK_BYTES,
    MLKEM_DK_BYTES,
    MLKEM_CT_BYTES,
    MLKEM_SS_BYTES,
)

# ==============================================================================
# Envelope v3 Binary Layout Constants
# ==============================================================================
ENVELOPE_VERSION_V3 = 0x03
PQC_SCHEME_MLKEM768_X25519 = 0x01

X25519_PK_BYTES = 32
NONCE_BYTES = 12      # Standard 96-bit AES-GCM nonce
TAG_BYTES = 16        # 128-bit AES-GCM authentication tag

# Overhead = 1 (ver) + 1 (scheme) + 32 (X25519 eph pk) + 1088 (ML-KEM CT) + 12 (nonce) + 16 (tag) = 1150 bytes
HEADER_OVERHEAD_BYTES = 1 + 1 + X25519_PK_BYTES + MLKEM_CT_BYTES + NONCE_BYTES + TAG_BYTES
assert HEADER_OVERHEAD_BYTES == 1150

HKDF_SALT = b"SHADOWCOMM-PQC-v3"
HKDF_INFO = b"ML-KEM-768/X25519/AES-256-GCM"


def derive_hybrid_session_key(ss_x25519: bytes, ss_mlkem: bytes) -> bytes:
    """Derives a 256-bit AES-GCM symmetric session key via HKDF-SHA256.

    Input Keying Material: SS_hybrid = SS_X25519 || SS_MLKEM (64 bytes).
    Salt: b"SHADOWCOMM-PQC-v3"
    Info: b"ML-KEM-768/X25519/AES-256-GCM"
    """
    if len(ss_x25519) != 32 or len(ss_mlkem) != 32:
        raise ValueError(
            f"Invalid shared secret lengths: SS_X25519={len(ss_x25519)}, SS_MLKEM={len(ss_mlkem)} (both must be 32)"
        )
    ikm = ss_x25519 + ss_mlkem
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=HKDF_SALT,
        info=HKDF_INFO,
    )
    return hkdf.derive(ikm)


def construct_aad(
    sender_endpoint_id: str,
    recipient_endpoint_id: str,
    message_id: str,
    envelope_version: int = ENVELOPE_VERSION_V3,
    scheme_id: int = PQC_SCHEME_MLKEM768_X25519,
) -> bytes:
    """Constructs Associated Authenticated Data (AAD) for anti-replay binding."""
    return (
        bytes([envelope_version, scheme_id])
        + sender_endpoint_id.encode("utf-8")
        + b":"
        + recipient_endpoint_id.encode("utf-8")
        + b":"
        + message_id.encode("utf-8")
    )


def encrypt_v3_hybrid(
    plaintext: Union[str, bytes],
    recipient_mlkem_pk: bytes,
    recipient_x25519_pk: bytes,
    sender_endpoint_id: str,
    recipient_endpoint_id: str,
    message_id: str,
) -> bytes:
    """Encrypts plaintext into Envelope v3 format using ML-KEM-768 + Ephemeral X25519.

    Envelope structure:
    [1B ver: 0x03][1B scheme: 0x01][32B Eph X25519 PK][1088B ML-KEM CT][12B Nonce][16B Tag][Ciphertext]
    Total fixed header overhead: exactly 1150 bytes.
    """
    if isinstance(plaintext, str):
        plaintext = plaintext.encode("utf-8")

    if len(recipient_mlkem_pk) != MLKEM_EK_BYTES:
        raise ValueError(
            f"Recipient ML-KEM public key must be {MLKEM_EK_BYTES} bytes, got {len(recipient_mlkem_pk)}"
        )
    if len(recipient_x25519_pk) != X25519_PK_BYTES:
        raise ValueError(
            f"Recipient X25519 public key must be {X25519_PK_BYTES} bytes, got {len(recipient_x25519_pk)}"
        )

    # 1. Ephemeral X25519 key generation and exchange
    eph_priv = x25519.X25519PrivateKey.generate()
    eph_pub_bytes = eph_priv.public_key().public_bytes_raw()
    recip_x25519_pub = x25519.X25519PublicKey.from_public_bytes(recipient_x25519_pk)
    ss_x25519 = eph_priv.exchange(recip_x25519_pub)

    # 2. ML-KEM-768 encapsulation
    mlkem_ct, ss_mlkem = mlkem768_encaps(recipient_mlkem_pk)

    # 3. Hybrid session key derivation
    k_session = derive_hybrid_session_key(ss_x25519, ss_mlkem)

    # 4. Construct AAD and encrypt with AES-256-GCM
    aad = construct_aad(sender_endpoint_id, recipient_endpoint_id, message_id)
    nonce = secrets.token_bytes(NONCE_BYTES)

    cipher = AES.new(k_session, AES.MODE_GCM, nonce=nonce)
    cipher.update(aad)
    ciphertext, tag = cipher.encrypt_and_digest(plaintext)

    # 5. Assemble Envelope v3 wire bytes
    envelope = (
        bytes([ENVELOPE_VERSION_V3, PQC_SCHEME_MLKEM768_X25519])
        + eph_pub_bytes
        + mlkem_ct
        + nonce
        + tag
        + ciphertext
    )
    return envelope


def decrypt_envelope(
    envelope: bytes,
    local_mlkem_sk: Optional[bytes] = None,
    local_x25519_sk: Optional[bytes] = None,
    sender_endpoint_id: str = "",
    recipient_endpoint_id: str = "",
    message_id: str = "",
    fallback_key: Optional[Union[str, bytes]] = None,
) -> Tuple[bytes, Dict[str, Any]]:
    """Decrypts an incoming message envelope (Envelope v3 or fallback Envelope v2).

    Inspects byte 0:
    - 0x03: Decrypts via PQC hybrid engine, validates AAD and GCM tag.
      Returns (plaintext, {"envelope_version": 3, "pqc_scheme": "ML-KEM-768+X25519", "pqc_verified": True, ...})
    - 0x02: Decrypts via classical crypto_v2.decrypt_v2_gcm.
      Returns (plaintext, {"envelope_version": 2, "pqc_scheme": "CLASSICAL_AES_256_GCM", "pqc_verified": False, "pqc_downgrade_warning": True})

    Raises:
        InvalidEnvelopeError: If envelope version or structure is invalid.
        AuthenticationError: If ciphertext, tag, or AAD validation fails (tamper detected).
    """
    if not envelope or len(envelope) < 1:
        raise InvalidEnvelopeError("Empty envelope received")

    version = envelope[0]

    if version == ENVELOPE_VERSION_V3:
        if len(envelope) < HEADER_OVERHEAD_BYTES:
            raise InvalidEnvelopeError(
                f"Envelope v3 length {len(envelope)} is shorter than fixed header {HEADER_OVERHEAD_BYTES} bytes"
            )

        scheme_id = envelope[1]
        if scheme_id != PQC_SCHEME_MLKEM768_X25519:
            raise InvalidEnvelopeError(
                f"Unsupported PQC scheme ID 0x{scheme_id:02x} (expected 0x{PQC_SCHEME_MLKEM768_X25519:02x})"
            )

        if not local_mlkem_sk or not local_x25519_sk:
            raise AuthenticationError("Local station private keys unavailable for Envelope v3 decryption")

        # Unpack envelope fields
        eph_x25519_pk = envelope[2:34]
        mlkem_ct = envelope[34:1122]
        nonce = envelope[1122:1134]
        tag = envelope[1134:1150]
        ciphertext = envelope[1150:]

        # Derive X25519 shared secret
        try:
            if isinstance(local_x25519_sk, bytes):
                local_x_priv = x25519.X25519PrivateKey.from_private_bytes(local_x25519_sk)
            else:
                local_x_priv = local_x25519_sk
            eph_x_pub = x25519.X25519PublicKey.from_public_bytes(eph_x25519_pk)
            ss_x25519 = local_x_priv.exchange(eph_x_pub)
        except Exception as e:
            raise AuthenticationError(f"X25519 ECDH exchange failed: {e}")

        # Decapsulate ML-KEM-768 shared secret
        ss_mlkem = mlkem768_decaps(local_mlkem_sk, mlkem_ct)

        # Derive hybrid AES-256 session key
        k_session = derive_hybrid_session_key(ss_x25519, ss_mlkem)

        # Authenticate Associated Data (AAD) & decrypt ciphertext
        aad = construct_aad(sender_endpoint_id, recipient_endpoint_id, message_id)
        cipher = AES.new(k_session, AES.MODE_GCM, nonce=nonce)
        cipher.update(aad)

        try:
            plaintext = cipher.decrypt_and_verify(ciphertext, tag)
        except ValueError as e:
            raise AuthenticationError(
                f"PQC hybrid envelope integrity check failed. Ciphertext or tag tampered: {e}"
            )

        metadata = {
            "envelope_version": 3,
            "pqc_scheme": "ML-KEM-768+X25519",
            "pqc_verified": True,
            "pqc_downgrade_warning": False,
            "eph_x25519_pk": eph_x25519_pk.hex(),
            "kem_ct_bytes": MLKEM_CT_BYTES,
        }
        return plaintext, metadata

    elif version == ENVELOPE_VERSION_V2_GCM:
        # Classical v2 fallback
        key = fallback_key or os.environ.get("SHADOWCOMM_SHARED_SECRET", "default-v2-shared-key-32bytes!")
        try:
            plaintext = decrypt_v2_gcm(envelope, key=key)
        except Exception as e:
            if isinstance(e, CryptoError):
                raise
            raise AuthenticationError(f"Classical v2 decryption failed: {e}")

        metadata = {
            "envelope_version": 2,
            "pqc_scheme": "CLASSICAL_AES_256_GCM",
            "pqc_verified": False,
            "pqc_downgrade_warning": True,
        }
        return plaintext, metadata

    else:
        raise InvalidEnvelopeError(
            f"Unsupported envelope version 0x{version:02x} (expected 0x03 or 0x02)"
        )


class HybridPQCManager:
    """Manager for hybrid PQC operations and envelope framing."""

    @staticmethod
    def encrypt(
        plaintext: Union[str, bytes],
        recipient_mlkem_pk: bytes,
        recipient_x25519_pk: bytes,
        sender_id: str,
        recipient_id: str,
        message_id: str,
    ) -> bytes:
        return encrypt_v3_hybrid(
            plaintext=plaintext,
            recipient_mlkem_pk=recipient_mlkem_pk,
            recipient_x25519_pk=recipient_x25519_pk,
            sender_endpoint_id=sender_id,
            recipient_endpoint_id=recipient_id,
            message_id=message_id,
        )

    @staticmethod
    def decrypt(
        envelope: bytes,
        local_mlkem_sk: Optional[bytes] = None,
        local_x25519_sk: Optional[bytes] = None,
        sender_id: str = "",
        recipient_id: str = "",
        message_id: str = "",
        fallback_key: Optional[Union[str, bytes]] = None,
    ) -> Tuple[bytes, Dict[str, Any]]:
        return decrypt_envelope(
            envelope=envelope,
            local_mlkem_sk=local_mlkem_sk,
            local_x25519_sk=local_x25519_sk,
            sender_endpoint_id=sender_id,
            recipient_endpoint_id=recipient_id,
            message_id=message_id,
            fallback_key=fallback_key,
        )

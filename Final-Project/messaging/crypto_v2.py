import os
import secrets
import hashlib
from typing import Tuple, Optional
from Crypto.Cipher import AES


class CryptoError(Exception):
    """Base exception for cryptographic operations."""
    pass


class AuthenticationError(CryptoError):
    """Raised when authentication tag verification fails (ciphertext tampered)."""
    pass


class InvalidEnvelopeError(CryptoError):
    """Raised when envelope structure or version is malformed."""
    pass


ENVELOPE_VERSION_V2_GCM = 0x02
NONCE_LENGTH_BYTES = 12  # Standard 96-bit nonce for AES-GCM
TAG_LENGTH_BYTES = 16    # 128-bit authentication tag


def derive_key_256(raw_key: str or bytes) -> bytes:
    """
    Derives a standard 256-bit (32-byte) key using SHA-256.
    Ensures input of any length is safely mapped to a valid AES-256 key.
    """
    if isinstance(raw_key, str):
        raw_key = raw_key.encode("utf-8")
    return hashlib.sha256(raw_key).digest()


def encrypt_v2_gcm(plaintext: str or bytes, key: bytes or str, associated_data: Optional[bytes] = None) -> bytes:
    """
    Encrypts plaintext using AES-256 in GCM mode with a cryptographically fresh 96-bit random nonce.
    
    Envelope structure:
    [1 byte version: 0x02] [12 bytes nonce] [16 bytes tag] [variable ciphertext]
    
    Never reuses nonces. A fresh nonce is sampled via secrets.token_bytes(12) on every invocation.
    """
    if isinstance(plaintext, str):
        plaintext = plaintext.encode("utf-8")
    k = derive_key_256(key) if len(key) != 32 else (key.encode("utf-8") if isinstance(key, str) else key)

    nonce = secrets.token_bytes(NONCE_LENGTH_BYTES)
    cipher = AES.new(k, AES.MODE_GCM, nonce=nonce)
    
    if associated_data:
        cipher.update(associated_data)
        
    ciphertext, tag = cipher.encrypt_and_digest(plaintext)
    
    envelope = bytes([ENVELOPE_VERSION_V2_GCM]) + nonce + tag + ciphertext
    return envelope


def decrypt_v2_gcm(envelope: bytes, key: bytes or str, associated_data: Optional[bytes] = None) -> bytes:
    """
    Decrypts a versioned AES-256-GCM envelope and verifies data authenticity.
    
    Raises:
        InvalidEnvelopeError: If envelope is too short or version is unsupported.
        AuthenticationError: If authentication tag fails verification (tampering detected).
    """
    min_len = 1 + NONCE_LENGTH_BYTES + TAG_LENGTH_BYTES
    if len(envelope) < min_len:
        raise InvalidEnvelopeError(f"Envelope length {len(envelope)} is shorter than minimum {min_len} bytes")
        
    version = envelope[0]
    if version != ENVELOPE_VERSION_V2_GCM:
        raise InvalidEnvelopeError(f"Unsupported envelope version 0x{version:02x} (expected 0x{ENVELOPE_VERSION_V2_GCM:02x})")
        
    nonce = envelope[1:1 + NONCE_LENGTH_BYTES]
    tag = envelope[1 + NONCE_LENGTH_BYTES:1 + NONCE_LENGTH_BYTES + TAG_LENGTH_BYTES]
    ciphertext = envelope[1 + NONCE_LENGTH_BYTES + TAG_LENGTH_BYTES:]
    
    k = derive_key_256(key) if len(key) != 32 else (key.encode("utf-8") if isinstance(key, str) else key)
    cipher = AES.new(k, AES.MODE_GCM, nonce=nonce)
    
    if associated_data:
        cipher.update(associated_data)
        
    try:
        plaintext = cipher.decrypt_and_verify(ciphertext, tag)
        return plaintext
    except ValueError as e:
        raise AuthenticationError(f"Message authentication failed: ciphertext or tag corrupted/tampered: {e}")

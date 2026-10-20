import pytest
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    decode_token,
    MessageCrypto,
    UserRole,
)


def test_password_hashing():
    pw = "SuperSecureFieldPassword@2026"
    pw_hash = get_password_hash(pw)
    assert pw_hash != pw
    assert verify_password(pw, pw_hash) is True
    assert verify_password("WrongPassword!", pw_hash) is False


def test_jwt_token_lifecycle():
    claims = {"sub": "tactical_operator", "role": UserRole.OPERATOR.value, "user_id": "usr-123"}
    token = create_access_token(claims)
    decoded = decode_token(token)
    assert decoded["sub"] == "tactical_operator"
    assert decoded["role"] == UserRole.OPERATOR.value
    assert decoded["user_id"] == "usr-123"


def test_message_crypto_aes_gcm():
    key = b"01234567890123456789012345678901"  # 32 bytes
    plaintext = "CLASSIFIED_INCIDENT_COORDINATES: 28.6139N 77.2090E"
    aad = b"message-id-998877"

    encrypted = MessageCrypto.encrypt(plaintext, key, associated_data=aad)
    assert "ciphertext_b64" in encrypted
    assert "nonce_b64" in encrypted
    assert encrypted["algorithm"] == "AES-256-GCM"

    decrypted = MessageCrypto.decrypt(
        encrypted["ciphertext_b64"],
        encrypted["nonce_b64"],
        key,
        associated_data=aad,
    )
    assert decrypted == plaintext

    # Tampering with AAD must fail authentication
    with pytest.raises(Exception):
        MessageCrypto.decrypt(
            encrypted["ciphertext_b64"],
            encrypted["nonce_b64"],
            key,
            associated_data=b"tampered-aad",
        )

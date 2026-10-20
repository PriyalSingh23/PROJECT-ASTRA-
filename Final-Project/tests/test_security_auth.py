import os
import pytest
from datetime import datetime, timezone, timedelta
from messaging.db import init_db, get_db_session
from messaging.models import User, UserSession, SecurityAuditLog
from messaging.auth_service import AuthService
from messaging.crypto_v2 import (
    encrypt_v2_gcm,
    decrypt_v2_gcm,
    AuthenticationError,
    InvalidEnvelopeError,
)


@pytest.fixture
def auth_db(tmp_path):
    db_file = tmp_path / "test_auth.db"
    db_path = str(db_file)
    init_db(db_path)
    return db_path


# ==================== CRYPTOGRAPHIC ENVELOPE TESTS ====================

def test_aes_256_gcm_roundtrip():
    key = "secret-key-passphrase-32bytes!!"
    plaintext = "CRITICAL SITREP: Evacuation route alpha is open."
    
    envelope = encrypt_v2_gcm(plaintext, key)
    assert envelope[0] == 0x02  # Version 2 GCM
    assert len(envelope) > 1 + 12 + 16  # Version + Nonce + Tag + Ciphertext
    
    decrypted = decrypt_v2_gcm(envelope, key)
    assert decrypted.decode("utf-8") == plaintext


def test_aes_256_gcm_unique_nonces():
    key = "master-aes-key-for-testing-0012"
    plaintext = "Repeat identical string"
    
    env1 = encrypt_v2_gcm(plaintext, key)
    env2 = encrypt_v2_gcm(plaintext, key)
    
    # Nonces (bytes 1..13) must differ
    nonce1 = env1[1:13]
    nonce2 = env2[1:13]
    assert nonce1 != nonce2, "Nonces must be fresh random per message!"
    assert env1 != env2, "Ciphertexts must differ due to distinct nonces!"


def test_aes_256_gcm_tamper_detection():
    key = "master-aes-key-for-testing-0012"
    envelope = bytearray(encrypt_v2_gcm("Sensitive coordinates: 34.05,-118.25", key))
    
    # Tamper with the ciphertext (last byte)
    envelope[-1] ^= 0x01
    
    with pytest.raises(AuthenticationError):
        decrypt_v2_gcm(bytes(envelope), key)


def test_aes_256_gcm_wrong_key():
    key1 = "correct-key-32bytes-long-secret!"
    key2 = "wrong-key-different-secret-pass!"
    
    envelope = encrypt_v2_gcm("Target message", key1)
    
    with pytest.raises(AuthenticationError):
        decrypt_v2_gcm(envelope, key2)


def test_aes_256_gcm_malformed_envelope():
    key = "some-key"
    with pytest.raises(InvalidEnvelopeError):
        decrypt_v2_gcm(b"short", key)
        
    invalid_ver = b"\x01" + b"\x00" * 30
    with pytest.raises(InvalidEnvelopeError):
        decrypt_v2_gcm(invalid_ver, key)


# ==================== AUTHENTICATION & ACCESS CONTROL TESTS ====================

def test_user_creation_and_password_hashing(auth_db):
    with get_db_session(auth_db) as session:
        user = AuthService.create_user(session, "field_lead", "SuperSecretPass123!", role="OPERATOR")
        assert user.username == "field_lead"
        assert user.role == "OPERATOR"
        assert user.password_hash != "SuperSecretPass123!"
        assert user.check_password("SuperSecretPass123!")
        assert not user.check_password("WrongPassword")


def test_user_authentication_flow(auth_db):
    with get_db_session(auth_db) as session:
        AuthService.create_user(session, "dispatcher", "DispatcH123!", role="OPERATOR")
        
        # Successful login
        user, user_sess, err = AuthService.authenticate_user(session, "dispatcher", "DispatcH123!", ip_address="192.168.1.10")
        assert err is None
        assert user is not None
        assert user_sess is not None
        assert user_sess.is_valid()
        
        # Validate session
        validated_user = AuthService.validate_session(session, user_sess.session_token)
        assert validated_user is not None
        assert validated_user.username == "dispatcher"
        
        # Logout
        logged_out = AuthService.revoke_session(session, user_sess.session_token)
        assert logged_out is True
        
        # Validate after logout fails
        assert AuthService.validate_session(session, user_sess.session_token) is None


def test_brute_force_lockout(auth_db):
    with get_db_session(auth_db) as session:
        AuthService.create_user(session, "patrol_01", "SecurePass123!", role="OPERATOR")
        
        # 4 failed attempts should not lock account
        for i in range(4):
            u, s, err = AuthService.authenticate_user(session, "patrol_01", "bad_pass")
            assert u is None
            assert "locked" not in err.lower()
            
        user = session.query(User).filter_by(username="patrol_01").first()
        assert not user.is_locked()
        assert user.failed_login_attempts == 4
        
        # 5th failed attempt triggers lockout
        u, s, err = AuthService.authenticate_user(session, "patrol_01", "bad_pass")
        assert u is None
        assert "locked" in err.lower()
        
        user = session.query(User).filter_by(username="patrol_01").first()
        assert user.is_locked()
        
        # Even correct password is now rejected while locked
        u, s, err = AuthService.authenticate_user(session, "patrol_01", "SecurePass123!")
        assert u is None
        assert "locked" in err.lower()


def test_security_audit_logging(auth_db):
    with get_db_session(auth_db) as session:
        AuthService.create_user(session, "sec_officer", "SecOfficerPass1!", role="ADMINISTRATOR")
        AuthService.authenticate_user(session, "sec_officer", "SecOfficerPass1!", ip_address="10.0.0.5")
        AuthService.authenticate_user(session, "sec_officer", "wrong_pass", ip_address="10.0.0.5")
        
        logs = session.query(SecurityAuditLog).order_by(SecurityAuditLog.timestamp.desc()).all()
        event_types = [log.event_type for log in logs]
        
        assert "USER_CREATED" in event_types
        assert "LOGIN_SUCCESS" in event_types
        assert "LOGIN_FAILED" in event_types

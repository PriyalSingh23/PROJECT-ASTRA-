import os
import pytest
from datetime import datetime, timezone, timedelta
from messaging.db import init_db, get_db_session
from messaging.models import User, UserSession, SecurityAuditLog
from messaging.auth_service import AuthService
from messaging.security_config import (
    DEMO_ADMIN_PASSWORD,
    DEMO_OPERATOR_PASSWORD,
    DEMO_SECRET_KEY,
    DEMO_TOKEN_ENDPOINT_A,
    DEMO_TOKEN_ENDPOINT_B,
    ensure_legacy_component_not_production,
    get_app_secret_key,
    get_endpoint_token,
    get_seed_password,
)
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



# ==================== PRODUCTION SECRET CONFIGURATION ====================

def test_production_mode_requires_a_configured_app_secret(monkeypatch):
    monkeypatch.setenv("SHADOWCOMM_ENV", "production")
    monkeypatch.delenv("SHADOWCOMM_SECRET_KEY", raising=False)

    with pytest.raises(RuntimeError, match="SHADOWCOMM_SECRET_KEY is required"):
        get_app_secret_key()


@pytest.mark.parametrize(
    "secret",
    [
        DEMO_SECRET_KEY,
        "generate_a_random_32_byte_hex_string_here",
        "too-short",
    ],
)
def test_production_mode_rejects_demo_placeholder_and_short_secrets(monkeypatch, secret):
    monkeypatch.setenv("SHADOWCOMM_ENV", "production")
    monkeypatch.setenv("SHADOWCOMM_SECRET_KEY", secret)

    with pytest.raises(RuntimeError):
        get_app_secret_key()


def test_production_mode_accepts_a_long_unique_app_secret(monkeypatch):
    monkeypatch.setenv("SHADOWCOMM_ENV", "production")
    monkeypatch.setenv("SHADOWCOMM_SECRET_KEY", "unique-runtime-secret-" + ("a7" * 24))

    assert len(get_app_secret_key()) >= 32


def test_production_mode_requires_configured_endpoint_tokens(monkeypatch):
    monkeypatch.setenv("SHADOWCOMM_ENV", "production")
    monkeypatch.delenv("SHADOWCOMM_TOKEN_ENDPOINT_A", raising=False)

    with pytest.raises(RuntimeError, match="SHADOWCOMM_TOKEN_ENDPOINT_A is required"):
        get_endpoint_token("SHADOWCOMM_TOKEN_ENDPOINT_A", DEMO_TOKEN_ENDPOINT_A)

    monkeypatch.setenv("SHADOWCOMM_TOKEN_ENDPOINT_A", "replace_with_a_real_token")
    with pytest.raises(RuntimeError):
        get_endpoint_token("SHADOWCOMM_TOKEN_ENDPOINT_A", DEMO_TOKEN_ENDPOINT_A)

    monkeypatch.setenv("SHADOWCOMM_TOKEN_ENDPOINT_A", "e4" * 32)
    assert len(get_endpoint_token("SHADOWCOMM_TOKEN_ENDPOINT_A", DEMO_TOKEN_ENDPOINT_A)) == 64


def test_production_mode_requires_initial_passwords_for_a_new_database(monkeypatch):
    monkeypatch.setenv("SHADOWCOMM_ENV", "production")
    monkeypatch.delenv("SHADOWCOMM_ADMIN_PASSWORD", raising=False)

    with pytest.raises(RuntimeError, match="SHADOWCOMM_ADMIN_PASSWORD is required"):
        get_seed_password("SHADOWCOMM_ADMIN_PASSWORD", DEMO_ADMIN_PASSWORD)

    monkeypatch.setenv("SHADOWCOMM_ADMIN_PASSWORD", DEMO_ADMIN_PASSWORD)
    with pytest.raises(RuntimeError):
        get_seed_password("SHADOWCOMM_ADMIN_PASSWORD", DEMO_ADMIN_PASSWORD)

    monkeypatch.setenv("SHADOWCOMM_ADMIN_PASSWORD", "field-admin-" + ("G7" * 16))
    assert len(get_seed_password("SHADOWCOMM_ADMIN_PASSWORD", DEMO_ADMIN_PASSWORD)) >= 16


def test_known_demo_users_block_production_startup(auth_db, monkeypatch):
    monkeypatch.setenv("SHADOWCOMM_ENV", "production")

    with get_db_session(auth_db) as session:
        with pytest.raises(RuntimeError, match="known demo password"):
            AuthService.seed_default_users(session)


def test_existing_endpoint_demo_tokens_block_production_startup(auth_db, monkeypatch):
    monkeypatch.setenv("SHADOWCOMM_ENV", "production")
    monkeypatch.setenv("SHADOWCOMM_TOKEN_ENDPOINT_A", "A9" * 32)
    monkeypatch.setenv("SHADOWCOMM_TOKEN_ENDPOINT_B", "B8" * 32)

    # Existing test DB contains the old development tokens; production startup
    # must require an explicit credential rotation rather than silently changing DB state.
    with pytest.raises(RuntimeError, match="Stored endpoint-a token does not match"):
        init_db(auth_db)


def test_legacy_fixed_counter_lpi_app_is_blocked_in_production(monkeypatch):
    monkeypatch.setenv("SHADOWCOMM_ENV", "production")

    with pytest.raises(RuntimeError, match="fixed initial counter"):
        ensure_legacy_component_not_production(
            "Final-Project/app.py",
            "legacy AES-CTR uses a fixed initial counter",
        )


def test_development_mode_fallback_remains_explicit_and_compatible(monkeypatch, caplog):
    import logging
    import messaging.security_config as security_config

    monkeypatch.delenv("SHADOWCOMM_ENV", raising=False)
    monkeypatch.delenv("SHADOWCOMM_SECRET_KEY", raising=False)
    monkeypatch.setattr(security_config, "_WARNED_NAMES", set())
    caplog.set_level(logging.WARNING, logger="messaging.security_config")

    assert get_app_secret_key() == DEMO_SECRET_KEY
    assert any(
        "SECURITY WARNING" in record.message and "SHADOWCOMM_SECRET_KEY" in record.message
        for record in caplog.records
    )

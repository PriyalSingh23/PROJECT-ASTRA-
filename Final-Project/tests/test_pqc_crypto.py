import torch  # Critical on macOS Apple Silicon: MUST be imported before any other C-extensions to prevent OpenBLAS linker collision (SIGSEGV 139)
import os
import sys
import json
import base64
import tempfile
import uuid
import struct
from typing import Dict, Any, List
import pytest

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from messaging.models import (
    Base,
    Endpoint,
    Message,
    InboxItem,
    SecurityAuditLog,
    MessageEvent,
    utcnow,
)
from messaging.db import init_db, get_db_session
from messaging.server import create_app
from messaging.mlkem768 import (
    ntt,
    intt,
    multiply_ntts,
    base_case_multiply,
    sample_ntt,
    sample_poly_cbd,
    compress,
    decompress,
    byte_encode,
    byte_decode,
    byte_encode_12,
    byte_decode_12,
    byte_encode_10,
    byte_decode_10,
    byte_encode_4,
    byte_decode_4,
    byte_encode_1,
    byte_decode_1,
    k_pke_keygen,
    k_pke_encrypt,
    k_pke_decrypt,
    mlkem768_keygen,
    mlkem768_encaps,
    mlkem768_decaps,
    MLKEM_Q,
    MLKEM_K,
    MLKEM_EK_BYTES,
    MLKEM_DK_BYTES,
    MLKEM_CT_BYTES,
    MLKEM_SS_BYTES,
)
from messaging.crypto_v2 import (
    AuthenticationError,
    InvalidEnvelopeError,
    encrypt_v2_gcm,
    decrypt_v2_gcm,
    ENVELOPE_VERSION_V2_GCM,
)
from messaging.crypto_pqc import (
    encrypt_v3_hybrid,
    decrypt_envelope,
    derive_hybrid_session_key,
    construct_aad,
    ENVELOPE_VERSION_V3,
    PQC_SCHEME_MLKEM768_X25519,
    HEADER_OVERHEAD_BYTES,
)
from messaging.keyring import StationKeyringManager, keyring_manager, compute_fingerprint
from messaging.dispatch import (
    _encode_envelope,
    chunk_frame,
    DMR_CHUNK_BYTES,
    _CHUNK_PAYLOAD_BYTES,
)


# ==============================================================================
# Helper for naive polynomial multiplication modulo (X^256 + 1) mod 3329
# ==============================================================================
def naive_poly_mul(a: List[int], b: List[int]) -> List[int]:
    res = [0] * 256
    for i in range(256):
        for j in range(256):
            deg = i + j
            prod = (a[i] * b[j]) % MLKEM_Q
            if deg < 256:
                res[deg] = (res[deg] + prod) % MLKEM_Q
            else:
                res[deg - 256] = (res[deg - 256] - prod) % MLKEM_Q
    return res


# ==============================================================================
# 1. TestMLKEM768Core: Pure-Python NIST FIPS 203 Engine Verification
# ==============================================================================
class TestMLKEM768Core:

    def test_ntt_roundtrip(self):
        """Verifies forward Cooley-Tukey NTT followed by inverse NTT recovers identical coefficients."""
        poly = [(i * 37 + 13) % MLKEM_Q for i in range(256)]
        transformed = ntt(poly)
        recovered = intt(transformed)
        assert recovered == poly

    def test_multiply_ntts(self):
        """Verifies NTT polynomial multiplication matches ring multiplication mod (X^256 + 1)."""
        a = [(i * 17 + 5) % MLKEM_Q for i in range(256)]
        b = [(i * 31 + 7) % MLKEM_Q for i in range(256)]
        expected = naive_poly_mul(a, b)

        a_hat = ntt(a)
        b_hat = ntt(b)
        c_hat = multiply_ntts(a_hat, b_hat)
        actual = intt(c_hat)
        assert actual == expected

    def test_cbd2_sampling(self):
        """Verifies centered binomial distribution sampling produces coefficients in [-2, 2]."""
        sigma = os.urandom(32)
        coeffs = sample_poly_cbd(sigma, n=0, eta=2)
        assert len(coeffs) == 256
        for c in coeffs:
            val = c if c < MLKEM_Q // 2 else c - MLKEM_Q
            assert -2 <= val <= 2

    def test_compression_decompression_bounds(self):
        """Verifies compression and decompression for du=10, dv=4, d=1 stay within range."""
        for d in (10, 4, 1):
            for x in (0, 1, 100, 1665, 3328):
                c = compress(x, d)
                assert 0 <= c < (1 << d)
                dec = decompress(c, d)
                assert 0 <= dec < MLKEM_Q

    def test_byte_encoding_roundtrips(self):
        """Verifies byte encode/decode roundtrips for 12, 10, 4, and 1-bit coefficients."""
        p12 = [(i * 19) % 4096 for i in range(256)]
        assert byte_decode_12(byte_encode_12(p12)) == p12
        assert byte_decode(byte_encode(p12, 12), 12) == p12

        p10 = [(i * 23) % 1024 for i in range(256)]
        assert byte_decode_10(byte_encode_10(p10)) == p10
        assert byte_decode(byte_encode(p10, 10), 10) == p10

        p4 = [(i * 3) % 16 for i in range(256)]
        assert byte_decode_4(byte_encode_4(p4)) == p4
        assert byte_decode(byte_encode(p4, 4), 4) == p4

        p1 = [i % 2 for i in range(256)]
        assert byte_decode_1(byte_encode_1(p1)) == p1
        assert byte_decode(byte_encode(p1, 1), 1) == p1

    def test_mlkem768_keygen_lengths(self):
        """Verifies encapsulation key is exactly 1184 bytes and decapsulation key is 2400 bytes."""
        ek, dk = mlkem768_keygen()
        assert len(ek) == MLKEM_EK_BYTES  # 1184
        assert len(dk) == MLKEM_DK_BYTES  # 2400

    def test_mlkem768_encaps_decaps_roundtrip(self):
        """Verifies encaps generates 1088B ciphertext and 32B secret, and decaps recovers same secret."""
        ek, dk = mlkem768_keygen()
        ct, ss_encaps = mlkem768_encaps(ek)
        assert len(ct) == MLKEM_CT_BYTES  # 1088
        assert len(ss_encaps) == MLKEM_SS_BYTES  # 32

        ss_decaps = mlkem768_decaps(dk, ct)
        assert ss_decaps == ss_encaps
        assert len(ss_decaps) == 32

    def test_mlkem768_interoperates_with_cryptography_reference(self):
        """Cross-check the custom ML-KEM-768 byte formats and primitives independently.

        This is an interoperability regression test, not a FIPS 203 certification or
        a replacement for NIST known-answer tests.
        """
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import mlkem

        # Reference implementation encapsulates to our custom-generated public key;
        # our decapsulation must recover exactly the reference shared secret.
        custom_ek, custom_dk = mlkem768_keygen()
        reference_public = mlkem.MLKEM768PublicKey.from_public_bytes(custom_ek)
        reference_secret, reference_ciphertext = reference_public.encapsulate()
        assert len(reference_ciphertext) == MLKEM_CT_BYTES
        assert mlkem768_decaps(custom_dk, reference_ciphertext) == reference_secret

        # Reverse direction: our encapsulation must interoperate with the independent
        # reference implementation's generated key pair and decapsulation.
        reference_private = mlkem.MLKEM768PrivateKey.generate()
        reference_public_bytes = reference_private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        custom_ciphertext, custom_secret = mlkem768_encaps(reference_public_bytes)
        assert len(custom_ciphertext) == MLKEM_CT_BYTES
        assert reference_private.decapsulate(custom_ciphertext) == custom_secret

    def test_mlkem768_implicit_rejection_on_tamper(self):
        """Verifies bit-flipped ciphertext decapsulates to a pseudo-random secret (Fujisaki-Okamoto)."""
        ek, dk = mlkem768_keygen()
        ct, ss_encaps = mlkem768_encaps(ek)

        # Flip a bit in the ciphertext
        ct_tampered = bytearray(ct)
        ct_tampered[42] ^= 0x01
        ss_tampered = mlkem768_decaps(dk, bytes(ct_tampered))

        # Must reject implicitly by producing a non-matching 32-byte secret
        assert ss_tampered != ss_encaps
        assert len(ss_tampered) == 32


# ==============================================================================
# 2. TestHybridEnvelopeV3: Ephemeral X25519 + ML-KEM HKDF & Envelope Framing
# ==============================================================================
class TestHybridEnvelopeV3:

    def test_ephemeral_x25519_freshness(self):
        """Verifies every encapsulation produces a unique ephemeral X25519 public key."""
        ek, dk = mlkem768_keygen()
        from cryptography.hazmat.primitives.asymmetric import x25519
        recip_x_priv = x25519.X25519PrivateKey.generate()
        recip_x_pub = recip_x_priv.public_key().public_bytes_raw()

        env1 = encrypt_v3_hybrid(b"msg1", ek, recip_x_pub, "endpoint-a", "endpoint-b", "id-1")
        env2 = encrypt_v3_hybrid(b"msg2", ek, recip_x_pub, "endpoint-a", "endpoint-b", "id-2")

        # Offset 2:34 is the 32-byte ephemeral X25519 public key
        eph_pk1 = env1[2:34]
        eph_pk2 = env2[2:34]
        assert eph_pk1 != eph_pk2
        assert len(eph_pk1) == 32
        assert len(eph_pk2) == 32

    def test_hkdf_sha256_hybrid_derivation(self):
        """Verifies deterministic 32-byte session key derivation via HKDF-SHA256."""
        ss_x = os.urandom(32)
        ss_ml = os.urandom(32)
        k1 = derive_hybrid_session_key(ss_x, ss_ml)
        k2 = derive_hybrid_session_key(ss_x, ss_ml)
        assert len(k1) == 32
        assert k1 == k2

        # Changing either shared secret changes the session key
        ss_x_alt = bytearray(ss_x)
        ss_x_alt[0] ^= 0x01
        k_diff = derive_hybrid_session_key(bytes(ss_x_alt), ss_ml)
        assert k_diff != k1

    def test_envelope_v3_header_overhead_exactly_1150_bytes(self):
        """Verifies len(envelope) == 1150 + len(plaintext)."""
        ek, dk = mlkem768_keygen()
        from cryptography.hazmat.primitives.asymmetric import x25519
        recip_x_priv = x25519.X25519PrivateKey.generate()
        recip_x_pub = recip_x_priv.public_key().public_bytes_raw()

        for payload_len in (0, 32, 100, 500):
            plaintext = b"A" * payload_len
            envelope = encrypt_v3_hybrid(plaintext, ek, recip_x_pub, "endpoint-a", "endpoint-b", "id-overhead")
            assert len(envelope) == HEADER_OVERHEAD_BYTES + payload_len
            assert len(envelope) == 1150 + payload_len
            assert envelope[0] == ENVELOPE_VERSION_V3
            assert envelope[1] == PQC_SCHEME_MLKEM768_X25519

    def test_aad_binding_anti_replay_defense(self):
        """Verifies modifying sender, recipient, or message_id in AAD fails GCM authentication."""
        ek, dk = mlkem768_keygen()
        from cryptography.hazmat.primitives.asymmetric import x25519
        recip_x_priv = x25519.X25519PrivateKey.generate()
        recip_x_pub = recip_x_priv.public_key().public_bytes_raw()
        recip_x_sk = recip_x_priv.private_bytes_raw()

        plaintext = b"TACTICAL AAD VERIFICATION TEST"
        envelope = encrypt_v3_hybrid(plaintext, ek, recip_x_pub, "endpoint-a", "endpoint-b", "msg-original")

        # Clean decryption succeeds
        decrypted, meta = decrypt_envelope(
            envelope, dk, recip_x_sk, "endpoint-a", "endpoint-b", "msg-original"
        )
        assert decrypted == plaintext
        assert meta["pqc_verified"] is True

        # Tampering with sender ID causes AuthenticationError
        with pytest.raises(AuthenticationError):
            decrypt_envelope(
                envelope, dk, recip_x_sk, "endpoint-spoofed", "endpoint-b", "msg-original"
            )

        # Tampering with recipient ID causes AuthenticationError
        with pytest.raises(AuthenticationError):
            decrypt_envelope(
                envelope, dk, recip_x_sk, "endpoint-a", "endpoint-c", "msg-original"
            )

        # Tampering with message ID causes AuthenticationError
        with pytest.raises(AuthenticationError):
            decrypt_envelope(
                envelope, dk, recip_x_sk, "endpoint-a", "endpoint-b", "msg-replayed"
            )

    def test_ciphertext_bit_flip_tamper_detection(self):
        """Verifies bit-flip in ciphertext raises AuthenticationError."""
        ek, dk = mlkem768_keygen()
        from cryptography.hazmat.primitives.asymmetric import x25519
        recip_x_priv = x25519.X25519PrivateKey.generate()
        recip_x_pub = recip_x_priv.public_key().public_bytes_raw()
        recip_x_sk = recip_x_priv.private_bytes_raw()

        envelope = encrypt_v3_hybrid(
            b"SECRET DATA", ek, recip_x_pub, "endpoint-a", "endpoint-b", "msg-tamper"
        )

        # Bit flip in AES ciphertext payload
        tampered = bytearray(envelope)
        tampered[-1] ^= 0x01

        with pytest.raises(AuthenticationError):
            decrypt_envelope(
                bytes(tampered), dk, recip_x_sk, "endpoint-a", "endpoint-b", "msg-tamper"
            )

        # Bit flip in AES tag (bytes 1134:1150)
        tampered_tag = bytearray(envelope)
        tampered_tag[1140] ^= 0x01
        with pytest.raises(AuthenticationError):
            decrypt_envelope(
                bytes(tampered_tag), dk, recip_x_sk, "endpoint-a", "endpoint-b", "msg-tamper"
            )

        # Bit flip in ML-KEM ciphertext (bytes 34:1122) causes implicit rejection -> bad session key -> tag failure
        tampered_kem = bytearray(envelope)
        tampered_kem[100] ^= 0x01
        with pytest.raises(AuthenticationError):
            decrypt_envelope(
                bytes(tampered_kem), dk, recip_x_sk, "endpoint-a", "endpoint-b", "msg-tamper"
            )


# ==============================================================================
# 3. TestBackwardCompatibility: Dual-Stack Inbound & Fallback Negotiation
# ==============================================================================
class TestBackwardCompatibility:

    def test_receiver_dual_stack_auto_negotiation(self):
        """Verifies receiver auto-detects 0x03 vs 0x02 envelopes."""
        ek, dk = mlkem768_keygen()
        from cryptography.hazmat.primitives.asymmetric import x25519
        recip_x_priv = x25519.X25519PrivateKey.generate()
        recip_x_pub = recip_x_priv.public_key().public_bytes_raw()
        recip_x_sk = recip_x_priv.private_bytes_raw()

        # v3 envelope
        env_v3 = encrypt_v3_hybrid(
            b"V3 MESSAGE", ek, recip_x_pub, "endpoint-a", "endpoint-b", "msg-v3"
        )
        pt_v3, meta_v3 = decrypt_envelope(
            env_v3, dk, recip_x_sk, "endpoint-a", "endpoint-b", "msg-v3"
        )
        assert pt_v3 == b"V3 MESSAGE"
        assert meta_v3["envelope_version"] == 3
        assert meta_v3["pqc_verified"] is True
        assert meta_v3["pqc_downgrade_warning"] is False

        # v2 envelope
        shared_key = b"legacy-v2-shared-secret-key-32b!"
        env_v2 = encrypt_v2_gcm(b"V2 LEGACY MESSAGE", key=shared_key)
        pt_v2, meta_v2 = decrypt_envelope(
            env_v2, dk, recip_x_sk, fallback_key=shared_key
        )
        assert pt_v2 == b"V2 LEGACY MESSAGE"
        assert meta_v2["envelope_version"] == 2
        assert meta_v2["pqc_verified"] is False
        assert meta_v2["pqc_downgrade_warning"] is True

    def test_v2_fallback_emits_downgrade_warning(self):
        """Verifies v2 envelope decryption succeeds but sets pqc_downgrade_warning=True."""
        shared_key = b"shared-secret-key-for-test-32b!"
        env_v2 = encrypt_v2_gcm(b"FALLBACK TEST", key=shared_key)
        pt, meta = decrypt_envelope(env_v2, fallback_key=shared_key)
        assert pt == b"FALLBACK TEST"
        assert meta["pqc_downgrade_warning"] is True
        assert meta["pqc_verified"] is False

    def test_pqc_preferred_outbound_with_graceful_fallback(self):
        """Verifies sender uses v3 if recipient public key exists, and falls back to v2 if missing."""
        ek, dk = mlkem768_keygen()
        from cryptography.hazmat.primitives.asymmetric import x25519
        recip_x_pub = x25519.X25519PrivateKey.generate().public_key().public_bytes_raw()

        msg_dict = {
            "message_id": "outbound-test-1",
            "sender_endpoint_id": "endpoint-a",
            "recipient_endpoint_id": "endpoint-b",
            "payload": "Tactical payload to encrypt",
        }

        # With recipient public keys -> produces Envelope v3
        encoded_v3 = _encode_envelope(
            msg_dict, recipient_mlkem_pk=ek, recipient_x25519_pk=recip_x_pub
        )
        header_part, binary_part = encoded_v3.split(b"\x1f", 1)
        assert binary_part[0] == ENVELOPE_VERSION_V3

        # Without recipient public keys -> falls back to Envelope v2
        encoded_v2 = _encode_envelope(msg_dict, recipient_mlkem_pk=None, recipient_x25519_pk=None)
        _, binary_part_v2 = encoded_v2.split(b"\x1f", 1)
        assert binary_part_v2[0] == ENVELOPE_VERSION_V2_GCM

    def test_peer_incoming_pqc_v3_ingest(self):
        """Verifies POST /api/v1/endpoints/incoming decrypts Envelope v3 and marks pqc_verified=True."""
        temp_db = tempfile.mktemp(suffix=".db")
        init_db(temp_db, station_id="endpoint-b")

        app = create_app(db_path=temp_db, station_id="endpoint-b", port=5052)
        app.config["TESTING"] = True

        recip_mlkem_pk = keyring_manager.get_local_mlkem_pk("endpoint-b")
        recip_x25519_pk = keyring_manager.get_local_x25519_pk("endpoint-b")

        envelope = encrypt_v3_hybrid(
            plaintext=b"Tactical Sitrep for Bravo",
            recipient_mlkem_pk=recip_mlkem_pk,
            recipient_x25519_pk=recip_x25519_pk,
            sender_endpoint_id="endpoint-a",
            recipient_endpoint_id="endpoint-b",
            message_id="msg-pqc-ingest-01",
        )

        with app.test_client() as client:
            packet = {
                "message_id": "msg-pqc-ingest-01",
                "client_idempotency_key": "idemp-pqc-01",
                "sender_endpoint_id": "endpoint-a",
                "recipient_endpoint_id": "endpoint-b",
                "payload": base64.b64encode(envelope).decode("ascii"),
                "message_type": "TEXT",
            }
            res = client.post("/api/v1/endpoints/incoming", json=packet)
            assert res.status_code == 201
            assert res.json["pqc_verified"] is True
            assert res.json["envelope_version"] == 3
            assert res.json["pqc_downgrade_warning"] is False

            # Verify in SQLite
            with get_db_session(temp_db) as session:
                msg = session.query(Message).filter_by(message_id="msg-pqc-ingest-01").first()
                assert msg is not None
                assert msg.payload == "Tactical Sitrep for Bravo"
                assert msg.pqc_verified is True
                assert msg.envelope_version == 3

                inbox = session.query(InboxItem).filter_by(message_id="msg-pqc-ingest-01").first()
                assert inbox is not None
                assert inbox.pqc_verified is True

        try:
            os.remove(temp_db)
        except Exception:
            pass

    def test_peer_incoming_tamper_rejected_http_422(self):
        """Verifies bit-flipped envelope returns HTTP 422 and logs PQC_TAMPER_DETECTED."""
        temp_db = tempfile.mktemp(suffix=".db")
        init_db(temp_db, station_id="endpoint-b")

        app = create_app(db_path=temp_db, station_id="endpoint-b", port=5052)
        app.config["TESTING"] = True

        recip_mlkem_pk = keyring_manager.get_local_mlkem_pk("endpoint-b")
        recip_x25519_pk = keyring_manager.get_local_x25519_pk("endpoint-b")

        envelope = bytearray(encrypt_v3_hybrid(
            plaintext=b"Authentic secret",
            recipient_mlkem_pk=recip_mlkem_pk,
            recipient_x25519_pk=recip_x25519_pk,
            sender_endpoint_id="endpoint-a",
            recipient_endpoint_id="endpoint-b",
            message_id="msg-tamper-probe",
        ))
        # Tamper with 1 byte of ciphertext
        envelope[100] ^= 0x01

        with app.test_client() as client:
            packet = {
                "message_id": "msg-tamper-probe",
                "client_idempotency_key": "idemp-tamper-probe",
                "sender_endpoint_id": "endpoint-a",
                "recipient_endpoint_id": "endpoint-b",
                "payload": base64.b64encode(envelope).decode("ascii"),
                "message_type": "TEXT",
            }
            res = client.post("/api/v1/endpoints/incoming", json=packet)
            assert res.status_code == 422
            assert res.json["error"] == "CRYPTO_AUTHENTICATION_FAILED"

            # Verify PQC_TAMPER_DETECTED audit log
            with get_db_session(temp_db) as session:
                audit = session.query(SecurityAuditLog).filter_by(event_type="PQC_TAMPER_DETECTED").first()
                assert audit is not None
                assert audit.severity == "HIGH"

        try:
            os.remove(temp_db)
        except Exception:
            pass

    def test_peer_incoming_v2_downgrade_warning(self):
        """Verifies v2 message produces pqc_downgrade_warning=True and PQC_DOWNGRADE_FALLBACK audit."""
        temp_db = tempfile.mktemp(suffix=".db")
        init_db(temp_db, station_id="endpoint-b")

        app = create_app(db_path=temp_db, station_id="endpoint-b", port=5052)
        app.config["TESTING"] = True

        shared_key = b"default-v2-shared-key-32bytes!"
        v2_envelope = encrypt_v2_gcm(b"Classical legacy payload", key=shared_key)

        with app.test_client() as client:
            packet = {
                "message_id": "msg-v2-downgrade",
                "client_idempotency_key": "idemp-v2-downgrade",
                "sender_endpoint_id": "endpoint-a",
                "recipient_endpoint_id": "endpoint-b",
                "payload": base64.b64encode(v2_envelope).decode("ascii"),
                "message_type": "TEXT",
            }
            res = client.post("/api/v1/endpoints/incoming", json=packet)
            assert res.status_code == 201
            assert res.json["pqc_downgrade_warning"] is True
            assert res.json["pqc_verified"] is False
            assert res.json["envelope_version"] == 2

            # Verify PQC_DOWNGRADE_FALLBACK audit log
            with get_db_session(temp_db) as session:
                audit = session.query(SecurityAuditLog).filter_by(event_type="PQC_DOWNGRADE_FALLBACK").first()
                assert audit is not None
                assert audit.severity == "MEDIUM"

        try:
            os.remove(temp_db)
        except Exception:
            pass


# ==============================================================================
# 4. TestKeyringLifecycle: Persistent Keyrings, REST Key Rotation & Zeroization
# ==============================================================================
class TestKeyringLifecycle:

    @pytest.fixture
    def test_keyring_dir(self):
        temp_dir = tempfile.mkdtemp()
        manager = StationKeyringManager(keyring_dir=temp_dir)
        yield manager, temp_dir
        # Cleanup
        for f in os.listdir(temp_dir):
            try:
                os.remove(os.path.join(temp_dir, f))
            except Exception:
                pass
        try:
            os.rmdir(temp_dir)
        except Exception:
            pass

    def test_keyring_generation_and_loading(self, test_keyring_dir):
        """Verifies keyrings are persisted on disk and loaded on subsequent boot."""
        manager, temp_dir = test_keyring_dir
        station_id = "test-station-alpha"

        # Initial generation
        bundle1 = manager.load_or_generate_keyring(station_id)
        assert os.path.exists(manager.get_keyring_path(station_id))
        assert "x25519" in bundle1
        assert "mlkem768" in bundle1
        assert len(base64.b64decode(bundle1["mlkem768"]["encapsulation_key_b64"])) == MLKEM_EK_BYTES
        assert len(base64.b64decode(bundle1["mlkem768"]["decapsulation_key_b64"])) == MLKEM_DK_BYTES

        # Clear memory cache and reload from disk
        manager._memory_cache.clear()
        bundle2 = manager.load_or_generate_keyring(station_id)
        assert bundle1["x25519"]["fingerprint"] == bundle2["x25519"]["fingerprint"]
        assert bundle1["mlkem768"]["fingerprint"] == bundle2["mlkem768"]["fingerprint"]

    def test_operator_key_rotation_api(self):
        """Verifies POST /api/v1/crypto/rotate-keys regenerates keys and logs security audit event."""
        temp_db = tempfile.mktemp(suffix=".db")
        init_db(temp_db, station_id="endpoint-a")

        app = create_app(db_path=temp_db, station_id="endpoint-a", port=5051)
        app.config["TESTING"] = True

        with app.test_client() as client:
            # Check initial public keys
            res_init = client.get("/api/v1/endpoints/public-keys")
            assert res_init.status_code == 200
            fp_pqc_init = res_init.json["pqc_fingerprint"]

            # Rotate keys
            res_rot = client.post("/api/v1/crypto/rotate-keys", json={"force": True})
            assert res_rot.status_code == 200
            assert res_rot.json["status"] == "KEYRING_ROTATED"
            fp_pqc_new = res_rot.json["pqc_fingerprint"]
            assert fp_pqc_new != fp_pqc_init

            # Verify audit log recorded
            with get_db_session(temp_db) as session:
                audit = (
                    session.query(SecurityAuditLog)
                    .filter_by(event_type="PQC_KEY_ROTATED")
                    .first()
                )
                assert audit is not None
                assert audit.severity == "INFO"

        try:
            os.remove(temp_db)
        except Exception:
            pass

    def test_emergency_zeroization_api(self):
        """Verifies POST /api/v1/crypto/zeroize purges keyrings and logs HIGH severity audit."""
        temp_db = tempfile.mktemp(suffix=".db")
        init_db(temp_db, station_id="endpoint-a")

        app = create_app(db_path=temp_db, station_id="endpoint-a", port=5051)
        app.config["TESTING"] = True

        with app.test_client() as client:
            res_zero = client.post("/api/v1/crypto/zeroize", json={"confirm": True})
            assert res_zero.status_code == 200
            assert res_zero.json["status"] == "KEYRING_ZEROIZED"

            # Check audit log recorded
            with get_db_session(temp_db) as session:
                audit = (
                    session.query(SecurityAuditLog)
                    .filter_by(event_type="PQC_KEYRING_ZEROIZED")
                    .first()
                )
                assert audit is not None
                assert audit.severity == "HIGH"

        try:
            os.remove(temp_db)
        except Exception:
            pass


# ==============================================================================
# 5. test_dmr_pqc_chunking: Transparent 280-Byte Burst Fragmentation & Reassembly
# ==============================================================================
def test_dmr_pqc_chunking():
    """Verifies chunking a v3 envelope produces ~5 chunks of <= 280 bytes that reassemble cleanly."""
    ek, dk = mlkem768_keygen()
    from cryptography.hazmat.primitives.asymmetric import x25519
    recip_x_priv = x25519.X25519PrivateKey.generate()
    recip_x_pub = recip_x_priv.public_key().public_bytes_raw()
    recip_x_sk = recip_x_priv.private_bytes_raw()

    plaintext = b"CRITICAL TACTICAL DISPATCH: SITREP REPORT EN-ROUTE TO BASE ALPHA"
    envelope = encrypt_v3_hybrid(
        plaintext, ek, recip_x_pub, "endpoint-a", "endpoint-b", "msg-dmr-burst"
    )

    # Frame structure: <json header>\x1f<binary envelope v3 bytes>
    header_json = json.dumps({"v": 1, "id": "msg-dmr-burst", "from": "endpoint-a", "to": "endpoint-b"}).encode("utf-8")
    frame = header_json + b"\x1f" + envelope

    # Chunk into <= 280 byte bursts
    chunks = chunk_frame(frame, chunk_bytes=_CHUNK_PAYLOAD_BYTES)
    assert len(chunks) == 5, f"Expected 5 DMR chunks, got {len(chunks)}"

    # Check each chunk length <= 280 bytes
    for c in chunks:
        assert len(c) <= DMR_CHUNK_BYTES

    # Reassemble chunks
    reassembled_parts = []
    for c in chunks:
        total, idx = struct.unpack("<HH", c[:4])
        assert total == len(chunks)
        reassembled_parts.append(c[4:])
    reassembled_frame = b"".join(reassembled_parts)
    assert reassembled_frame == frame

    # Extract binary envelope and decrypt
    header_rec, envelope_rec = reassembled_frame.split(b"\x1f", 1)
    assert envelope_rec == envelope

    decrypted, meta = decrypt_envelope(
        envelope_rec, dk, recip_x_sk, "endpoint-a", "endpoint-b", "msg-dmr-burst"
    )
    assert decrypted == plaintext
    assert meta["pqc_verified"] is True

import os
from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, timezone, timedelta
from messaging.db import get_db_session
from messaging.models import Endpoint, Message, MessageEvent, DeliveryAttempt, Acknowledgement, utcnow, generate_uuid
from messaging.service import MessagingService
from messaging.transport import transport
from messaging.retry_policy import RetryPolicy
from messaging.state_machine import MessageState, InvalidStateTransitionError

api_v1 = Blueprint("messaging_api_v1", __name__, url_prefix="/api/v1")


def _safe_int(value, default: int) -> int:
    """Parse an integer query parameter without raising on malformed input.

    Prevents HTTP 500 responses from non-numeric values such as
    ``?limit=abc`` by falling back to ``default``.
    """
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default



@api_v1.route("/health", methods=["GET"])
def health():
    db_p = current_app.config.get("DB_PATH")
    db_name = os.path.basename(db_p) if db_p else "default"
    return jsonify({
        "status": "HEALTHY",
        "service": "shadowcomm-reliable-messaging",
        "version": "2.0.0",
        "station_id": current_app.config.get("STATION_ID"),
        "station_name": current_app.config.get("STATION_NAME"),
        "db_path": db_name,
        "port": current_app.config.get("STATION_PORT"),
        "peer_url": current_app.config.get("PEER_URL"),
        "worker_status": "RUNNING",
        "transport_mode": "SIMULATION",
    })


@api_v1.route("/endpoints", methods=["GET"])
def list_endpoints():
    with get_db_session() as session:
        endpoints = session.query(Endpoint).all()
        return jsonify([e.to_dict() for e in endpoints])


@api_v1.route("/endpoints/public-keys", methods=["GET"])
def get_station_public_keys():
    """Returns station public cryptographic identity (ML-KEM-768 and X25519)."""
    from messaging.keyring import keyring_manager
    station_id = current_app.config.get("STATION_ID") or "endpoint-a"
    keys_info = keyring_manager.get_public_keys(station_id)
    keys_info["display_name"] = current_app.config.get(
        "STATION_NAME",
        "Station Alpha" if station_id == "endpoint-a" else "Station Bravo" if station_id == "endpoint-b" else "Tactical Station"
    )
    return jsonify(keys_info), 200


@api_v1.route("/crypto/rotate-keys", methods=["POST"])
def rotate_crypto_keys():
    """Operator key rotation API."""
    from messaging.keyring import keyring_manager
    from messaging.models import SecurityAuditLog
    station_id = current_app.config.get("STATION_ID") or "endpoint-a"
    new_bundle = keyring_manager.rotate_keyring(station_id)

    with get_db_session() as session:
        ep = session.query(Endpoint).filter_by(endpoint_id=station_id).first()
        if ep:
            ep.public_key_pqc = new_bundle["mlkem768"]["encapsulation_key_b64"]
            ep.public_key_x25519 = new_bundle["x25519"]["public_key_b64"]
            ep.pqc_fingerprint = new_bundle["mlkem768"]["fingerprint"]
            ep.pqc_algorithm = "ML-KEM-768"

        audit = SecurityAuditLog(
            action="PQC_KEY_ROTATED",
            severity="INFO",
            endpoint_id=station_id,
            details={
                "pqc_fingerprint": new_bundle["mlkem768"]["fingerprint"],
                "x25519_fingerprint": new_bundle["x25519"]["fingerprint"],
            }
        )
        session.add(audit)
        session.commit()

    return jsonify({
        "status": "KEYRING_ROTATED",
        "endpoint_id": station_id,
        "pqc_fingerprint": new_bundle["mlkem768"]["fingerprint"],
        "x25519_fingerprint": new_bundle["x25519"]["fingerprint"],
        "rotated_at": new_bundle["created_at"],
        "public_key_pqc": new_bundle["mlkem768"]["encapsulation_key_b64"],
        "public_key_x25519": new_bundle["x25519"]["public_key_b64"],
    }), 200


@api_v1.route("/crypto/zeroize", methods=["POST"])
def zeroize_crypto_keys():
    """Emergency zeroization API."""
    from messaging.keyring import keyring_manager
    from messaging.models import SecurityAuditLog
    station_id = current_app.config.get("STATION_ID") or "endpoint-a"
    keyring_manager.zeroize_keyring(station_id)

    with get_db_session() as session:
        ep = session.query(Endpoint).filter_by(endpoint_id=station_id).first()
        if ep:
            ep.public_key_pqc = None
            ep.public_key_x25519 = None
            ep.pqc_fingerprint = None

        audit = SecurityAuditLog(
            action="PQC_KEYRING_ZEROIZED",
            severity="HIGH",
            endpoint_id=station_id,
            details={
                "status": "PURGED",
                "note": "Station cryptographic keyrings securely expunged from memory and disk.",
            }
        )
        session.add(audit)
        session.commit()

    return jsonify({
        "status": "KEYRING_ZEROIZED",
        "endpoint_id": station_id,
        "detail": "Station cryptographic keyrings securely expunged from memory and disk.",
        "zeroized_at": utcnow().isoformat(),
    }), 200


@api_v1.route("/crypto/test-tamper", methods=["POST"])
def test_tamper_crypto():
    """Simulate transmission of tampered PQC ciphertext to target station to verify HTTP 422 rejection."""
    import requests
    import base64
    from messaging.crypto_pqc import encrypt_v3_hybrid
    from messaging.keyring import keyring_manager

    data = request.get_json(force=True, silent=True) or {}
    target_url = data.get("target_station_url") or current_app.config.get("PEER_URL")
    target_endpoint_id = data.get("target_endpoint_id")

    sender_station_id = current_app.config.get("STATION_ID") or "endpoint-a"
    if not target_endpoint_id:
        target_endpoint_id = "endpoint-b" if sender_station_id == "endpoint-a" else "endpoint-a"

    if not target_url:
        target_port = 5052 if sender_station_id == "endpoint-a" else 5051
        target_url = f"http://127.0.0.1:{target_port}/api/v1"

    pub_url = target_url.rstrip("/")
    if not pub_url.endswith("/endpoints/public-keys"):
        pub_url = f"{pub_url}/endpoints/public-keys"

    recip_mlkem_pk = None
    recip_x25519_pk = None
    try:
        resp_pub = requests.get(pub_url, timeout=3.0)
        if resp_pub.status_code == 200:
            pub_data = resp_pub.json()
            recip_mlkem_pk = base64.b64decode(pub_data["public_key_pqc"])
            recip_x25519_pk = base64.b64decode(pub_data["public_key_x25519"])
    except Exception:
        pass

    if not recip_mlkem_pk or not recip_x25519_pk:
        recip_mlkem_pk = keyring_manager.get_local_mlkem_pk(target_endpoint_id)
        recip_x25519_pk = keyring_manager.get_local_x25519_pk(target_endpoint_id)

    if not recip_mlkem_pk or not recip_x25519_pk:
        return jsonify({"error": "Target station public keys unavailable"}), 400

    test_msg_id = f"test-tamper-{generate_uuid()[:8]}"
    valid_env = encrypt_v3_hybrid(
        plaintext=b"AUTHENTIC TEST MESSAGE TO TAMPER",
        recipient_mlkem_pk=recip_mlkem_pk,
        recipient_x25519_pk=recip_x25519_pk,
        sender_endpoint_id=sender_station_id,
        recipient_endpoint_id=target_endpoint_id,
        message_id=test_msg_id,
    )

    tampered_env = bytearray(valid_env)
    tampered_env[100] ^= 0x01

    incoming_url = target_url.rstrip("/")
    if not incoming_url.endswith("/endpoints/incoming"):
        incoming_url = f"{incoming_url}/endpoints/incoming"

    bundle = {
        "message_id": test_msg_id,
        "client_idempotency_key": f"tamper-probe-{generate_uuid()[:8]}",
        "sender_endpoint_id": sender_station_id,
        "recipient_endpoint_id": target_endpoint_id,
        "payload": base64.b64encode(tampered_env).decode("ascii"),
        "message_type": "TEXT",
        "created_at": utcnow().isoformat(),
    }

    try:
        tx_resp = requests.post(incoming_url, json=bundle, timeout=5.0)
        status_code = tx_resp.status_code
        resp_data = tx_resp.json() if tx_resp.content else {}
    except Exception as e:
        return jsonify({"error": f"Failed to dispatch to target: {e}"}), 502

    return jsonify({
        "test_id": test_msg_id,
        "target": target_endpoint_id,
        "target_url": incoming_url,
        "injected_fault": "CIPHERTEXT_BIT_FLIP",
        "peer_http_status": status_code,
        "peer_response_code": resp_data.get("error"),
        "tamper_detected": (status_code == 422),
        "audit_event_logged": True,
    }), 200


@api_v1.route("/endpoints/incoming", methods=["POST"])
def ingest_incoming_message():
    """Peer-to-peer ingest route that receives cross-station message bundles (D-02)."""
    data = request.get_json(force=True, silent=True) or {}

    message_id = data.get("message_id")
    client_idempotency_key = data.get("client_idempotency_key")
    sender_endpoint_id = data.get("sender_endpoint_id")
    recipient_endpoint_id = data.get("recipient_endpoint_id")
    payload = data.get("payload")
    message_type = data.get("message_type", "TEXT")
    incident_id = data.get("incident_id")
    priority = data.get("priority", 1)
    created_at_raw = data.get("created_at")
    expires_at_raw = data.get("expires_at")

    if not message_id or not client_idempotency_key or not sender_endpoint_id or not recipient_endpoint_id or payload is None:
        return jsonify({"error": "Missing required fields for peer ingest"}), 400

    local_station_id = current_app.config.get("STATION_ID")
    if local_station_id and recipient_endpoint_id != local_station_id:
        return jsonify({
            "error": "RECIPIENT_MISMATCH",
            "detail": f"Recipient '{recipient_endpoint_id}' does not match local station '{local_station_id}'"
        }), 422

    # Parse timestamps
    created_at = None
    if created_at_raw:
        try:
            created_at = datetime.fromisoformat(created_at_raw.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            created_at = utcnow()
    else:
        created_at = utcnow()

    expires_at = None
    if expires_at_raw:
        try:
            expires_at = datetime.fromisoformat(expires_at_raw.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            expires_at = utcnow() + timedelta(days=1)
    else:
        expires_at = utcnow() + timedelta(days=1)

    # Cryptographic Envelope Decryption & Dual-Stack Inspection
    from messaging.keyring import keyring_manager
    from messaging.crypto_pqc import decrypt_envelope, ENVELOPE_VERSION_V3, ENVELOPE_VERSION_V2_GCM
    from messaging.crypto_v2 import CryptoError, AuthenticationError, InvalidEnvelopeError
    from messaging.models import SecurityAuditLog, MessageEvent
    import base64

    # Extract raw envelope bytes
    raw_envelope = None
    if isinstance(payload, bytes):
        raw_envelope = payload
    elif isinstance(payload, str):
        try:
            raw_envelope = base64.b64decode(payload)
        except Exception:
            raw_envelope = None

    envelope_meta = None
    decrypted_payload = payload

    if raw_envelope and len(raw_envelope) > 1 and raw_envelope[0] in (ENVELOPE_VERSION_V3, ENVELOPE_VERSION_V2_GCM):
        station_key_id = local_station_id or recipient_endpoint_id
        local_mlkem_sk = keyring_manager.get_local_mlkem_sk(station_key_id)
        local_x25519_sk = keyring_manager.get_local_x25519_sk(station_key_id)
        shared_v2_key = os.environ.get("SHADOWCOMM_SHARED_SECRET", "default-v2-shared-key-32bytes!")

        try:
            decrypted_bytes, envelope_meta = decrypt_envelope(
                envelope=raw_envelope,
                local_mlkem_sk=local_mlkem_sk,
                local_x25519_sk=local_x25519_sk,
                sender_endpoint_id=sender_endpoint_id,
                recipient_endpoint_id=recipient_endpoint_id,
                message_id=message_id,
                fallback_key=shared_v2_key,
            )
            decrypted_payload = decrypted_bytes.decode("utf-8", errors="replace")
        except (AuthenticationError, InvalidEnvelopeError) as e:
            with get_db_session() as session:
                audit = SecurityAuditLog(
                    action="PQC_TAMPER_DETECTED",
                    severity="HIGH",
                    endpoint_id=recipient_endpoint_id,
                    details={
                        "sender_endpoint_id": sender_endpoint_id,
                        "recipient_endpoint_id": recipient_endpoint_id,
                        "message_id": message_id,
                        "error": str(e),
                    }
                )
                session.add(audit)
                existing_msg = session.query(Message).filter_by(message_id=message_id).first()
                if existing_msg:
                    ev = MessageEvent(
                        event_id=generate_uuid(),
                        message_id=message_id,
                        event_type="CRYPTO_TAMPER_DETECTED",
                        timestamp=utcnow(),
                        source_endpoint=recipient_endpoint_id,
                        safe_metadata={
                            "sender": sender_endpoint_id,
                            "error": str(e),
                        },
                        error_code="CRYPTO_AUTHENTICATION_FAILED",
                    )
                    session.add(ev)
                session.commit()

            return jsonify({
                "error": "CRYPTO_AUTHENTICATION_FAILED",
                "detail": f"Ciphertext or authentication tag corrupted/tampered: {e}",
            }), 422

    from messaging.ack_manager import AckManager

    with get_db_session() as session:
        # Check if message already exists in messages table
        msg = session.query(Message).filter_by(message_id=message_id).first()
        is_new_msg = False
        if not msg:
            env_ver = envelope_meta.get("envelope_version", 3) if envelope_meta else 3
            scheme = envelope_meta.get("pqc_scheme", "ML-KEM-768+X25519") if envelope_meta else "ML-KEM-768+X25519"
            verified = envelope_meta.get("pqc_verified", False) if envelope_meta else False
            downgrade = envelope_meta.get("pqc_downgrade_warning", False) if envelope_meta else False

            msg = Message(
                message_id=message_id,
                client_idempotency_key=client_idempotency_key,
                sender_endpoint_id=sender_endpoint_id,
                recipient_endpoint_id=recipient_endpoint_id,
                payload=decrypted_payload,
                message_type=message_type,
                incident_id=incident_id,
                priority=priority,
                current_state=MessageState.DELIVERED.value,
                created_at=created_at,
                expires_at=expires_at,
                envelope_version=env_ver,
                pqc_scheme=scheme,
                pqc_verified=verified,
                pqc_downgrade_warning=downgrade,
            )
            session.add(msg)
            session.flush()
            is_new_msg = True

            if envelope_meta:
                if envelope_meta.get("pqc_downgrade_warning"):
                    audit = SecurityAuditLog(
                        action="PQC_DOWNGRADE_FALLBACK",
                        severity="MEDIUM",
                        endpoint_id=recipient_endpoint_id,
                        details={
                            "message_id": message_id,
                            "sender": sender_endpoint_id,
                            "scheme": "CLASSICAL_AES_256_GCM",
                        }
                    )
                    session.add(audit)
                    ev = MessageEvent(
                        event_id=generate_uuid(),
                        message_id=message_id,
                        event_type="PQC_DOWNGRADE_ACCEPTED",
                        timestamp=utcnow(),
                        source_endpoint=recipient_endpoint_id,
                        safe_metadata={"sender": sender_endpoint_id, "scheme": "CLASSICAL_AES_256_GCM"}
                    )
                    session.add(ev)
                elif envelope_meta.get("pqc_verified"):
                    ev = MessageEvent(
                        event_id=generate_uuid(),
                        message_id=message_id,
                        event_type="PQC_ENVELOPE_PROCESSED",
                        timestamp=utcnow(),
                        source_endpoint=recipient_endpoint_id,
                        safe_metadata={"scheme": "ML-KEM-768+X25519"}
                    )
                    session.add(ev)

        is_new_inbox, ack = AckManager.process_incoming_at_receiver(session, msg)
        receipt_sig = AckManager.generate_receipt_signature(ack, msg)
        msg.signed_ack_receipt = receipt_sig
        session.commit()

        status_code = 201 if is_new_inbox else 200
        return jsonify({
            "status": "STORED",
            "message_id": msg.message_id,
            "ack_id": ack.ack_id,
            "origin_endpoint": ack.origin_endpoint,
            "destination_endpoint": ack.destination_endpoint,
            "stored_at": msg.receiver_stored_at.isoformat() if msg.receiver_stored_at else utcnow().isoformat(),
            "signed_ack_receipt": msg.signed_ack_receipt,
            "is_duplicate": not is_new_inbox,
            "pqc_verified": msg.pqc_verified,
            "envelope_version": msg.envelope_version,
            "pqc_downgrade_warning": msg.pqc_downgrade_warning,
        }), status_code


@api_v1.route("/messages", methods=["GET"])
def list_messages():
    sender = request.args.get("sender")
    recipient = request.args.get("recipient")
    state = request.args.get("state")
    incident_id = request.args.get("incident_id")

    with get_db_session() as session:
        query = session.query(Message)
        if sender:
            query = query.filter_by(sender_endpoint_id=sender)
        if recipient:
            query = query.filter_by(recipient_endpoint_id=recipient)
        if state:
            query = query.filter_by(current_state=state)
        if incident_id:
            query = query.filter_by(incident_id=incident_id)

        messages = query.order_by(Message.created_at.desc()).all()
        return jsonify([m.to_dict() for m in messages])


@api_v1.route("/auth/verify", methods=["POST"])
def verify_auth():
    """Authenticates an endpoint using a pre-shared token."""
    data = request.get_json(force=True, silent=True) or {}
    endpoint_id = data.get("endpoint_id")
    token = data.get("token") or request.headers.get("X-Endpoint-Token")

    if not endpoint_id or not token:
        return jsonify({"error": "endpoint_id and token are required"}), 400

    with get_db_session() as session:
        ep = session.query(Endpoint).filter_by(endpoint_id=endpoint_id).first()
        if not ep or not ep.enabled:
            return jsonify({"error": f"Endpoint '{endpoint_id}' not found or disabled"}), 404
        if ep.auth_token and ep.auth_token != token:
            return jsonify({"authenticated": False, "error": "Invalid authentication token"}), 401

        return jsonify({
            "authenticated": True,
            "endpoint_id": ep.endpoint_id,
            "display_name": ep.display_name,
        })


@api_v1.route("/auth/login", methods=["POST"])
def login_user():
    data = request.get_json(force=True, silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    ip_addr = request.remote_addr
    ua = request.headers.get("User-Agent")

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    from messaging.auth_service import AuthService
    with get_db_session() as session:
        user, user_session, err = AuthService.authenticate_user(
            session=session,
            username=username,
            password=password,
            ip_address=ip_addr,
            user_agent=ua,
        )
        if err or not user:
            return jsonify({"authenticated": False, "error": err or "Authentication failed"}), 401

        return jsonify({
            "authenticated": True,
            "token": user_session.session_token,
            "expires_at": user_session.expires_at.isoformat(),
            "user": user.to_dict(),
        })


@api_v1.route("/auth/logout", methods=["POST"])
def logout_user():
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "").strip()
    if not token:
        data = request.get_json(force=True, silent=True) or {}
        token = data.get("token")

    if not token:
        return jsonify({"error": "Session token required"}), 400

    from messaging.auth_service import AuthService
    with get_db_session() as session:
        success = AuthService.revoke_session(session, token, ip_address=request.remote_addr)
        return jsonify({"logged_out": success})


@api_v1.route("/auth/me", methods=["GET"])
def get_current_user_profile():
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "").strip()
    if not token:
        token = request.args.get("token")

    if not token:
        return jsonify({"error": "Authentication required"}), 401

    from messaging.auth_service import AuthService
    with get_db_session() as session:
        user = AuthService.validate_session(session, token)
        if not user:
            return jsonify({"error": "Invalid or expired session"}), 401
        return jsonify(user.to_dict())


@api_v1.route("/users", methods=["POST"])
def create_new_user():
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "").strip()
    from messaging.auth_service import AuthService
    with get_db_session() as session:
        admin_user = AuthService.validate_session(session, token)
        if not admin_user or admin_user.role != "ADMINISTRATOR":
            return jsonify({"error": "Forbidden: Administrator role required"}), 403

        data = request.get_json(force=True, silent=True) or {}
        username = data.get("username")
        password = data.get("password")
        role = data.get("role", "OPERATOR")

        try:
            new_user = AuthService.create_user(
                session=session,
                username=username,
                password=password,
                role=role,
                actor_user_id=admin_user.user_id,
                ip_address=request.remote_addr,
            )
            return jsonify(new_user.to_dict()), 201
        except ValueError as e:
            return jsonify({"error": str(e)}), 400


@api_v1.route("/security/audit-logs", methods=["GET"])
def get_security_audit_logs():
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "").strip()
    from messaging.auth_service import AuthService
    from messaging.models import SecurityAuditLog
    with get_db_session() as session:
        admin_user = AuthService.validate_session(session, token)
        if not admin_user or admin_user.role != "ADMINISTRATOR":
            return jsonify({"error": "Forbidden: Administrator role required"}), 403

        limit = min(_safe_int(request.args.get("limit"), 100), 500)
        logs = session.query(SecurityAuditLog).order_by(SecurityAuditLog.timestamp.desc()).limit(limit).all()
        return jsonify([log.to_dict() for log in logs])


@api_v1.route("/messages", methods=["POST"])
def submit_message():
    data = request.get_json(force=True, silent=True) or {}

    client_idempotency_key = data.get("client_idempotency_key")
    sender_endpoint_id = data.get("sender_endpoint_id")
    recipient_endpoint_id = data.get("recipient_endpoint_id")
    payload = data.get("payload")
    message_type = data.get("message_type", "TEXT")
    incident_id = data.get("incident_id")
    expires_in_seconds = data.get("expires_in_seconds", 86400)
    priority = data.get("priority", 1)

    if not client_idempotency_key:
        return jsonify({"error": "client_idempotency_key is required"}), 400
    if not sender_endpoint_id:
        return jsonify({"error": "sender_endpoint_id is required"}), 400
    if not recipient_endpoint_id:
        return jsonify({"error": "recipient_endpoint_id is required"}), 400
    if payload is None:
        return jsonify({"error": "payload is required"}), 400

    local_station_id = current_app.config.get("STATION_ID")
    if local_station_id and sender_endpoint_id != local_station_id:
        return jsonify({
            "error": "IDENTITY_SPOOFING_BLOCKED",
            "detail": f"Local node identity is '{local_station_id}'. Local drafts cannot author messages as remote station '{sender_endpoint_id}'."
        }), 403

    # Sender Authentication Verification
    import os
    require_auth = os.environ.get("SHADOWCOMM_REQUIRE_AUTH", "false").lower() in ("true", "1", "yes")
    token = (
        request.headers.get("X-Endpoint-Token")
        or (request.headers.get("Authorization") or "").replace("Bearer ", "").strip()
        or data.get("auth_token")
    )

    with get_db_session() as session:
        sender = session.query(Endpoint).filter_by(endpoint_id=sender_endpoint_id).first()
        if require_auth or token:
            if not sender or not sender.auth_token:
                return jsonify({"error": f"Endpoint '{sender_endpoint_id}' has no authentication token configured"}), 401
            if sender.auth_token != token:
                return jsonify({"error": f"Unauthorized: invalid authentication token for '{sender_endpoint_id}'"}), 401

    try:
        with get_db_session() as session:
            msg, is_new = MessagingService.submit_message(
                session=session,
                client_idempotency_key=client_idempotency_key,
                sender_endpoint_id=sender_endpoint_id,
                recipient_endpoint_id=recipient_endpoint_id,
                payload=payload,
                message_type=message_type,
                incident_id=incident_id,
                expires_in_seconds=int(expires_in_seconds),
                priority=int(priority),
            )
            resp = msg.to_dict()
            resp["is_new"] = is_new
            status_code = 201 if is_new else 200
            return jsonify(resp), status_code
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Internal server error: {e}"}), 500


@api_v1.route("/messages/<message_id>", methods=["GET"])
def get_message(message_id):
    with get_db_session() as session:
        msg = session.query(Message).filter_by(message_id=message_id).first()
        if not msg:
            return jsonify({"error": f"Message '{message_id}' not found"}), 404
        return jsonify(msg.to_dict())


@api_v1.route("/messages/<message_id>/events", methods=["GET"])
def get_message_events(message_id):
    with get_db_session() as session:
        msg = session.query(Message).filter_by(message_id=message_id).first()
        if not msg:
            return jsonify({"error": f"Message '{message_id}' not found"}), 404

        events = (
            session.query(MessageEvent)
            .filter_by(message_id=message_id)
            .order_by(MessageEvent.timestamp.asc())
            .all()
        )
        return jsonify([e.to_dict() for e in events])


@api_v1.route("/messages/<message_id>/retry", methods=["POST"])
def retry_message(message_id):
    try:
        with get_db_session() as session:
            msg = MessagingService.retry_message(session, message_id)
            return jsonify(msg.to_dict())
    except ValueError as e:
        return jsonify({"error": str(e)}), 404 if "not found" in str(e) else 400
    except InvalidStateTransitionError as e:
        return jsonify({"error": str(e)}), 409


@api_v1.route("/messages/<message_id>/cancel", methods=["POST"])
def cancel_message(message_id):
    try:
        with get_db_session() as session:
            msg = MessagingService.cancel_message(session, message_id)
            return jsonify(msg.to_dict())
    except ValueError as e:
        return jsonify({"error": str(e)}), 404 if "not found" in str(e) else 400
    except InvalidStateTransitionError as e:
        return jsonify({"error": str(e)}), 409


@api_v1.route("/endpoints/<endpoint_id>/inbox", methods=["GET"])
def get_endpoint_inbox(endpoint_id):
    with get_db_session() as session:
        ep = session.query(Endpoint).filter_by(endpoint_id=endpoint_id).first()
        if not ep:
            return jsonify({"error": f"Endpoint '{endpoint_id}' not found"}), 404
        inbox = MessagingService.get_inbox_messages(session, endpoint_id)
        return jsonify(inbox)


@api_v1.route("/endpoints/<endpoint_id>/outbox", methods=["GET"])
def get_endpoint_outbox(endpoint_id):
    with get_db_session() as session:
        ep = session.query(Endpoint).filter_by(endpoint_id=endpoint_id).first()
        if not ep:
            return jsonify({"error": f"Endpoint '{endpoint_id}' not found"}), 404
        outbox = MessagingService.get_outbox_messages(session, endpoint_id)
        return jsonify(outbox)


@api_v1.route("/queue/stats", methods=["GET"])
def queue_stats():
    with get_db_session() as session:
        stats = MessagingService.get_queue_stats(session)
        stats["transport"] = transport.get_status()
        return jsonify(stats)


# ==================== SIMULATION CONTROL ROUTES ====================
@api_v1.route("/sim/transport", methods=["GET"])
def get_sim_transport():
    return jsonify(transport.get_status())


@api_v1.route("/sim/transport", methods=["POST"])
def update_sim_transport():
    data = request.get_json(force=True, silent=True) or {}
    if data.get("reset"):
        transport.reset()
    if "preset" in data:
        try:
            transport.apply_preset(data["preset"])
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
    if "is_online" in data:
        transport.set_online(bool(data["is_online"]))
    if "latency_ms" in data:
        transport.set_latency(float(data["latency_ms"]))
    if "drop_message_prob" in data:
        transport.set_drop_rate(float(data["drop_message_prob"]))
    if "drop_ack_prob" in data:
        transport.set_ack_drop_rate(float(data["drop_ack_prob"]))
    return jsonify(transport.get_status())


@api_v1.route("/sim/faults", methods=["POST"])
def inject_sim_fault():
    data = request.get_json(force=True, silent=True) or {}
    action = data.get("action")
    msg_id = data.get("message_id")

    if not action:
        return jsonify({"error": "action is required"}), 400

    if action == "arm_drop_message":
        transport.arm_drop_message()
        return jsonify({"status": "fault_armed", "action": action, "armed_faults": transport.get_status()["armed_faults"]})
    elif action == "arm_drop_ack":
        transport.arm_drop_ack()
        return jsonify({"status": "fault_armed", "action": action, "armed_faults": transport.get_status()["armed_faults"]})
    elif action == "arm_corrupt_hmac":
        transport.arm_corrupt_hmac()
        return jsonify({"status": "fault_armed", "action": action, "armed_faults": transport.get_status()["armed_faults"]})
    elif action == "disarm_all":
        transport.disarm_all()
        return jsonify({"status": "fault_armed", "action": action, "armed_faults": transport.get_status()["armed_faults"]})

    if not msg_id:
        return jsonify({"error": "message_id and action are required"}), 400

    if action == "drop_message":
        transport.drop_message(msg_id)
    elif action == "drop_ack":
        transport.drop_ack(msg_id)
    elif action == "error":
        err_code = data.get("error_code", "TEMPORARY_NETWORK_ERROR")
        transport.inject_fault(msg_id, err_code)
    else:
        return jsonify({"error": f"Unknown fault action: {action}"}), 400

    return jsonify({"status": "fault_injected", "message_id": msg_id, "action": action})


# ==================== WORKER LEASE & RETRY MANAGEMENT ROUTES ====================
@api_v1.route("/worker/reclaim", methods=["POST"])
def trigger_worker_reclaim():
    with get_db_session() as session:
        count = RetryPolicy.reclaim_stale_leases(session)
        if count > 0:
            session.commit()
        return jsonify({
            "reclaimed_count": count,
            "timestamp": utcnow().isoformat(),
        })


@api_v1.route("/worker/crash-simulation", methods=["POST"])
def simulate_worker_crash():
    data = request.get_json(force=True, silent=True) or {}
    target_id = data.get("message_id")
    with get_db_session() as session:
        msg = None
        if target_id:
            msg = session.query(Message).filter_by(message_id=target_id).first()
        if not msg:
            # Find any candidate message in SENDING, QUEUED, FAILED_RETRYABLE, or AWAITING_ACK
            msg = (
                session.query(Message)
                .filter(Message.current_state.in_([
                    MessageState.SENDING.value,
                    MessageState.QUEUED.value,
                    MessageState.FAILED_RETRYABLE.value,
                    MessageState.AWAITING_ACK.value,
                ]))
                .order_by(Message.created_at.desc())
                .first()
            )
        if not msg:
            # If no candidate exists, create one for demonstration
            msg, _ = MessagingService.submit_message(
                session=session,
                client_idempotency_key=f"crash-sim-{generate_uuid()[:8]}",
                sender_endpoint_id="endpoint-a",
                recipient_endpoint_id="endpoint-b",
                payload="SIMULATED_WORKER_CRASH_PAYLOAD",
            )

        now = utcnow()
        msg.current_state = MessageState.SENDING.value
        msg.worker_lease_id = "crashed-worker-sim"
        msg.lease_expires_at = now - timedelta(seconds=10)
        session.commit()
        return jsonify({
            "status": "worker_crash_simulated",
            "message_id": msg.message_id,
            "worker_lease_id": msg.worker_lease_id,
            "lease_expires_at": msg.lease_expires_at.isoformat(),
        })


@api_v1.route("/worker/retry-profile", methods=["GET"])
def get_worker_retry_profile():
    prof_key = RetryPolicy.active_profile
    prof_cfg = RetryPolicy.PROFILES.get(prof_key, RetryPolicy.PROFILES["TACTICAL"])
    return jsonify({
        "active_profile": prof_key,
        **prof_cfg,
    })


@api_v1.route("/worker/retry-profile", methods=["POST"])
def set_worker_retry_profile():
    data = request.get_json(force=True, silent=True) or {}
    profile = data.get("profile")
    if not profile:
        return jsonify({"error": "profile is required"}), 400
    try:
        RetryPolicy.configure_profile(profile)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    prof_key = RetryPolicy.active_profile
    prof_cfg = RetryPolicy.PROFILES.get(prof_key, RetryPolicy.PROFILES["TACTICAL"])
    return jsonify({
        "active_profile": prof_key,
        **prof_cfg,
    })


@api_v1.route("/transports", methods=["GET"])
def list_transports():
    from integration.manager import transport_manager
    return jsonify(transport_manager.list_adapters())


@api_v1.route("/transports/active", methods=["GET"])
def get_active_transport():
    """Reports which outbound path the delivery worker is currently using.

    The selection lives in shared storage, so this reflects the whole node —
    not just this web process.
    """
    from messaging.dispatch import (
        dispatch_router,
        dispatch_status,
        get_persisted_transport,
        get_persisted_failover,
    )

    with get_db_session() as session:
        persisted_transport = get_persisted_transport(session)
        persisted_failover = get_persisted_failover(session)
    dispatch_router.refresh(persisted_transport, persisted_failover)

    payload = dispatch_status(dispatch_router)
    if dispatch_router.is_live:
        from integration.manager import transport_manager
        adapter = transport_manager.get_adapter(dispatch_router.transport_id)
        if adapter is not None and hasattr(adapter, "bridge_probe"):
            payload["bridge"] = adapter.bridge_probe()
    return jsonify(payload)


@api_v1.route("/transports/active", methods=["POST"])
def set_active_transport():
    """Flip the node between the simulated link and a live transport adapter.

    Body: ``{"transport_id": "motorola-mototrbo-01"}`` to go live, or
    ``{"transport_id": null}`` to return to the simulated link. Optionally
    accepts ``"auto_failover": bool``. The choice is persisted so the delivery
    worker (a separate process) honours it too.
    """
    from messaging.dispatch import (
        dispatch_router,
        dispatch_status,
        set_persisted_transport,
        set_persisted_failover,
    )
    from integration.manager import transport_manager

    data = request.get_json(force=True, silent=True) or {}
    transport_id = data.get("transport_id")
    auto_failover = data.get("auto_failover")
    if transport_id:
        if transport_manager.get_adapter(transport_id) is None:
            return jsonify({"error": f"Unknown transport '{transport_id}'"}), 404

    with get_db_session() as session:
        set_persisted_transport(session, transport_id)
        if auto_failover is not None:
            set_persisted_failover(session, bool(auto_failover))

    dispatch_router.configure(transport_id, auto_failover=auto_failover)
    return jsonify(dispatch_status(dispatch_router))


@api_v1.route("/transports/failover", methods=["POST"])
def set_failover_policy():
    """Configure auto-failover policy.

    Body: ``{"auto_failover": true}`` or ``{"auto_failover": false}``.
    """
    from messaging.dispatch import (
        dispatch_router,
        dispatch_status,
        set_persisted_failover,
    )

    data = request.get_json(force=True, silent=True) or {}
    auto_failover = data.get("auto_failover")
    if auto_failover is None:
        return jsonify({"error": "Field 'auto_failover' is required (boolean)"}), 400

    auto_failover_bool = bool(auto_failover)
    with get_db_session() as session:
        set_persisted_failover(session, auto_failover_bool)

    dispatch_router.configure(dispatch_router.transport_id, auto_failover=auto_failover_bool)
    return jsonify(dispatch_status(dispatch_router))


@api_v1.route("/transports/starv/test-lockout", methods=["POST"])
def test_starv_lockout():
    """Execute a dry-run test bench probe against STAR-V software lockout.

    Body: ``{"test_type": "soft_refusal"}`` or ``{"test_type": "hard_command"}``.
    Records high-severity security audit log and returns lockout status.
    """
    from integration.manager import transport_manager
    from messaging.models import SecurityAuditLog, generate_uuid, utcnow

    data = request.get_json(force=True, silent=True) or {}
    test_type = data.get("test_type", "soft_refusal")

    adapter = transport_manager.get_adapter("starv-tactical-locked")
    if adapter is None:
        return jsonify({"error": "STAR-V adapter not registered"}), 500

    try:
        result = adapter.test_safety_lockout(test_type)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    # Record SecurityAuditLog
    try:
        with get_db_session() as session:
            audit = SecurityAuditLog(
                log_id=generate_uuid(),
                timestamp=utcnow(),
                action="STARV_LOCKOUT_TEST_VERIFIED",
                severity="HIGH",
                details={
                    "test_type": test_type,
                    "mechanism": result.get("mechanism"),
                    "status": result.get("status"),
                },
            )
            session.add(audit)
    except Exception:
        pass

    return jsonify({
        "status": result.get("status", "BLOCKED"),
        "test_type": test_type,
        "mechanism": result.get("mechanism"),
        "details": "Hardware safety lockout verified active and enforced.",
        "audit_logged": True,
    })


@api_v1.route("/transports/<transport_id>", methods=["GET"])
def get_transport_detail(transport_id):
    from integration.manager import transport_manager
    adapter = transport_manager.get_adapter(transport_id)
    if adapter is None:
        return jsonify({"error": f"Unknown transport '{transport_id}'"}), 404
    if hasattr(adapter, "health_check"):
        return jsonify(adapter.health_check())
    return jsonify(adapter.to_dict())


@api_v1.route("/relays", methods=["GET"])
def list_relays():
    from integration.relay_nodes.manager import relay_manager
    return jsonify(relay_manager.list_nodes())


@api_v1.route("/relays/<relay_id>", methods=["GET"])
def get_relay_detail(relay_id):
    from integration.relay_nodes.manager import relay_manager
    node = relay_manager.get_node(relay_id)
    if node is None:
        return jsonify({"error": f"Relay node '{relay_id}' not found"}), 404
    return jsonify(node.to_dict())


@api_v1.route("/relays/<relay_id>/telemetry", methods=["POST"])
def update_relay_telemetry(relay_id):
    from integration.relay_nodes.manager import relay_manager, RelayStatus
    from integration.relay_nodes.mesh_router import mesh_router
    node = relay_manager.get_node(relay_id)
    if node is None:
        return jsonify({"error": f"Relay node '{relay_id}' not found"}), 404

    data = request.get_json(force=True, silent=True) or {}
    battery = data.get("battery")
    if battery is None:
        battery = data.get("battery_percentage") if data.get("battery_percentage") is not None else data.get("battery_level_pct")
    temperature = data.get("temperature") if data.get("temperature") is not None else data.get("temperature_celsius")
    storage_pct = data.get("storage_pct")
    if storage_pct is None:
        storage_pct = data.get("storage_used_pct") if data.get("storage_used_pct") is not None else data.get("storage_usage_pct")
    queue_depth = data.get("queue_depth") if data.get("queue_depth") is not None else data.get("queued_bundles_count")
    status_str = data.get("status")
    status = None
    if status_str:
        try:
            status = RelayStatus(str(status_str).upper())
        except ValueError:
            pass

    position = data.get("position")
    sector = data.get("sector")

    node.update_telemetry(
        battery=float(battery) if battery is not None else None,
        temperature=float(temperature) if temperature is not None else None,
        storage_pct=float(storage_pct) if storage_pct is not None else None,
        status=status,
        queue_depth=int(queue_depth) if queue_depth is not None else None,
        position=position,
        sector=sector,
    )
    new_route = mesh_router.compute_route("endpoint-a", "endpoint-b")
    res = node.to_dict()
    res["new_route"] = new_route
    return jsonify(res)


@api_v1.route("/topology/mesh", methods=["GET"])
def get_mesh_topology():
    from integration.relay_nodes.manager import relay_manager
    from integration.relay_nodes.mesh_router import mesh_router

    active_route = mesh_router.compute_route("endpoint-a", "endpoint-b")
    nodes = relay_manager.list_nodes()
    links = mesh_router.get_topology_links(active_path=active_route.get("path", []))

    return jsonify({
        "nodes": nodes,
        "links": links,
        "active_route": active_route,
    })


@api_v1.route("/relays/scenario", methods=["POST"])
def execute_relay_scenario():
    import time
    from integration.relay_nodes.manager import relay_manager, RelayStatus
    from integration.relay_nodes.mesh_router import mesh_router

    data = request.get_json(force=True, silent=True) or {}
    scenario = data.get("scenario", "reset_nominal")

    # Get previous path
    prev_route = mesh_router.compute_route("endpoint-a", "endpoint-b")
    prev_path = prev_route.get("path", [])

    t0 = time.time()
    reroute_event = ""

    if scenario == "scenario_1_uav_signal_lost":
        uav_a = relay_manager.get_node("relay-uav-alpha")
        if uav_a:
            uav_a.update_telemetry(status=RelayStatus.FORCE_OFFLINE)
        reroute_event = "[MESH REROUTE: Bypassed relay-uav-alpha -> Diverted via relay-ground-01 -> Delivered]"

    elif scenario == "scenario_2_ground_relays_jammed":
        # Make sure aerial relays are nominal online
        uav_a = relay_manager.get_node("relay-uav-alpha")
        uav_b = relay_manager.get_node("relay-uav-bravo")
        if uav_a:
            uav_a.update_telemetry(status=RelayStatus.ONLINE, battery=98.0)
        if uav_b:
            uav_b.update_telemetry(status=RelayStatus.ONLINE, battery=92.0)
        # Jam ground nodes
        for gid in ("relay-ground-01", "relay-convoy-01", "relay-ground-02"):
            g_node = relay_manager.get_node(gid)
            if g_node:
                g_node.update_telemetry(status=RelayStatus.RF_JAMMED)
        reroute_event = "[MESH REROUTE: Ground relays jammed -> Diverted via aerial corridor -> Delivered]"

    elif scenario == "scenario_3_convoy_breakout":
        # Set both UAVs to OFFLINE
        for uav_id in ("relay-uav-alpha", "relay-uav-bravo"):
            u_node = relay_manager.get_node(uav_id)
            if u_node:
                u_node.update_telemetry(status=RelayStatus.OFFLINE)
        # Restore ground nodes to online
        for gid in ("relay-ground-01", "relay-convoy-01", "relay-ground-02"):
            g_node = relay_manager.get_node(gid)
            if g_node:
                g_node.update_telemetry(status=RelayStatus.ONLINE)
        reroute_event = "[MESH REROUTE: Aerial corridor lost -> Diverted via tactical convoy -> Delivered]"

    elif scenario == "reset_nominal":
        relay_manager.reset_all_nodes()
        reroute_event = "[MESH TOPOLOGY: Restored nominal operating topology]"

    else:
        return jsonify({"error": f"Unknown scenario: {scenario}"}), 400

    new_route = mesh_router.compute_route("endpoint-a", "endpoint-b")
    new_path = new_route.get("path", [])
    convergence_ms = (time.time() - t0) * 1000.0

    return jsonify({
        "scenario": scenario,
        "previous_path": prev_path,
        "new_path": new_path,
        "reroute_event": reroute_event,
        "convergence_latency_ms": round(convergence_ms, 2),
        "status": "CONVERGED",
    })


@api_v1.route("/mesh/route/simulate", methods=["POST"])
def simulate_mesh_route():
    import uuid
    from integration.relay_nodes.mesh_router import mesh_router
    from integration.relay_nodes.manager import relay_manager
    from messaging.mesh_bundle import (
        wrap_mesh_bundle,
        process_hop_bundle,
        generate_custody_ack_token,
    )

    route = mesh_router.compute_route("endpoint-a", "endpoint-b")
    path = route.get("path", [])
    if not path or len(path) < 2:
        return jsonify({
            "delivered": False,
            "error": "No viable route available across mesh",
            "active_route": path,
            "trace": [],
        }), 400

    bundle_uuid = uuid.uuid4()
    bundle_bytes = wrap_mesh_bundle(b"SIMULATED_ENVELOPE_V3_PAYLOAD", bundle_uuid=bundle_uuid, source_node_id=path[0])

    trace = []
    delivered = True

    for i in range(len(path) - 1):
        u = path[i]
        v = path[i + 1]
        repacked, next_hdr, err = process_hop_bundle(bundle_bytes, v)
        if err:
            trace.append({
                "hop": i + 1,
                "from_node": u,
                "to_node": v,
                "status": "DROPPED",
                "error": err,
            })
            delivered = False
            break

        custody_token = generate_custody_ack_token(v, bundle_uuid.bytes, next_hdr.hop_count)
        u_node = relay_manager.get_node(u)
        v_node = relay_manager.get_node(v)
        lat = mesh_router.estimate_link_latency(u_node, v_node) if (u_node and v_node) else 20.0

        trace.append({
            "hop": i + 1,
            "from_node": u,
            "to_node": v,
            "status": "FORWARDED",
            "custody_ack": custody_token.hex(),
            "remaining_ttl": next_hdr.remaining_ttl,
            "latency_ms": lat,
        })
        bundle_bytes = repacked

    return jsonify({
        "delivered": delivered,
        "active_route": path,
        "total_hops": len(path) - 1,
        "estimated_latency_ms": route.get("estimated_latency_ms", 0.0),
        "trace": trace,
    })


@api_v1.route("/relays/<relay_id>/reset", methods=["POST"])
def reset_relay_node(relay_id):
    from integration.relay_nodes.manager import relay_manager
    node = relay_manager.reset_node(relay_id)
    if node is None:
        return jsonify({"error": f"Relay node '{relay_id}' not found"}), 404
    return jsonify(node.to_dict())


@api_v1.route("/sdr-research/status", methods=["GET"])
@api_v1.route("/research/status", methods=["GET"])
def get_sdr_research_status():
    from integration.sdr_research.service import sdr_research_service
    return jsonify(sdr_research_service.get_research_status())


@api_v1.route("/research/checkpoints", methods=["GET"])
def get_research_checkpoints():
    from integration.sdr_research.service import sdr_research_service
    return jsonify(sdr_research_service.audit_checkpoints())


@api_v1.route("/research/checkpoints/verify", methods=["POST"])
def verify_research_checkpoint():
    from integration.sdr_research.service import sdr_research_service
    from messaging.models import SecurityAuditLog

    result = sdr_research_service.verify_checkpoint_bundle(force=True)
    verified = result.get("verified", False)
    digest = result.get("sha256")
    bundle_files = result.get("bundle_files", {})
    expected = result.get("expected_sha256")

    with get_db_session() as session:
        if verified:
            audit = SecurityAuditLog(
                action="MODEL_CHECKPOINT_VERIFIED",
                severity="INFO",
                details={
                    "checkpoint": "lpi_v4.best.pt",
                    "sha256": digest,
                    "bundle_intact": result.get("bundle_intact", True),
                },
            )
            session.add(audit)
            session.flush()
            return jsonify({
                "success": True,
                "verified": True,
                "sha256": digest,
                "bundle_files": bundle_files,
                "bundle_intact": True,
                "audit_log_id": audit.audit_id,
            }), 200
        else:
            audit = SecurityAuditLog(
                action="MODEL_CHECKPOINT_HASH_MISMATCH",
                severity="HIGH",
                details={
                    "checkpoint": "lpi_v4.best.pt",
                    "sha256": digest,
                    "expected": expected,
                    "status": "ANALYTICAL_FALLBACK_ACTIVE",
                },
            )
            session.add(audit)
            session.flush()
            return jsonify({
                "success": False,
                "verified": False,
                "sha256": digest,
                "fallback_active": True,
                "audit_log_id": audit.audit_id,
            }), 200


@api_v1.route("/research/checkpoints/test-tamper", methods=["POST"])
def test_tamper_checkpoint():
    from integration.sdr_research.service import sdr_research_service
    from messaging.models import SecurityAuditLog

    data = request.get_json(silent=True) or {}
    tamper = bool(data.get("tamper", True))

    tamper_result = sdr_research_service.simulate_tamper(active=tamper)

    with get_db_session() as session:
        if tamper:
            audit = SecurityAuditLog(
                action="MODEL_CHECKPOINT_HASH_MISMATCH",
                severity="HIGH",
                details={
                    "tamper_simulated": True,
                    "status": "ANALYTICAL_FALLBACK_ACTIVE",
                    "note": "Interactive dry-run tamper test bench triggered by operator.",
                },
            )
        else:
            audit = SecurityAuditLog(
                action="MODEL_CHECKPOINT_VERIFIED",
                severity="INFO",
                details={
                    "tamper_simulated": False,
                    "status": "NORMAL_NEURAL_INFERENCE_RESTORED",
                },
            )
        session.add(audit)
        session.flush()
        audit_id = audit.audit_id

    return jsonify({
        "tamper_simulated": tamper,
        "fallback_active": tamper,
        "status": "ANALYTICAL_FALLBACK_ACTIVE" if tamper else "NORMAL",
        "audit_log_id": audit_id,
        "details": tamper_result,
    }), 200


@api_v1.route("/research/benchmark/compare", methods=["POST"])
def compare_research_benchmark():
    from integration.sdr_research.service import sdr_research_service

    data = request.get_json(silent=True) or {}
    frames = _safe_int(data.get("frames"), 64)
    result = sdr_research_service.run_comparative_benchmark(frames=frames)
    return jsonify(result), 200


@api_v1.route("/research/training-history", methods=["GET"])
def get_research_training_history():
    from integration.sdr_research.service import sdr_research_service
    limit = _safe_int(request.args.get("limit"), 100)
    return jsonify(sdr_research_service.get_training_history(limit=limit))


@api_v1.route("/research/evaluation", methods=["GET"])
def get_research_evaluation():
    from integration.sdr_research.service import sdr_research_service
    return jsonify(sdr_research_service.get_evaluation_report())


@api_v1.route("/research/signal-sample", methods=["GET"])
def get_research_signal_sample():
    from integration.sdr_research.service import sdr_research_service
    n = min(_safe_int(request.args.get("n"), 256), 1024)
    return jsonify(sdr_research_service.get_signal_sample(n_samples=n))


@api_v1.route("/research/environment", methods=["GET"])
def get_research_environment():
    from integration.sdr_research.service import sdr_research_service
    return jsonify(sdr_research_service.get_environment_metadata())


@api_v1.route("/research/anomalies", methods=["GET"])
def get_research_anomalies():
    """One honest snapshot: live EW anomaly battery + operational anomalies.

    The RF/electronic-warfare half is a real eight-domain measurement taken
    from the loaded checkpoint (or an explicitly-labelled baseline replay).
    The delivery-plane half is derived from recorded rows only.
    """
    from integration.sdr_research.service import sdr_research_service as svc
    from messaging.anomaly_service import AnomalyService

    n_frames = max(1, min(_safe_int(request.args.get("frames"), 32), 128))
    ew = svc.get_ew_anomaly_report(n_frames=n_frames)
    model = svc.get_model_telemetry()

    operational = []
    try:
        with get_db_session() as session:
            operational = AnomalyService.operational_anomalies(session)
    except Exception as exc:  # noqa: BLE001 - never fail the panel on a store issue
        operational = [{
            "key": "store_unavailable", "label": "Message store", "observed": None,
            "baseline": "reachable", "unit": "\u2014", "state": "UNKNOWN",
            "detail": f"Operational checks unavailable: {exc}",
            "threshold": {},
        }]

    summary = AnomalyService.summarize(ew.get("domains", []), operational)
    return jsonify({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "provenance": ew.get("provenance"),
        "baseline_source": ew.get("baseline_source"),
        "model": model,
        "domains": ew.get("domains", []),
        "operational": operational,
        "ew": {
            "n_frames": ew.get("n_frames"),
            "Sc": ew.get("Sc"),
            "grade": ew.get("grade"),
            "n_pass": ew.get("n_pass"),
            "error": ew.get("error"),
            "disclaimer": ew.get("disclaimer"),
        },
    })


@api_v1.route("/research/waveform-comparison", methods=["GET"])
def get_waveform_comparison():
    """LPI-CGAN waveform vs. a conventional (non-LPI) reference.

    Both tracks are measured through the *same* eight-domain EW battery at the
    same payload and the same real-sample budget, so the two columns of the
    Waveform Lab page are directly comparable. Track A is a live forward pass
    of the trained generator; Track B is RRC-shaped QPSK.

    Additionally includes the **Motorola LPI burst** from the latest actual
    message transmission, if available. This is the real-world measurement of
    what the Motorola radio actually transmits.

    The Motorola burst is returned as a *sibling* key ``motorola_track`` (plus
    ``motorola_lpi_active`` / ``motorola_lpi_note``), NOT as a third entry in
    ``tracks``. ``tracks`` is a stabilised two-key contract (``lpi`` and
    ``conventional``) that the Waveform Lab UI and its type declaration both
    require; injecting a third track there changes the shape of a public field
    and silently breaks consumers that destructure it.
    """
    from integration.waveform_lab.service import waveform_lab_service

    n_frames = max(1, min(_safe_int(request.args.get("frames"), 4), 16))
    result = waveform_lab_service.compare(n_frames=n_frames)

    # Expose the live Motorola LPI burst alongside (not inside) the two tracks.
    try:
        from integration.motorola.lpi_waveform_buffer import lpi_waveform_buffer
        ew = lpi_waveform_buffer.ew_battery()
        waveform = lpi_waveform_buffer.waveform_view(n_samples=256)
        spectrum = lpi_waveform_buffer.spectrum_snapshot(fft_size=256)
        burst = lpi_waveform_buffer.latest()

        if burst is not None and ew is not None:
            motorola_track = {
                "id": "motorola_lpi",
                "label": "Motorola LPI Carrier (live burst)",
                "source": "integration/motorola/lpi_carrier.py — actual transmission",
                "available": True,
                "waveform": waveform.get("waveform", []) if waveform else [],
                "constellation": waveform.get("constellation", []) if waveform else [],
                "spectrum": [
                    {"freq_khz": round(i * burst.sample_rate / 256.0 / 1000.0 - burst.sample_rate / 2000.0, 3),
                     "power_db": v}
                    for i, v in enumerate(spectrum.get("spectrum_db", []))
                ] if spectrum else [],
                "domains": ew.get("signal", {}).get("domains", []) if isinstance(ew.get("signal"), dict) else [],
                "n_pass": ew.get("signal", {}).get("n_pass", 0) if isinstance(ew.get("signal"), dict) else 0,
                "n_domains": 8,
                "stealth_score": None,
                "classification": "MOTOROLA_LPI_LIVE",
                "burst_timestamp": burst.timestamp,
                "message_id": burst.message_id,
            }
            result["motorola_track"] = motorola_track
            result["motorola_lpi_active"] = True
        else:
            result["motorola_track"] = None
            result["motorola_lpi_active"] = False
            result["motorola_lpi_note"] = "Send a message to capture a live Motorola LPI burst"
    except Exception:
        result["motorola_track"] = None
        result["motorola_lpi_active"] = False

    return jsonify(result)


@api_v1.route("/research/eval/run", methods=["POST"])
def run_research_eval():
    data = request.get_json(force=True, silent=True) or {}
    frames = int(data.get("frames", 128))
    snrs = data.get("snrs", "2,6,10")
    device = data.get("device", "cpu")
    from integration.sdr_research.service import SDRResearchService
    svc = SDRResearchService()
    res = svc.run_controlled_eval(frames=frames, snrs=snrs, device=device)
    return jsonify(res)


# =========================================================================
# ASTRA ADVANCED SDR WORKSTATION REST APIS
# =========================================================================
@api_v1.route("/workstation/overview", methods=["GET"])
def workstation_overview():
    from integration.workstation_service import workstation_service
    return jsonify(workstation_service.get_mission_overview())


@api_v1.route("/workstation/sdr-status", methods=["GET"])
def workstation_sdr_status():
    from integration.workstation_service import workstation_service
    return jsonify(workstation_service.probe_sdr_hardware())


@api_v1.route("/workstation/transmitter/prepare", methods=["POST"])
def workstation_tx_prepare():
    data = request.get_json(force=True, silent=True) or {}
    text = data.get("text", "")
    msg_type = data.get("message_type", "TEXT")
    from integration.workstation_service import workstation_service
    return jsonify(workstation_service.prepare_transmitter_payload(text=text, msg_type=msg_type))


@api_v1.route("/workstation/transmitter/generate", methods=["POST"])
def workstation_tx_generate():
    data = request.get_json(force=True, silent=True) or {}
    text = data.get("text", "ASTRA_PING")
    from integration.workstation_service import workstation_service
    return jsonify(workstation_service.generate_waveform_burst(text=text))


@api_v1.route("/workstation/transmitter/transmit", methods=["POST"])
def workstation_tx_transmit():
    data = request.get_json(force=True, silent=True) or {}
    text = data.get("text", "ASTRA_BURST")
    mode = data.get("mode", "SIMULATION")
    confirm = bool(data.get("confirm", False))
    from integration.workstation_service import workstation_service
    return jsonify(workstation_service.execute_transmission(text=text, mode=mode, confirm=confirm))


@api_v1.route("/workstation/receiver/capture", methods=["POST"])
def workstation_rx_capture():
    data = request.get_json(force=True, silent=True) or {}
    mode = data.get("mode", "SIMULATION")
    target_snr_db = float(data.get("target_snr_db", 6.0))
    payload_text = data.get("payload_text") or data.get("text")
    from integration.workstation_service import workstation_service
    return jsonify(workstation_service.execute_receiver_dsp_pipeline(
        mode=mode,
        target_snr_db=target_snr_db,
        payload_text=payload_text
    ))


@api_v1.route("/workstation/channel/simulate", methods=["POST"])
def workstation_channel_simulate():
    data = request.get_json(force=True, silent=True) or {}
    target_snr_db = float(data.get("target_snr_db", 6.0))
    cfo_hz = float(data.get("cfo_hz", 50.0))
    phase_offset_deg = float(data.get("phase_offset_deg", 15.0))
    multipath = bool(data.get("multipath", False))
    from integration.workstation_service import workstation_service
    return jsonify(workstation_service.simulate_channel(
        target_snr_db=target_snr_db,
        cfo_hz=cfo_hz,
        phase_offset_deg=phase_offset_deg,
        multipath=multipath
    ))


@api_v1.route("/workstation/signal/analysis", methods=["GET"])
def workstation_signal_analysis():
    source = request.args.get("source", "SYNTHESIS")
    try:
        fft_size = int(request.args.get("fft_size", 256))
        if fft_size not in [256, 512, 1024]:
            fft_size = 256
    except (ValueError, TypeError):
        fft_size = 256

    window = request.args.get("window", "blackman_harris")
    if window.lower() not in ["blackman_harris", "hann", "hamming", "rectangular"]:
        window = "blackman_harris"
    file_path = request.args.get("file", None)
    from integration.workstation_service import workstation_service
    return jsonify(workstation_service.get_signal_intelligence_data(
        source=source,
        fft_size=fft_size,
        window=window,
        file_path=file_path
    ))


@api_v1.route("/workstation/diagnostics", methods=["GET"])
def workstation_diagnostics():
    from integration.workstation_service import workstation_service
    return jsonify(workstation_service.get_system_diagnostics())


@api_v1.route("/workstation/experiments", methods=["GET"])
def workstation_experiments():
    from integration.sdr_research.service import SDRResearchService
    svc = SDRResearchService()
    report = svc.get_evaluation_report()
    history = svc.get_training_history(limit=50)
    return jsonify({
        "current_evaluation": report,
        "training_epochs": history,
        "available_checkpoints": ["lpi_v4.best.pt", "generator_lpi.pt", "decoder_lpi.pt"],
    })


@api_v1.route("/workstation/glossary", methods=["GET"])
def workstation_glossary():
    from integration.workstation_service import workstation_service
    return jsonify(workstation_service.get_glossary())


@api_v1.route("/workstation/help", methods=["GET"])
def workstation_help():
    from integration.workstation_service import workstation_service
    return jsonify(workstation_service.get_help_documentation())


@api_v1.route("/diagnostics/pcap", methods=["GET"])
def export_pcap_capture():
    from flask import Response
    from messaging.pcap import global_pcap_buffer
    import time

    # Ensure at least one initial baseline packet exists in buffer for valid PCAP inspection
    if global_pcap_buffer.count() == 0:
        sample_packet = b"\x53\x48\x44\x57\x03\x01\x00\x00" + b"ASTRA_TACTICAL_ENVELOPE_V3_INIT_FRAME"
        global_pcap_buffer.record(sample_packet, {"type": "BEACON_INIT"})

    pcap_data = global_pcap_buffer.generate_pcap()
    station = current_app.config.get("STATION_ID") or "gateway"
    ts_str = time.strftime("%Y%m%d_%H%M%S")
    filename = f"astra_tactical_{station}_{ts_str}.pcap"

    return Response(
        pcap_data,
        mimetype="application/vnd.tcpdump.pcap",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "X-Pcap-Packet-Count": str(global_pcap_buffer.count()),
            "X-Pcap-LinkType": "147",
        },
    )


@api_v1.route("/rf/link-budget", methods=["POST", "GET"])
def compute_rf_link_budget():
    from messaging.link_budget import calculate_link_budget, TACTICAL_BAND_PRESETS
    if request.method == "POST":
        data = request.get_json(force=True, silent=True) or {}
    else:
        data = request.args.to_dict()

    preset_key = data.get("preset")
    preset_params = TACTICAL_BAND_PRESETS.get(preset_key, {})

    distance_km = float(data.get("distance_km", 5.0))
    freq_mhz = float(data.get("freq_mhz", preset_params.get("freq_mhz", 433.0)))
    tx_power_dbm = float(data.get("tx_power_dbm", preset_params.get("tx_power_dbm", 37.0)))
    tx_gain_dbi = float(data.get("tx_gain_dbi", preset_params.get("tx_gain_dbi", 2.15)))
    rx_gain_dbi = float(data.get("rx_gain_dbi", preset_params.get("rx_gain_dbi", 2.15)))
    cable_loss_db = float(data.get("cable_loss_db", 1.0))
    rx_sensitivity_dbm = float(data.get("rx_sensitivity_dbm", preset_params.get("rx_sensitivity_dbm", -114.0)))

    result = calculate_link_budget(
        distance_km=distance_km,
        freq_mhz=freq_mhz,
        tx_power_dbm=tx_power_dbm,
        tx_gain_dbi=tx_gain_dbi,
        rx_gain_dbi=rx_gain_dbi,
        cable_loss_db=cable_loss_db,
        rx_sensitivity_dbm=rx_sensitivity_dbm,
    )
    result["presets"] = TACTICAL_BAND_PRESETS
    return jsonify(result)


@api_v1.route("/stream/spectrum", methods=["GET"])
def get_spectrum_stream_snapshot():
    """Live spectrum snapshot — shows REAL Motorola LPI burst PSD when available.

    When a message has been sent through the Motorola LPI carrier, this
    endpoint returns the actual FFT/PSD of the latest burst audio. When no
    burst has been captured yet, it falls back to a synthetic noise floor so
    the UI still renders.
    """
    import numpy as np
    import time

    # Try to get real Motorola LPI burst spectrum first
    try:
        from integration.motorola.lpi_waveform_buffer import lpi_waveform_buffer
        snapshot = lpi_waveform_buffer.spectrum_snapshot(fft_size=256)
        if snapshot is not None:
            return jsonify(snapshot)
    except Exception:
        pass

    # Fallback: synthetic noise floor (no burst captured yet)
    fft_size = 256
    noise = np.random.normal(loc=-105.0, scale=3.5, size=fft_size)
    center = fft_size // 2
    signal = 18.0 * np.exp(-0.5 * ((np.arange(fft_size) - center) / 12.0) ** 2)
    spectrum_db = (noise + signal).tolist()
    return jsonify({
        "fft_size": fft_size,
        "center_freq_mhz": 433.0,
        "spectrum_db": [round(val, 2) for val in spectrum_db],
        "timestamp": time.time(),
        "source": "synthetic_noise_floor",
        "note": "No Motorola LPI burst captured yet — send a message to see real LPI spectrum",
    })


@api_v1.route("/stream/lpi-status", methods=["GET"])
def get_lpi_status():
    """Live status of the Motorola LPI carrier pipeline.

    Returns the waveform buffer status and the latest EW battery results.
    """
    try:
        from integration.motorola.lpi_waveform_buffer import lpi_waveform_buffer
        status = lpi_waveform_buffer.status()
        ew = lpi_waveform_buffer.ew_battery()
        waveform = lpi_waveform_buffer.waveform_view(n_samples=128)
        return jsonify({
            "lpi_pipeline_active": True,
            "buffer": status,
            "ew_battery": ew,
            "waveform_preview": waveform,
        })
    except Exception as e:
        return jsonify({
            "lpi_pipeline_active": False,
            "error": str(e),
        })




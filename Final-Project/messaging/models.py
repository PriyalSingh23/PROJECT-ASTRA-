import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    DateTime,
    Text,
    JSON,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def generate_uuid():
    return str(uuid.uuid4())


class Endpoint(Base):
    __tablename__ = "endpoints"

    endpoint_id = Column(String(64), primary_key=True)
    display_name = Column(String(128), nullable=False)
    endpoint_type = Column(String(32), default="simulated", nullable=False)
    auth_token = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    is_local = Column(Boolean, default=False, nullable=False)
    last_seen_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    public_key_pqc = Column(Text, nullable=True)
    public_key_x25519 = Column(Text, nullable=True)
    pqc_fingerprint = Column(String(128), nullable=True)
    pqc_algorithm = Column(String(64), default="ML-KEM-768", nullable=True)

    def to_dict(self, include_sensitive: bool = False):
        data = {
            "endpoint_id": self.endpoint_id,
            "display_name": self.display_name,
            "endpoint_type": self.endpoint_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "enabled": self.enabled,
            "is_local": self.is_local,
            "last_seen_at": self.last_seen_at.isoformat() if self.last_seen_at else None,
            "public_key_pqc": self.public_key_pqc,
            "public_key_x25519": self.public_key_x25519,
            "pqc_fingerprint": self.pqc_fingerprint,
            "pqc_algorithm": self.pqc_algorithm,
        }
        if include_sensitive:
            data["auth_token"] = self.auth_token
        return data


class Message(Base):
    __tablename__ = "messages"

    message_id = Column(String(64), primary_key=True, default=generate_uuid)
    client_idempotency_key = Column(String(128), nullable=False, index=True)
    sender_endpoint_id = Column(String(64), ForeignKey("endpoints.endpoint_id"), nullable=False, index=True)
    recipient_endpoint_id = Column(String(64), ForeignKey("endpoints.endpoint_id"), nullable=False, index=True)
    message_type = Column(String(32), default="TEXT", nullable=False)
    incident_id = Column(String(64), nullable=True, index=True)
    payload = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    priority = Column(Integer, default=1, nullable=False)
    current_state = Column(String(32), default="QUEUED", nullable=False, index=True)
    attempt_count = Column(Integer, default=0, nullable=False)
    next_attempt_at = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    last_error_code = Column(String(64), nullable=True)
    last_error_at = Column(DateTime(timezone=True), nullable=True)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    receiver_stored_at = Column(DateTime(timezone=True), nullable=True)
    sender_acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    signed_ack_receipt = Column(Text, nullable=True)

    # Post-Quantum Cryptography (PQC) metadata
    envelope_version = Column(Integer, default=3, nullable=False)
    pqc_scheme = Column(String(64), default="ML-KEM-768+X25519", nullable=True)
    pqc_verified = Column(Boolean, default=False, nullable=False)
    pqc_downgrade_warning = Column(Boolean, default=False, nullable=False)

    # Concurrency control & worker leases
    worker_lease_id = Column(String(64), nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("sender_endpoint_id", "client_idempotency_key", name="uq_sender_idempotency"),
        Index("ix_messages_queue_poll", "current_state", "next_attempt_at"),
    )

    def to_dict(self):
        return {
            "message_id": self.message_id,
            "client_idempotency_key": self.client_idempotency_key,
            "sender_endpoint_id": self.sender_endpoint_id,
            "recipient_endpoint_id": self.recipient_endpoint_id,
            "message_type": self.message_type,
            "incident_id": self.incident_id,
            "payload": self.payload,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "priority": self.priority,
            "current_state": self.current_state,
            "attempt_count": self.attempt_count,
            "retry_count": self.attempt_count,
            "max_retries": 5,
            "next_attempt_at": self.next_attempt_at.isoformat() if self.next_attempt_at else None,
            "next_retry_at": self.next_attempt_at.isoformat() if self.next_attempt_at else None,
            "worker_lease_id": self.worker_lease_id,
            "lease_expires_at": self.lease_expires_at.isoformat() if self.lease_expires_at else None,
            "last_error_code": self.last_error_code,
            "last_error_at": self.last_error_at.isoformat() if self.last_error_at else None,
            "accepted_at": self.accepted_at.isoformat() if self.accepted_at else None,
            "receiver_stored_at": self.receiver_stored_at.isoformat() if self.receiver_stored_at else None,
            "sender_acknowledged_at": self.sender_acknowledged_at.isoformat() if self.sender_acknowledged_at else None,
            "signed_ack_receipt": self.signed_ack_receipt,
            "envelope_version": self.envelope_version,
            "pqc_scheme": self.pqc_scheme,
            "pqc_verified": self.pqc_verified,
            "pqc_downgrade_warning": self.pqc_downgrade_warning,
        }


class InboxItem(Base):
    __tablename__ = "inbox"

    inbox_id = Column(String(64), primary_key=True, default=generate_uuid)
    recipient_endpoint_id = Column(String(64), ForeignKey("endpoints.endpoint_id"), nullable=False, index=True)
    message_id = Column(String(64), ForeignKey("messages.message_id"), nullable=False, index=True)
    stored_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    integrity_status = Column(String(32), default="VALID", nullable=False)
    processing_status = Column(String(32), default="STORED", nullable=False)
    envelope_version = Column(Integer, default=3, nullable=True)
    pqc_scheme = Column(String(64), default="ML-KEM-768+X25519", nullable=True)
    pqc_verified = Column(Boolean, default=False, nullable=True)
    pqc_downgrade_warning = Column(Boolean, default=False, nullable=True)

    __table_args__ = (
        UniqueConstraint("recipient_endpoint_id", "message_id", name="uq_recipient_message"),
    )

    def to_dict(self):
        return {
            "inbox_id": self.inbox_id,
            "recipient_endpoint_id": self.recipient_endpoint_id,
            "message_id": self.message_id,
            "stored_at": self.stored_at.isoformat() if self.stored_at else None,
            "integrity_status": self.integrity_status,
            "processing_status": self.processing_status,
            "envelope_version": self.envelope_version,
            "pqc_scheme": self.pqc_scheme,
            "pqc_verified": self.pqc_verified,
            "pqc_downgrade_warning": self.pqc_downgrade_warning,
        }


class DeliveryAttempt(Base):
    __tablename__ = "delivery_attempts"

    attempt_id = Column(String(64), primary_key=True, default=generate_uuid)
    message_id = Column(String(64), ForeignKey("messages.message_id"), nullable=False, index=True)
    attempt_number = Column(Integer, nullable=False)
    start_timestamp = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    completion_timestamp = Column(DateTime(timezone=True), nullable=True)
    result = Column(String(32), nullable=False)  # SUCCESS, RETRYABLE_ERROR, PERMANENT_ERROR, DROPPED
    transport_state = Column(String(32), nullable=False)  # ONLINE, OFFLINE
    error_code = Column(String(64), nullable=True)
    retryability = Column(Boolean, default=False, nullable=False)
    acknowledgement_state = Column(String(32), default="NONE", nullable=False)

    def to_dict(self):
        return {
            "attempt_id": self.attempt_id,
            "message_id": self.message_id,
            "attempt_number": self.attempt_number,
            "start_timestamp": self.start_timestamp.isoformat() if self.start_timestamp else None,
            "completion_timestamp": self.completion_timestamp.isoformat() if self.completion_timestamp else None,
            "result": self.result,
            "transport_state": self.transport_state,
            "error_code": self.error_code,
            "retryability": self.retryability,
            "acknowledgement_state": self.acknowledgement_state,
        }


class Acknowledgement(Base):
    __tablename__ = "acknowledgements"

    ack_id = Column(String(64), primary_key=True, default=generate_uuid)
    original_message_id = Column(String(64), ForeignKey("messages.message_id"), nullable=False, index=True)
    ack_type = Column(String(32), default="RECEIVED", nullable=False)
    origin_endpoint = Column(String(64), ForeignKey("endpoints.endpoint_id"), nullable=False)
    destination_endpoint = Column(String(64), ForeignKey("endpoints.endpoint_id"), nullable=False)
    creation_timestamp = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    validation_status = Column(String(32), default="VALID", nullable=False)
    delivery_status = Column(String(32), default="DELIVERED", nullable=False)

    __table_args__ = (
        UniqueConstraint("original_message_id", "ack_type", name="uq_message_ack_type"),
    )

    def to_dict(self):
        return {
            "ack_id": self.ack_id,
            "message_id": self.original_message_id,
            "ack_type": self.ack_type,
            "sender_endpoint_id": self.origin_endpoint,
            "recipient_endpoint_id": self.destination_endpoint,
            "timestamp": self.creation_timestamp.isoformat() if self.creation_timestamp else None,
            "integrity_verified": (self.validation_status == "VALID"),
            "delivery_status": self.delivery_status,
        }


class MessageEvent(Base):
    __tablename__ = "message_events"

    # Phase 8 Multi-Hop Mesh Event Constants
    BUNDLE_TTL_EXPIRED = "BUNDLE_TTL_EXPIRED"
    ROUTING_LOOP_DETECTED = "ROUTING_LOOP_DETECTED"
    CUSTODY_ACK_RECEIVED = "CUSTODY_ACK_RECEIVED"
    MESH_REROUTE_DIVERTED = "MESH_REROUTE_DIVERTED"

    event_id = Column(String(64), primary_key=True, default=generate_uuid)
    message_id = Column(String(64), ForeignKey("messages.message_id"), nullable=False, index=True)
    event_type = Column(String(64), nullable=False)
    timestamp = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    source_endpoint = Column(String(64), nullable=False)
    safe_metadata = Column(JSON, default=dict, nullable=False)
    error_code = Column(String(64), nullable=True)

    def to_dict(self):
        return {
            "event_id": self.event_id,
            "message_id": self.message_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "source_endpoint": self.source_endpoint,
            "safe_metadata": self.safe_metadata,
            "details": self.safe_metadata,
            "error_code": self.error_code,
        }


class User(Base):
    __tablename__ = "users"

    user_id = Column(String(64), primary_key=True, default=generate_uuid)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(32), default="OPERATOR", nullable=False)  # ADMINISTRATOR, OPERATOR, VIEWER
    enabled = Column(Boolean, default=True, nullable=False)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    last_login_at = Column(DateTime, nullable=True)

    def set_password(self, password: str):
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)

    def is_locked(self) -> bool:
        if self.locked_until and self.locked_until > utcnow():
            return True
        return False

    def register_failed_attempt(self, max_attempts: int = 5, lock_duration_minutes: int = 15):
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= max_attempts:
            from datetime import timedelta
            self.locked_until = utcnow() + timedelta(minutes=lock_duration_minutes)

    def reset_failed_attempts(self):
        self.failed_login_attempts = 0
        self.locked_until = None

    def to_dict(self, include_sensitive: bool = False):
        data = {
            "user_id": self.user_id,
            "username": self.username,
            "role": self.role,
            "enabled": self.enabled,
            "is_locked": self.is_locked(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
        }
        if include_sensitive:
            data["failed_login_attempts"] = self.failed_login_attempts
            data["locked_until"] = self.locked_until.isoformat() if self.locked_until else None
        return data


class UserSession(Base):
    __tablename__ = "user_sessions"

    session_id = Column(String(64), primary_key=True, default=generate_uuid)
    user_id = Column(String(64), ForeignKey("users.user_id"), nullable=False, index=True)
    session_token = Column(String(128), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(String(256), nullable=True)

    def is_valid(self) -> bool:
        return (not self.revoked) and (self.expires_at > utcnow())

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "revoked": self.revoked,
            "is_valid": self.is_valid(),
        }


class SecurityAuditLog(Base):
    __tablename__ = "security_audit_logs"

    # Phase 8 Multi-Hop Mesh Audit Constants
    BUNDLE_TTL_EXPIRED = "BUNDLE_TTL_EXPIRED"
    ROUTING_LOOP_DETECTED = "ROUTING_LOOP_DETECTED"
    CUSTODY_TRANSFER_FAILED = "CUSTODY_TRANSFER_FAILED"
    MESH_REROUTE_DIVERTED = "MESH_REROUTE_DIVERTED"

    audit_id = Column(String(64), primary_key=True, default=generate_uuid)
    event_type = Column(String(64), nullable=False, index=True)  # LOGIN_SUCCESS, LOGIN_FAILED, ACCOUNT_LOCKED, LOGOUT, PERMISSION_DENIED
    user_id = Column(String(64), nullable=True, index=True)
    endpoint_id = Column(String(64), nullable=True, index=True)
    ip_address = Column(String(64), nullable=True)
    details = Column(JSON, default=dict, nullable=False)
    timestamp = Column(DateTime, default=utcnow, nullable=False, index=True)

    def __init__(self, *args, **kwargs):
        if "action" in kwargs and "event_type" not in kwargs:
            kwargs["event_type"] = kwargs.pop("action")
        sev = kwargs.pop("severity", None)
        if "details" not in kwargs or kwargs["details"] is None:
            kwargs["details"] = {}
        if sev is not None and isinstance(kwargs["details"], dict):
            if "severity" not in kwargs["details"]:
                kwargs["details"]["severity"] = sev
        super().__init__(*args, **kwargs)

    @property
    def log_id(self) -> str:
        return self.audit_id

    @property
    def action(self) -> str:
        return self.event_type

    @action.setter
    def action(self, val: str):
        self.event_type = val

    @property
    def severity(self) -> str:
        if isinstance(self.details, dict):
            return self.details.get("severity", "INFO")
        return "INFO"

    @severity.setter
    def severity(self, val: str):
        if not isinstance(self.details, dict):
            self.details = {}
        self.details["severity"] = val

    def to_dict(self):
        return {
            "audit_id": self.audit_id,
            "log_id": self.audit_id,
            "event_type": self.event_type,
            "action": self.event_type,
            "severity": self.severity,
            "user_id": self.user_id,
            "endpoint_id": self.endpoint_id,
            "ip_address": self.ip_address,
            "details": self.details,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class SystemSetting(Base):
    """Durable key/value store for node-wide configuration.

    The API server and the delivery worker run as *separate processes*, so a
    runtime switch such as "send over the Motorola radio path" has to live
    somewhere both can see. This table is that shared switch.
    """

    __tablename__ = "system_settings"

    key = Column(String(64), primary_key=True)
    value = Column(String(255), nullable=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    def to_dict(self):
        return {
            "key": self.key,
            "value": self.value,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

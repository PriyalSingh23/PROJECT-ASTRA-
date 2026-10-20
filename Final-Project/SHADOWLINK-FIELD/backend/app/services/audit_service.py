from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from app.core.database import utcnow
from app.models.audit import AuditLog

SENSITIVE_KEYS = {"password", "secret", "token", "payload", "key", "authorization", "private_key"}


def sanitize_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively redacts sensitive values from dictionaries."""
    sanitized = {}
    for k, v in data.items():
        if any(s in k.lower() for s in SENSITIVE_KEYS):
            sanitized[k] = "[REDACTED]"
        elif isinstance(v, dict):
            sanitized[k] = sanitize_dict(v)
        elif isinstance(v, list):
            sanitized[k] = [sanitize_dict(item) if isinstance(item, dict) else item for item in v]
        else:
            sanitized[k] = v
    return sanitized


class AuditService:
    """Service for capturing sanitized operational audit logs."""

    @classmethod
    def record_action(
        cls,
        session: Session,
        action: str,
        resource_type: str,
        user_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        safe_details = sanitize_dict(details or {})
        log_entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            safe_details=safe_details,
            ip_address=ip_address,
            timestamp=utcnow(),
        )
        session.add(log_entry)
        session.commit()
        return log_entry

    @classmethod
    def get_logs(
        cls,
        session: Session,
        action: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        query = session.query(AuditLog)
        if action:
            query = query.filter_by(action=action)
        if user_id:
            query = query.filter_by(user_id=user_id)
        logs = query.order_by(AuditLog.timestamp.desc()).limit(limit).all()
        return [l.to_dict() for l in logs]

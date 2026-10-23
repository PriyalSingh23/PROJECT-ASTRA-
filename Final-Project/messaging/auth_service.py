import os
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from messaging.models import User, UserSession, SecurityAuditLog, utcnow
from messaging.security_config import (
    DEMO_ADMIN_PASSWORD,
    DEMO_OPERATOR_PASSWORD,
    DEMO_VIEWER_PASSWORD,
    get_seed_password,
)


SESSION_DURATION_HOURS = 1
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15


class AuthService:
    @staticmethod
    def create_user(
        session: Session,
        username: str,
        password: str,
        role: str = "OPERATOR",
        actor_user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> User:
        username = username.strip().lower()
        if not username or len(username) < 3:
            raise ValueError("Username must be at least 3 characters long")
        if not password or len(password) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if role not in ("ADMINISTRATOR", "OPERATOR", "VIEWER"):
            raise ValueError(f"Invalid role: {role}")

        existing = session.query(User).filter(User.username == username).first()
        if existing:
            raise ValueError(f"User '{username}' already exists")

        user = User(username=username, role=role)
        user.set_password(password)
        session.add(user)
        session.flush()

        audit = SecurityAuditLog(
            event_type="USER_CREATED",
            user_id=actor_user_id,
            ip_address=ip_address,
            details={"created_user_id": user.user_id, "username": username, "role": role},
        )
        session.add(audit)
        session.commit()
        return user

    @staticmethod
    def authenticate_user(
        session: Session,
        username: str,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[Optional[User], Optional[UserSession], Optional[str]]:
        username = username.strip().lower()
        user = session.query(User).filter(User.username == username).first()

        if not user:
            audit = SecurityAuditLog(
                event_type="LOGIN_FAILED_UNKNOWN_USER",
                ip_address=ip_address,
                details={"username_attempted": username},
            )
            session.add(audit)
            session.commit()
            return None, None, "Invalid username or password"

        if not user.enabled:
            return None, None, "Account is disabled. Contact system administrator."

        if user.is_locked():
            remaining_mins = int((user.locked_until - utcnow()).total_seconds() / 60) + 1
            audit = SecurityAuditLog(
                event_type="LOGIN_ATTEMPT_ON_LOCKED_ACCOUNT",
                user_id=user.user_id,
                ip_address=ip_address,
                details={"username": username, "remaining_minutes": remaining_mins},
            )
            session.add(audit)
            session.commit()
            return None, None, f"Account is locked due to repeated failed logins. Try again in ~{remaining_mins} minutes."

        if not user.check_password(password):
            user.register_failed_attempt(
                max_attempts=MAX_FAILED_ATTEMPTS,
                lock_duration_minutes=LOCKOUT_DURATION_MINUTES,
            )
            is_locked_now = user.is_locked()
            event = "ACCOUNT_LOCKED" if is_locked_now else "LOGIN_FAILED"
            audit = SecurityAuditLog(
                event_type=event,
                user_id=user.user_id,
                ip_address=ip_address,
                details={
                    "username": username,
                    "failed_attempts": user.failed_login_attempts,
                    "locked": is_locked_now,
                },
            )
            session.add(audit)
            session.commit()
            if is_locked_now:
                return None, None, f"Too many failed login attempts. Account locked for {LOCKOUT_DURATION_MINUTES} minutes."
            return None, None, "Invalid username or password"

        # Authentication success
        user.reset_failed_attempts()
        user.last_login_at = utcnow()

        # Create session
        token = secrets.token_hex(32)
        expires_at = utcnow() + timedelta(hours=SESSION_DURATION_HOURS)
        user_session = UserSession(
            user_id=user.user_id,
            session_token=token,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        session.add(user_session)

        audit = SecurityAuditLog(
            event_type="LOGIN_SUCCESS",
            user_id=user.user_id,
            ip_address=ip_address,
            details={"username": username, "session_id": user_session.session_id},
        )
        session.add(audit)
        session.commit()
        return user, user_session, None

    @staticmethod
    def validate_session(session: Session, session_token: str) -> Optional[User]:
        if not session_token:
            return None
        sess = session.query(UserSession).filter(
            UserSession.session_token == session_token,
            UserSession.revoked == False,
        ).first()

        if not sess or not sess.is_valid():
            return None

        user = session.query(User).filter(User.user_id == sess.user_id).first()
        if not user or not user.enabled:
            return None
        return user

    @staticmethod
    def revoke_session(session: Session, session_token: str, ip_address: Optional[str] = None) -> bool:
        sess = session.query(UserSession).filter(UserSession.session_token == session_token).first()
        if not sess:
            return False
        sess.revoked = True
        audit = SecurityAuditLog(
            event_type="LOGOUT",
            user_id=sess.user_id,
            ip_address=ip_address,
            details={"session_id": sess.session_id},
        )
        session.add(audit)
        session.commit()
        return True

    @staticmethod
    def seed_default_users(session: Session):
        """Seeds demo users only outside production; production must avoid known defaults."""
        count = session.query(User).count()
        if count:
            if os.environ.get("SHADOWCOMM_ENV", "development").strip().lower() in {"prod", "production"}:
                legacy_credentials = (
                    ("admin", (DEMO_ADMIN_PASSWORD, "FieldAdmin2026!")),
                    ("operator", (DEMO_OPERATOR_PASSWORD, "OperatorPassword123!")),
                    ("viewer", (DEMO_VIEWER_PASSWORD,)),
                )
                for username, demo_passwords in legacy_credentials:
                    user = session.query(User).filter_by(username=username).first()
                    if user and any(user.check_password(password) for password in demo_passwords):
                        raise RuntimeError(
                            f"User '{username}' still uses a known demo password. "
                            "Rotate that account password before production startup."
                        )
            return

        admin_pw = get_seed_password("SHADOWCOMM_ADMIN_PASSWORD", DEMO_ADMIN_PASSWORD)
        operator_pw = get_seed_password("SHADOWCOMM_OPERATOR_PASSWORD", DEMO_OPERATOR_PASSWORD)

        admin = User(username="admin", role="ADMINISTRATOR")
        admin.set_password(admin_pw)
        session.add(admin)

        operator = User(username="operator", role="OPERATOR")
        operator.set_password(operator_pw)
        session.add(operator)

        audit = SecurityAuditLog(
            event_type="SYSTEM_INITIAL_USERS_SEEDED",
            details={"seeded_users": ["admin", "operator"]},
        )
        session.add(audit)
        session.commit()

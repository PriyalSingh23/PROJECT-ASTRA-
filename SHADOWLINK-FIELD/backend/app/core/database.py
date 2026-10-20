import os
from contextlib import contextmanager
from datetime import datetime, timezone
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.core.config import settings

Base = declarative_base()


def utcnow() -> datetime:
    """Returns timezone-naive UTC timestamp for consistent SQLite / Postgres storage."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_engine(db_url: str = settings.DATABASE_URL):
    connect_args = {}
    if db_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False, "timeout": 15}

    engine = create_engine(db_url, connect_args=connect_args)

    if db_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency yielding a transactional DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context(custom_db_url: str = None):
    """Context manager for standalone worker scripts or tests."""
    if custom_db_url:
        eng = get_engine(custom_db_url)
        factory = sessionmaker(autocommit=False, autoflush=False, bind=eng)
        session = factory()
    else:
        session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def init_db(custom_engine=None):
    """Creates all tables and idempotently seeds initial entities."""
    target_engine = custom_engine or engine
    Base.metadata.create_all(bind=target_engine)

    from app.models.endpoint import Endpoint
    from app.models.user import User
    from app.core.security import get_password_hash, UserRole

    SessionCls = sessionmaker(bind=target_engine)
    session = SessionCls()
    try:
        # Seed default Admin and Operator accounts
        admin_user = session.query(User).filter_by(username="admin").first()
        if not admin_user:
            admin_user = User(
                user_id="usr-admin-001",
                username="admin",
                password_hash=get_password_hash("FieldOps@2026!"),
                role=UserRole.ADMIN.value,
                display_name="Senior Field Administrator",
                enabled=True,
                created_at=utcnow(),
            )
            session.add(admin_user)

        operator_user = session.query(User).filter_by(username="operator").first()
        if not operator_user:
            operator_user = User(
                user_id="usr-operator-001",
                username="operator",
                password_hash=get_password_hash("TacticalOps@2026!"),
                role=UserRole.OPERATOR.value,
                display_name="Tactical Radio Operator",
                enabled=True,
                created_at=utcnow(),
            )
            session.add(operator_user)

        # Seed Endpoint A and Endpoint B
        ep_a = session.query(Endpoint).filter_by(endpoint_id="endpoint-a").first()
        if not ep_a:
            ep_a = Endpoint(
                endpoint_id="endpoint-a",
                display_name="Endpoint Alpha (Forward Post)",
                endpoint_type="tactical_node",
                enabled=True,
                created_at=utcnow(),
                last_seen_at=utcnow(),
            )
            session.add(ep_a)

        ep_b = session.query(Endpoint).filter_by(endpoint_id="endpoint-b").first()
        if not ep_b:
            ep_b = Endpoint(
                endpoint_id="endpoint-b",
                display_name="Endpoint Bravo (Command Base)",
                endpoint_type="command_node",
                enabled=True,
                created_at=utcnow(),
                last_seen_at=utcnow(),
            )
            session.add(ep_b)

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

import os
import threading
from contextlib import contextmanager
from typing import Optional
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from messaging.security_config import (
    DEMO_TOKEN_ENDPOINT_A,
    DEMO_TOKEN_ENDPOINT_B,
    get_endpoint_token,
    ensure_distinct_endpoint_tokens,
    is_production,
)
from messaging.models import Base, Endpoint, SystemSetting, utcnow

DEFAULT_DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../shadowcomm_messaging.db")
)


def get_engine(db_path: Optional[str] = None):
    if not db_path:
        db_path = DEFAULT_DB_PATH
    dir_name = os.path.dirname(os.path.abspath(db_path))
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False, "timeout": 15},
    )

    # Enable WAL mode and robust concurrency pragmas for SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        # busy_timeout MUST be set before journal_mode: switching a database
        # into WAL mode requires a write lock, and at server boot the embedded
        # worker thread opens a second connection concurrently. Without the
        # timeout already in place, that race surfaces as
        # "sqlite3.OperationalError: database is locked".
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


_engines = {}
_session_factories = {}


def get_session_factory(db_path: Optional[str] = None):
    global _engines, _session_factories
    if not db_path:
        db_path = DEFAULT_DB_PATH
    if db_path not in _session_factories:
        eng = get_engine(db_path)
        _engines[db_path] = eng
        _session_factories[db_path] = sessionmaker(autocommit=False, autoflush=False, bind=eng)
    return _session_factories[db_path]


_init_lock = threading.Lock()


def init_db(db_path: str = DEFAULT_DB_PATH, station_id: Optional[str] = None):
    """Initializes schema and idempotently seeds Endpoint A and Endpoint B.

    Serialized with a process-wide lock. At server boot the embedded delivery
    worker thread and the main thread call this concurrently; without the lock
    both run ``CREATE TABLE`` and the loser crashes with
    "table endpoints already exists".
    """
    with _init_lock:
        return _init_db(db_path, station_id=station_id)


def _init_db(db_path: str = DEFAULT_DB_PATH, station_id: Optional[str] = None):
    engine = get_engine(db_path)

    # Safe SQLite column migrations for existing databases
    with engine.connect() as conn:
        try:
            columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(endpoints)").fetchall()]
            if columns and "auth_token" not in columns:
                conn.exec_driver_sql("ALTER TABLE endpoints ADD COLUMN auth_token VARCHAR(128)")
            if columns and "is_local" not in columns:
                conn.exec_driver_sql("ALTER TABLE endpoints ADD COLUMN is_local BOOLEAN DEFAULT 0")
            if columns and "public_key_pqc" not in columns:
                conn.exec_driver_sql("ALTER TABLE endpoints ADD COLUMN public_key_pqc TEXT")
            if columns and "public_key_x25519" not in columns:
                conn.exec_driver_sql("ALTER TABLE endpoints ADD COLUMN public_key_x25519 TEXT")
            if columns and "pqc_fingerprint" not in columns:
                conn.exec_driver_sql("ALTER TABLE endpoints ADD COLUMN pqc_fingerprint VARCHAR(128)")
            if columns and "pqc_algorithm" not in columns:
                conn.exec_driver_sql("ALTER TABLE endpoints ADD COLUMN pqc_algorithm VARCHAR(64) DEFAULT 'ML-KEM-768'")
        except Exception:
            pass

        try:
            msg_cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(messages)").fetchall()]
            if msg_cols and "incident_id" not in msg_cols:
                conn.exec_driver_sql("ALTER TABLE messages ADD COLUMN incident_id VARCHAR(64)")
            if msg_cols and "signed_ack_receipt" not in msg_cols:
                conn.exec_driver_sql("ALTER TABLE messages ADD COLUMN signed_ack_receipt TEXT")
            if msg_cols and "envelope_version" not in msg_cols:
                conn.exec_driver_sql("ALTER TABLE messages ADD COLUMN envelope_version INTEGER DEFAULT 3")
            if msg_cols and "pqc_scheme" not in msg_cols:
                conn.exec_driver_sql("ALTER TABLE messages ADD COLUMN pqc_scheme VARCHAR(64) DEFAULT 'ML-KEM-768+X25519'")
            if msg_cols and "pqc_verified" not in msg_cols:
                conn.exec_driver_sql("ALTER TABLE messages ADD COLUMN pqc_verified BOOLEAN DEFAULT 0")
            if msg_cols and "pqc_downgrade_warning" not in msg_cols:
                conn.exec_driver_sql("ALTER TABLE messages ADD COLUMN pqc_downgrade_warning BOOLEAN DEFAULT 0")
        except Exception:
            pass

        try:
            inbox_cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(inbox)").fetchall()]
            if inbox_cols and "envelope_version" not in inbox_cols:
                conn.exec_driver_sql("ALTER TABLE inbox ADD COLUMN envelope_version INTEGER DEFAULT 3")
            if inbox_cols and "pqc_scheme" not in inbox_cols:
                conn.exec_driver_sql("ALTER TABLE inbox ADD COLUMN pqc_scheme VARCHAR(64) DEFAULT 'ML-KEM-768+X25519'")
            if inbox_cols and "pqc_verified" not in inbox_cols:
                conn.exec_driver_sql("ALTER TABLE inbox ADD COLUMN pqc_verified BOOLEAN DEFAULT 0")
            if inbox_cols and "pqc_downgrade_warning" not in inbox_cols:
                conn.exec_driver_sql("ALTER TABLE inbox ADD COLUMN pqc_downgrade_warning BOOLEAN DEFAULT 0")
        except Exception:
            pass

    Base.metadata.create_all(bind=engine)

    SessionCls = sessionmaker(bind=engine)
    session = SessionCls()
    try:
        # Determine local station designations
        is_a_local = (station_id == "endpoint-a") if station_id else False
        is_b_local = (station_id == "endpoint-b") if station_id else False

        # Seed Endpoint A
        from messaging.keyring import keyring_manager
        keyring_a = keyring_manager.load_or_generate_keyring("endpoint-a")
        token_a = get_endpoint_token("SHADOWCOMM_TOKEN_ENDPOINT_A", DEMO_TOKEN_ENDPOINT_A)
        ep_a = session.query(Endpoint).filter_by(endpoint_id="endpoint-a").first()
        if not ep_a:
            ep_a = Endpoint(
                endpoint_id="endpoint-a",
                display_name="Endpoint Alpha (Forward Node A)",
                endpoint_type="simulated",
                auth_token=token_a,
                enabled=True,
                is_local=is_a_local,
                public_key_pqc=keyring_a["mlkem768"]["encapsulation_key_b64"],
                public_key_x25519=keyring_a["x25519"]["public_key_b64"],
                pqc_fingerprint=keyring_a["mlkem768"]["fingerprint"],
                pqc_algorithm="ML-KEM-768",
                created_at=utcnow(),
                last_seen_at=utcnow(),
            )
            session.add(ep_a)
        else:
            if is_production() and ep_a.auth_token != token_a:
                raise RuntimeError(
                    "Stored endpoint-a token does not match SHADOWCOMM_TOKEN_ENDPOINT_A. "
                    "Perform an explicit credential rotation before production startup."
                )
            if not ep_a.auth_token:
                ep_a.auth_token = token_a
            if station_id:
                ep_a.is_local = is_a_local
            if not ep_a.public_key_pqc:
                ep_a.public_key_pqc = keyring_a["mlkem768"]["encapsulation_key_b64"]
                ep_a.public_key_x25519 = keyring_a["x25519"]["public_key_b64"]
                ep_a.pqc_fingerprint = keyring_a["mlkem768"]["fingerprint"]
                ep_a.pqc_algorithm = "ML-KEM-768"

        # Seed Endpoint B
        keyring_b = keyring_manager.load_or_generate_keyring("endpoint-b")
        token_b = get_endpoint_token("SHADOWCOMM_TOKEN_ENDPOINT_B", DEMO_TOKEN_ENDPOINT_B)
        ensure_distinct_endpoint_tokens(token_a, token_b)
        ep_b = session.query(Endpoint).filter_by(endpoint_id="endpoint-b").first()
        if not ep_b:
            ep_b = Endpoint(
                endpoint_id="endpoint-b",
                display_name="Endpoint Bravo (Command Base B)",
                endpoint_type="simulated",
                auth_token=token_b,
                enabled=True,
                is_local=is_b_local,
                public_key_pqc=keyring_b["mlkem768"]["encapsulation_key_b64"],
                public_key_x25519=keyring_b["x25519"]["public_key_b64"],
                pqc_fingerprint=keyring_b["mlkem768"]["fingerprint"],
                pqc_algorithm="ML-KEM-768",
                created_at=utcnow(),
                last_seen_at=utcnow(),
            )
            session.add(ep_b)
        else:
            if is_production() and ep_b.auth_token != token_b:
                raise RuntimeError(
                    "Stored endpoint-b token does not match SHADOWCOMM_TOKEN_ENDPOINT_B. "
                    "Perform an explicit credential rotation before production startup."
                )
            if not ep_b.auth_token:
                ep_b.auth_token = token_b
            if station_id:
                ep_b.is_local = is_b_local
            if not ep_b.public_key_pqc:
                ep_b.public_key_pqc = keyring_b["mlkem768"]["encapsulation_key_b64"]
                ep_b.public_key_x25519 = keyring_b["x25519"]["public_key_b64"]
                ep_b.pqc_fingerprint = keyring_b["mlkem768"]["fingerprint"]
                ep_b.pqc_algorithm = "ML-KEM-768"

        # Record station metadata in system_settings table if station_id provided
        if station_id:
            st_name = "Station Alpha" if station_id == "endpoint-a" else "Station Bravo" if station_id == "endpoint-b" else "Standalone Node"
            settings_map = {
                "node_station_id": station_id,
                "node_station_name": st_name,
            }
            for k, v in settings_map.items():
                setting = session.query(SystemSetting).filter_by(key=k).first()
                if not setting:
                    setting = SystemSetting(key=k, value=v)
                    session.add(setting)
                else:
                    setting.value = v

        # Seed initial administrator and operator users
        from messaging.auth_service import AuthService
        AuthService.seed_default_users(session)

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def get_db_session(db_path: Optional[str] = None):
    """Transactional context manager for database operations."""
    if not db_path:
        try:
            from flask import current_app, has_app_context
            if has_app_context() and current_app.config.get("DB_PATH"):
                db_path = current_app.config["DB_PATH"]
            else:
                db_path = DEFAULT_DB_PATH
        except Exception:
            db_path = DEFAULT_DB_PATH

    if not db_path:
        db_path = DEFAULT_DB_PATH

    factory = get_session_factory(db_path)
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


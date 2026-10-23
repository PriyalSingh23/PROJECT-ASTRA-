"""Runtime secret configuration with an explicit fail-closed production mode.

Set SHADOWCOMM_ENV=production in deployed environments. Demo defaults remain
available for local development/test compatibility, but production startup must
supply unique credentials with adequate minimum lengths.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

DEMO_SECRET_KEY = "shadowcomm-dev-secret-key-offline-demo"
DEMO_TOKEN_ENDPOINT_A = "token-pilot-alpha-94e82b"
DEMO_TOKEN_ENDPOINT_B = "token-pilot-bravo-31a7c4"
DEMO_ADMIN_PASSWORD = "AdminPass@2026!"
DEMO_OPERATOR_PASSWORD = "OperatorPass@2026!"
DEMO_VIEWER_PASSWORD = "ViewerPassword123!"

_PRODUCTION_MODES = {"prod", "production"}
_WARNED_NAMES: set[str] = set()
_PLACEHOLDER_PREFIXES = (
    "replace_", "generate_", "your_", "placeholder", "change_me", "changeme",
)
_PLACEHOLDER_VALUES = {"", "replace-me", "change-me", "secret", "password"}


def is_production() -> bool:
    """Return True only for an explicitly declared production environment."""
    return os.environ.get("SHADOWCOMM_ENV", "development").strip().lower() in _PRODUCTION_MODES


def endpoint_authentication_required() -> bool:
    """Require endpoint tokens in production even if the legacy opt-in flag is unset."""
    if is_production():
        return True
    return os.environ.get("SHADOWCOMM_REQUIRE_AUTH", "false").strip().lower() in {
        "true", "1", "yes",
    }


def _is_placeholder(value: str) -> bool:
    candidate = value.strip().lower()
    return (
        candidate in _PLACEHOLDER_VALUES
        or candidate.startswith(_PLACEHOLDER_PREFIXES)
        or "string_here" in candidate
        or "replace with" in candidate
    )


def _warn_once(name: str, message: str) -> None:
    if name not in _WARNED_NAMES:
        logger.warning("SECURITY WARNING: %s: %s", name, message)
        _WARNED_NAMES.add(name)


def get_configured_secret(
    name: str,
    development_default: Optional[str],
    *,
    minimum_length: int = 32,
    purpose: str = "secret",
) -> str:
    """Get an environment secret; reject missing/demo/weak values in production.

    This does not estimate entropy. It checks only minimum length, known demo
    defaults and obvious template placeholders; operators must still provision
    secrets from a cryptographically secure random source.
    """
    value = os.environ.get(name, "").strip()

    if is_production():
        if not value:
            raise RuntimeError(
                f"{name} is required when SHADOWCOMM_ENV=production ({purpose})."
            )
        if _is_placeholder(value):
            raise RuntimeError(
                f"{name} still contains a template placeholder; configure a unique production value."
            )
        if len(value) < minimum_length:
            raise RuntimeError(
                f"{name} must be at least {minimum_length} characters in production ({purpose})."
            )
        if development_default is not None and value == development_default:
            raise RuntimeError(
                f"{name} uses a known development/demo value; configure a unique production value."
            )
        return value

    if not value or value == development_default or _is_placeholder(value):
        if development_default is None:
            raise RuntimeError(f"{name} is not configured.")
        _warn_once(
            name,
            "using a development/demo fallback; set a unique value before deployment",
        )
        return development_default

    if len(value) < minimum_length:
        _warn_once(
            name,
            "configured value is shorter than the production minimum; production mode will reject it",
        )
    return value


def get_app_secret_key() -> str:
    """Resolve the shared Flask-session and receipt-HMAC secret."""
    return get_configured_secret(
        "SHADOWCOMM_SECRET_KEY",
        DEMO_SECRET_KEY,
        minimum_length=32,
        purpose="Flask session and receipt HMAC",
    )


def get_endpoint_token(name: str, development_default: str) -> str:
    """Resolve a device token, failing closed on missing/weak production tokens."""
    return get_configured_secret(
        name,
        development_default,
        minimum_length=32,
        purpose="endpoint authentication",
    )


def ensure_distinct_endpoint_tokens(token_a: str, token_b: str) -> None:
    """Require distinct A/B tokens in production; keep legacy demo behavior in development."""
    if is_production() and token_a == token_b:
        raise RuntimeError(
            "SHADOWCOMM_TOKEN_ENDPOINT_A and SHADOWCOMM_TOKEN_ENDPOINT_B must be different in production."
        )


def get_seed_password(name: str, development_default: str) -> str:
    """Resolve the first-run seed password without known production defaults."""
    return get_configured_secret(
        name,
        development_default,
        minimum_length=16,
        purpose="initial user password",
    )

def ensure_legacy_component_not_production(component: str, reason: str) -> None:
    """Prevent a known legacy/insecure component from running in production."""
    if is_production():
        raise RuntimeError(
            f"{component} is disabled when SHADOWCOMM_ENV=production: {reason}"
        )

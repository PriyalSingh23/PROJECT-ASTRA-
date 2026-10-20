import os
import hmac
import hashlib
import base64
from enum import Enum
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    OPERATOR = "OPERATOR"
    OBSERVER = "OBSERVER"


def get_password_hash(password: str) -> str:
    """Hashes password using PBKDF2-HMAC-SHA256 with 600,000 iterations and random 16B salt."""
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600000)
    return f"pbkdf2:sha256:600000${base64.b64encode(salt).decode('ascii')}${base64.b64encode(key).decode('ascii')}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies plaintext password against PBKDF2 formatted hash string."""
    try:
        algorithm, hash_name, iterations_str, salt_b64, key_b64 = hashed_password.split("$")[0].split(":") + hashed_password.split("$")[1:]
        iterations = int(iterations_str)
        salt = base64.b64decode(salt_b64.encode("ascii"))
        expected_key = base64.b64decode(key_b64.encode("ascii"))
        computed_key = hashlib.pbkdf2_hmac(hash_name, plain_password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(computed_key, expected_key)
    except Exception:
        return False


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Generates an HMAC-SHA256 signed JSON Web Token."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": now})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    """Decodes and validates JWT token expiration and signature."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    token: str = Depends(oauth2_scheme),
) -> Dict[str, Any]:
    """Extracts and verifies user claims from active token."""
    payload = decode_token(token)
    username: str = payload.get("sub")
    role: str = payload.get("role")
    user_id: str = payload.get("user_id")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"username": username, "role": role, "user_id": user_id}


def require_role(allowed_roles: List[UserRole]):
    """Role-Based Access Control decorator/dependency."""
    def role_checker(current_user: Dict[str, Any] = Depends(get_current_user)):
        user_role = current_user.get("role")
        if user_role not in [r.value for r in allowed_roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient role permissions. Required: {[r.value for r in allowed_roles]}",
            )
        return current_user
    return role_checker


# ==================== AUTHENTICATED ENCRYPTION (AES-256-GCM) ====================
class MessageCrypto:
    """Authenticated encryption utility for application-level message payloads."""

    @staticmethod
    def encrypt(plaintext: str, key_bytes: bytes, associated_data: Optional[bytes] = None) -> Dict[str, str]:
        """Encrypts UTF-8 plaintext with AES-256-GCM using unique 12-byte random nonce."""
        if len(key_bytes) != 32:
            raise ValueError("AES-256-GCM key must be exactly 32 bytes")
        aesgcm = AESGCM(key_bytes)
        nonce = os.urandom(12)
        ct_and_tag = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), associated_data)
        return {
            "nonce_b64": base64.b64encode(nonce).decode("ascii"),
            "ciphertext_b64": base64.b64encode(ct_and_tag).decode("ascii"),
            "algorithm": "AES-256-GCM",
        }

    @staticmethod
    def decrypt(ciphertext_b64: str, nonce_b64: str, key_bytes: bytes, associated_data: Optional[bytes] = None) -> str:
        """Decrypts and authenticates AES-256-GCM ciphertext."""
        if len(key_bytes) != 32:
            raise ValueError("AES-256-GCM key must be exactly 32 bytes")
        aesgcm = AESGCM(key_bytes)
        nonce = base64.b64decode(nonce_b64)
        ct_and_tag = base64.b64decode(ciphertext_b64)
        pt_bytes = aesgcm.decrypt(nonce, ct_and_tag, associated_data)
        return pt_bytes.decode("utf-8")

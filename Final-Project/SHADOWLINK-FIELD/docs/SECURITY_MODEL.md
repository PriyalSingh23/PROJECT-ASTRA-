# SHADOWLINK FIELD: Security Model & Cryptographic Architecture

## 1. Security Philosophy & Principles

In tactical, remote, and emergency-response operations, communications infrastructure is subject to physical capture, eavesdropping, traffic analysis, and spoofing. **SHADOWLINK FIELD** applies defense-in-depth across four distinct domains:
1. **User Authentication & Authorization**: Proving who is operating the software.
2. **Device Identity & Provisioning**: Proving which physical machine or radio terminal is connecting.
3. **Application-Layer Cryptography**: Ensuring message confidentiality and tamper evidence.
4. **Auditability & Log Sanitization**: Maintaining an immutable operational record without leaking secrets.

---

## 2. Authentication & Role-Based Access Control (RBAC)

### 2.1 Role Definitions
- **`ADMIN`**:
  - Full system configuration.
  - User and device provisioning.
  - Radio adapter arming and RF configuration.
  - Export of diagnostic and audit event logs.
- **`OPERATOR`**:
  - Message drafting, queueing, and dispatch.
  - Retrying failed messages.
  - Voice/PTT radio operation via approved adapters.
  - Viewing live telemetry and delivery timelines.
- **`OBSERVER`**:
  - Read-only monitoring of message boards, link statuses, and incident history.
  - No access to transmission or configuration endpoints.

### 2.2 Credentials & Session Tokens
- **Password Storage**: Passwords are never stored in plaintext. Passwords are hashed using PBKDF2-HMAC-SHA256 with 600,000 rounds and unique 16-byte random salts.
- **Session Tokens**: REST and WebSocket connections authenticate using HMAC-SHA256 signed JSON Web Tokens (JWT).
  - Access Token TTL: 15 minutes.
  - Refresh Token TTL: 7 days, stored in HTTP-only, SameSite secure cookies.
  - Revocation: Stored in an in-memory and database blacklist on operator logout.

---

## 3. Cryptographic Specification

### 3.1 Legacy Encryption Review & Deprecation
The original research implementation in `app.py` utilized AES-128 in CTR mode:
```python
# VULNERABLE LEGACY PATTERN
ctr = Counter.new(128, initial_value=0)
cipher = AES.new(self.key, AES.MODE_CTR, counter=ctr)
```
**Identified Vulnerabilities:**
1. **Static Nonce**: The counter starts at 0 for every transmission. Reusing the stream cipher key-stream allows trivial passive XOR decryption of plaintexts.
2. **No Authentication Tag**: Unauthenticated CTR mode is malleable. An adversary can modify bits in ciphertext with deterministic changes to the decrypted plaintext.
3. **Hard-coded Secret**: The demo key `"0123456789abcdef"` was compiled directly into source code.

### 3.2 SHADOWLINK FIELD Standard Cryptography
For application-level message encryption, the platform implements **AES-256-GCM** (Galois/Counter Mode) authenticated encryption:
- **Key Length**: 256 bits (32 bytes).
- **Nonce (IV)**: 96 bits (12 bytes) cryptographically random, generated per message via `os.urandom(12)`.
- **Authentication Tag**: 128 bits (16 bytes) verifying ciphertext integrity and authenticity.
- **Associated Authenticated Data (AAD)**: Plaintext envelope headers (`message_id`, `sender_endpoint_id`, `recipient_endpoint_id`, `created_at`) are included in AAD to prevent header splicing and replay attacks.

```
+-------------------------------------------------------------------------------+
|                            AES-256-GCM Wire Frame                             |
|                                                                               |
|  [ Version: 1B ] [ Key ID: 8B ] [ Nonce: 12B ] [ Ciphertext: N ] [ Tag: 16B ] |
+-------------------------------------------------------------------------------+
```

### 3.3 Key Management & Provisioning
- Secrets and keys are injected exclusively via environment variables (`SHADOWLINK_SECRET_KEY`, `SHADOWLINK_MASTER_KEY_FILE`) or encrypted key vaults.
- No cryptographic material is ever stored in application code, frontend bundles, or SQLite database tables in plaintext.

---

## 4. Audit Log Safety & Redaction

Diagnostic timeline events (`MessageEvent`) and system audit logs (`AuditLog`) must be safe for inspection by maintenance teams without exposing classified or sensitive operational data.

### Redaction Rules
1. **Plaintext Body**: The message `payload` is strictly excluded from `MessageEvent.safe_metadata` and `audit.log`. Only metadata (`payload_bytes`, `sha256_digest`, `message_type`, `priority`) is recorded.
2. **Secrets & Credentials**: Passwords, API keys, JWT tokens, and private keys are detected and redacted before logging.
3. **Hardware Registers**: Hardware diagnostic dumps exclude raw crypto module memory regions.

---

## 5. Input Validation & API Protection

1. **Payload Size Limits**: Strict 64 KB ceiling per message enforced by Pydantic validators (`MAX_PAYLOAD_BYTES = 65536`).
2. **Rate Limiting**: Dispatches throttled to 30 requests/minute per authenticated user to prevent queue exhaustion and denial-of-service.
3. **SQL Injection Defense**: All database queries use SQLAlchemy parameter binding; no dynamic raw SQL string interpolation is permitted.

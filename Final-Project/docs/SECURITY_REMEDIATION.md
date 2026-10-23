# SECURITY AUDIT & REMEDIATION REPORT

**Target Codebase**: `https://github.com/PriyalSingh23/Final-Project`  
**Evaluation Date**: October 2026  
**Security Classification**: Non-Critical Controlled Pilot Readiness  

---

## 1. Executive Summary

This report documents the security audit conducted on the legacy and messaging subsystems of **Final-Project**, establishes the remediation actions performed, and defines operational policies for a controlled, non-critical field pilot.

> [!WARNING]
> Historical commits in the public repository contain hardcoded cryptographic keys and secret keys. In accordance with strict project rules, **Git history has NOT been force-pushed or rewritten**. Instead, all historical keys are declared **permanently compromised**, invalidated, and replaced by runtime environment configurations.

---

## 2. Audit Findings & Threat Analysis

| Vulnerability ID | Description | Historical Location | Severity | Current Status |
|---|---|---|---|---|
| **SEC-01** | Hardcoded AES-128 Encryption Key (`0123456789abcdef`) | `app.py:27`, `index.html:357`, `lpi_v4/lpi_crypto.py:242` | **HIGH** | **REMEDIATED** in active code; env variable overrides enabled. |
| **SEC-02** | Hardcoded Flask session secret (`shadowcomm-secret-key`) | `app.py`, `messaging/server.py`, `messaging/ack_manager.py` | **MEDIUM** | Production-mode fail-closed guard added in the security branch; local-development fallback remains explicit and warns. Pending CI until the branch passes. |
| **SEC-03** | Permissive Wildcard CORS (`cors_allowed_origins="*"`) | `app.py:16` | **MEDIUM** | **REMEDIATED**; restricted to explicit origin list from `SHADOWCOMM_CORS_ORIGINS`. |
| **SEC-04** | Static zero-counter in AES-CTR (`Counter.new(128, initial_value=0)`) | `app.py`, legacy tests | **HIGH** | Fixed-counter design remains unsafe; the standalone prototype is blocked when `SHADOWCOMM_ENV=production`, but its crypto is not repaired. |
| **SEC-05** | Unauthenticated API Message Ingestion | `messaging/api.py:48` | **HIGH** | **REMEDIATED**; added `verify_auth` endpoint and `X-Endpoint-Token` validation. |
| **SEC-06** | Plaintext payload logging / event leakage | `messaging/models.py:185` | **LOW** | **REMEDIATED**; `to_dict()` sanitizes audit metadata. |
| **SEC-07** | Predictable seeded endpoint tokens and default account passwords | `messaging/db.py`, `messaging/auth_service.py` | **HIGH** | Production startup guard added on the security branch; missing/weak credentials, mismatched stored tokens, or documented demo passwords block startup. Pending CI. |

---

## 3. Detailed Audit of Git History

A search of the Git history identified the exact commits where secrets were committed:

```bash
$ git log -S "0123456789abcdef" --oneline
d241739 lpi_v4: complete covert-link stack that meets the metric targets
5f9f4c8 Add files via upload

$ git log -S "shadowcomm-secret-key" --oneline
5f9f4c8 Add files via upload
```

### Remediation Protocol for Exposed Historical Secrets
1. **Compromised Status**: The key `0123456789abcdef` and secret `shadowcomm-secret-key` are permanently untrusted and must never be used in production or field environments.
2. **No Destructive Rewriting**: Because force-pushing (`git push --force`) or rewriting repository history breaks collaborator workflows and risks data loss, the historical commits are preserved.
3. **Environment Isolation**: Development mode preserves demo fallbacks for local simulations and logs a high-visibility security warning. The follow-up production guard requires `SHADOWCOMM_ENV=production` explicitly and fails closed for missing, weak, or placeholder session secrets and endpoint credentials:
   ```
   [SECURITY WARNING] Insecure or default AES key in use. Rotate SHADOWCOMM_AES_KEY before production/pilot.
   [SECURITY WARNING] 'SHADOWCOMM_SECRET_KEY' environment variable not set. Using dev fallback.
   ```
4. **Gitignore Protection**: `.env` and `.env.local` have been added to `.gitignore`. A clean template is provided in `.env.example`.

---

## 4. Remediation Actions Implemented

### 4.1. Runtime secret configuration and production mode

The current implementation centralizes secret resolution in `messaging/security_config.py`. **Set `SHADOWCOMM_ENV=production` explicitly** on production deployment. The default remains `development` so local demo/test behavior is backward compatible; the production guard is not activated merely by omitting the variable.

When production mode is enabled:
- `SHADOWCOMM_SECRET_KEY` must be a unique, non-placeholder value of at least 32 characters. Flask session signing and acknowledgement-receipt HMAC use the same validated value.
- `SHADOWCOMM_TOKEN_ENDPOINT_A` and `SHADOWCOMM_TOKEN_ENDPOINT_B` must be unique, non-placeholder values of at least 32 characters.
- A new database requires `SHADOWCOMM_ADMIN_PASSWORD` and `SHADOWCOMM_OPERATOR_PASSWORD`, each at least 16 characters; existing admin/operator/viewer accounts with documented demo defaults block startup.
- If an existing database's stored endpoint token differs from the configured production token, startup fails and requires explicit credential rotation. The application does not silently rotate a stored credential.
- Flask session cookies are set Secure, HttpOnly and SameSite=Lax in production mode.
- The standalone `Final-Project/app.py` research prototype is blocked in production because its legacy AES-CTR implementation starts each encryption at the same counter. This prevents that component from being selected in production; it **does not repair the AES-CTR cryptographic design**.

The guard checks minimum lengths, known demo values and obvious placeholders. It cannot estimate secret entropy or replace a threat-model/security review. Generate fresh secrets from a cryptographically secure random source, protect them from logs/version control, use authenticated transport, and rotate any historically exposed credentials. Do not reuse the demonstration tokens/passwords below for any field deployment.

### 4.2. Independent Device Authentication (`X-Endpoint-Token`)
In [`messaging/models.py`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/messaging/models.py#L28-L48) and [`messaging/api.py`](file:///Users/sabhay/Downloads/PROJECT%2013OCT/Final-Project/messaging/api.py#L47-L95):
- The `Endpoint` model now stores an `auth_token` seeded from environment variables (`SHADOWCOMM_TOKEN_ENDPOINT_A`, `SHADOWCOMM_TOKEN_ENDPOINT_B`).
- Endpoint listing via `/api/v1/endpoints` strictly redacts the `auth_token`.
- Message ingestion requires either `X-Endpoint-Token` header, `Authorization: Bearer <token>`, or a token payload field when authentication is enabled (`SHADOWCOMM_REQUIRE_AUTH=true`).
- Device 1 on Endpoint A cannot forge messages on behalf of Endpoint B without presenting Endpoint B's valid secret token.

### 4.3. AES-CTR Two-Time Pad Vulnerability Analysis
In legacy `app.py`:
```python
ctr = Counter.new(128, initial_value=0)
cipher = AES.new(self.key, AES.MODE_CTR, counter=ctr)
```
- **Vulnerability**: Every message encrypted using `CryptoEngine` resets the counter to 0 with the same key. In CTR mode, this generates identical keystream blocks $K$.
- **Consequence**: An eavesdropper intercepting two ciphertexts $C_1 = P_1 \oplus K$ and $C_2 = P_2 \oplus K$ computes $C_1 \oplus C_2 = P_1 \oplus P_2$, completely cancelling out the encryption and exposing the plaintexts.
- **Pilot Roadmap**: The reliable messaging subsystem (`messaging/`) currently operates with cleartext/simulated envelopes for deterministic verification, bypassing this vulnerable path. For production, AES-256-GCM with a 96-bit random nonce per message must replace legacy AES-CTR.

---

### 4.4 Production fail-closed configuration guard (ASTRA follow-up)

The security branch `codex/astra-secret-config-guard-2026-10-23` adds an explicit production mode. **Set `SHADOWCOMM_ENV=production` deliberately**; the default remains `development` for backward-compatible local simulations, so merely omitting the setting does not activate these production checks.

When production mode is enabled:

- `messaging.server` requires a non-placeholder `SHADOWCOMM_SECRET_KEY` of at least 32 characters and sets secure, HttpOnly, SameSite=Lax session-cookie options.
- Receipt HMAC generation uses the same validated application secret rather than its own predictable fallback.
- Both endpoint tokens must be configured as unique values of at least 32 characters. If an existing database holds a different token, startup stops and requires explicit credential rotation; the application does not silently rewrite the stored database token.
- A fresh database requires separately configured initial administrator/operator passwords of at least 16 characters. Existing users with the known demo passwords `AdminPass@2026!` or `OperatorPass@2026!` prevent production startup until they are rotated.
- The standalone research prototype `Final-Project/app.py` is blocked entirely in production because its legacy AES-CTR implementation resets the counter for each message. This does not repair the prototype's cryptography; it makes the restriction enforceable when the production mode is correctly set.

The guard checks minimum lengths and obvious placeholder/default values, not entropy or a full deployment's security posture. Generate credentials with a cryptographically secure source, rotate any historical/pilot secrets, protect the database and keyring files, and use authenticated transport. This branch makes no automatic database migration or token rotation.

**Validation status:** the production guard, tests, template, and documentation are under review; do not claim the guard is merged or CI-validated until the pull-request workflow succeeds.

## 5. Security Checklist for Field Pilot Deployment

Before conducting the two-device local network pilot:

- [ ] Copy `.env.example` to `.env`.
- [ ] Generate a secure 32-byte secret key:
  ```bash
  python3 -c "import secrets; print(secrets.token_hex(32))"
  ```
- [ ] Assign distinct device tokens for Endpoint A and Endpoint B.
- [ ] Export environment variables:
  ```bash
  export SHADOWCOMM_ENV=production
  export SHADOWCOMM_ENV=production
  export SHADOWCOMM_REQUIRE_AUTH=true
  export SHADOWCOMM_SECRET_KEY="$(python3 -c "import secrets; print(secrets.token_hex(32))")"
  export SHADOWCOMM_TOKEN_ENDPOINT_A="$(python3 -c "import secrets; print(secrets.token_hex(32))")"
  export SHADOWCOMM_TOKEN_ENDPOINT_B="$(python3 -c "import secrets; print(secrets.token_hex(32))")"
  export SHADOWCOMM_ADMIN_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
  export SHADOWCOMM_OPERATOR_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
  # Existing DBs require explicit endpoint-token/password rotation before production startup.
  ```
- [ ] Ensure the pilot runs on a protected WPA2/WPA3 local Wi-Fi network without public internet exposure.

---

## 6. Security Threat Model

| Asset | Potential Threat | Existing / Implemented Control | Residual Risk | Status / Plan |
|:---|:---|:---|:---|:---|
| **Message Confidentiality** | Keystream reuse via static AES-CTR counter | Isolated in legacy prototype; messaging subsystem decoupled | Legacy code in `app.py` susceptible if invoked | Deprecate legacy crypto; deploy AES-256-GCM envelope |
| **Message Integrity** | Eavesdropper tamper/bit-flip in transit | Receiver-verified SHA-256 digest + signed durable receipts | Unauthenticated cleartext payloads over LAN if unencrypted | Mandate TLS / authenticated envelope for pilot |
| **Endpoint Identity** | Device impersonation / unauthorized send | Token-based authentication (`X-Endpoint-Token`) | Tokens stored in client memory/IndexedDB | Role-based sessions and hardware key storage (TPM/Secure Enclave) |
| **Queue Availability** | DoS flood / queue exhaustion | Max payload limits (64 KB) & rate limits | Local SQLite lock contention under concurrent load | SQLite WAL mode + busy timeout 5000ms |
| **Audit Trails** | Log tampering / diagnostic data leak | Serializers sanitize tokens and redact sensitive payload fields | Audit log stored in standard database | Append-only tamper-evident event log |

---

## 7. Versioned Authenticated-Encryption Specification (AES-256-GCM)

To resolve the legacy AES-CTR zero-counter flaw, new messages adopt a versioned envelope format:

```
+---------------+----------------+-------------------+--------------------+----------------+
| Version (1B)  | Nonce (12B)    | Tag (16B)         | Ciphertext (var)   | Sig/Receipt    |
| 0x02 (v2-GCM) | Cryptorandom   | Poly1305 / GMAC   | AES-256 Payload    | Optional HMAC  |
+---------------+----------------+-------------------+--------------------+----------------+
```

### Nonce Management Rules:
1. Every message generates a **cryptographically fresh 96-bit (12-byte) random nonce** via `secrets.token_bytes(12)` or `os.urandom(12)`.
2. Under no circumstance may the nonce counter be reset to 0 with the same key.
3. Decryption strictly validates the 16-byte authentication tag; tampered ciphertexts are rejected before any decoding is performed.

---

## 8. Role-Based Access Control & User Administration Architecture

For multi-user deployments:
- **Roles**:
  - `OPERATOR`: Permitted to compose messages, view local outbox, and inspect received inbox items.
  - `ADMINISTRATOR`: Permitted to register endpoints, configure transport parameters, re-seed tokens, view system audit logs, and trigger maintenance drills.
- **Session Lifecycle**:
  - Cryptographically signed session tokens (HMAC-SHA256) with 60-minute idle expiry.
  - Account lockout after 5 consecutive failed authentication attempts (15-minute throttle cooldown).

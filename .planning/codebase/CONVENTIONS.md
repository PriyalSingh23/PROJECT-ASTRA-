# Coding Conventions

**Analysis Date:** 2026-10-19

## Naming Patterns

**Files:**
- **Python:** Lowercase `snake_case` with descriptive suffixes for modules and services: `Final-Project/messaging/auth_service.py`, `Final-Project/messaging/crypto_v2.py`, `Final-Project/messaging/state_machine.py`.
- **Tests:** Prefixed with `test_` matching target module or capability: `Final-Project/tests/test_offline_messaging.py`, `Final-Project/tests/test_security_auth.py`, `Final-Project/tests/integration/test_adapters.py`.
- **React / TypeScript Components:** Upper `PascalCase` with `.tsx` extension: `Final-Project/frontend/src/components/MessagesView.tsx`, `Final-Project/frontend/src/components/Header.tsx`, `Final-Project/frontend/src/components/SecurityModal.tsx`.
- **TypeScript Services / Utilities:** Lower `camelCase` with `.ts` extension: `Final-Project/frontend/src/services/api.ts`, `Final-Project/frontend/src/services/outboxDb.ts`.
- **GNU Radio Flowgraphs:** Lowercase with model/protocol tags: `Final-Project/rx_lpi_cgan.grc`, `Final-Project/lpi_v4/tx_lpi_v4.grc`.

**Functions:**
- **Python:** `snake_case` verbs describing action: `encrypt_v2_gcm()`, `validate_transition()`, `get_db_session()`, `drain_worker()`. Internal helpers prefixed with leading underscore: `_safe_int()`, `_generate_aad()`.
- **TypeScript:** `camelCase` verbs: `fetchData()`, `submitMessage()`, `getHealth()`, `handleStatusChange()`.

**Variables:**
- **Python:** `snake_case` for local instances: `client_idempotency_key`, `recipient_endpoint_id`, `db_session`.
- **TypeScript:** `camelCase`: `isBackendHealthy`, `activeTab`, `queueStats`, `currentUser`.
- **Constants:** Upper `SCREAMING_SNAKE_CASE` across Python and TypeScript: `MAX_PAYLOAD_BYTES`, `ENVELOPE_VERSION_V2_GCM`, `NONCE_LENGTH_BYTES`, `TAG_LENGTH_BYTES`.

**Types:**
- **Python Classes / ORM Models:** `PascalCase`: `Message`, `Endpoint`, `MessageEvent`, `QueueWorker`, `MessagingService`.
- **Python Enums:** `PascalCase` class with uppercase attributes: `class MessageState(str, Enum): SUBMITTED = "SUBMITTED"`.
- **TypeScript Interfaces & Types:** `PascalCase`: `Message`, `InboxMessage`, `QueueStats`, `WorkstationTab`, `MessageState`.

---

## Code Style

**Formatting:**
- **Python:** PEP 8 compliance with 4-space indentation. 100-character line lengths encouraged. Docstrings formatted using Google/Sphinx style with parameter definitions and exception declarations.
- **Frontend / TypeScript:** ESLint/Prettier/Biome compatibility via Oxlint configuration (`Final-Project/frontend/.oxlintrc.json`). 2-space indentation, single quotes for strings, no semicolons preferred in React components.

**Linting:**
- **Python:** Pyright configuration (`Final-Project/pyrightconfig.json`) enforcing type checking across `.` root. Python 3.12 target.
- **TypeScript / React:** Oxlint (`Final-Project/frontend/.oxlintrc.json`) configured with `react`, `typescript`, and `oxc` plugins:
  - `"react/rules-of-hooks": "error"`
  - `"react/only-export-components": ["warn", { "allowConstantExport": true }]`

---

## Import Organization

**Order:**

**Python:**
1. Standard library imports (`os`, `sys`, `time`, `uuid`, `secrets`, `hashlib`, `typing`, `datetime`).
2. Third-party core dependencies (`pytest`, `sqlalchemy`, `flask`, `Crypto.Cipher.AES`, `torch`, `numpy`, `scipy`).
   - **CRITICAL MAC OS LINKER SAFETY:** `import torch` MUST precede `numpy` and `scipy` imports across all entry points (e.g., `Final-Project/tests/conftest.py`) to prevent Apple Silicon OpenBLAS symbol collisions (`SIGSEGV 139`).
3. Local application package imports (`messaging.models`, `messaging.db`, `messaging.crypto_v2`, `integration.manager`).

**TypeScript:**
1. React core hooks and types (`import React, { useState, useEffect, useCallback } from 'react'`).
2. Third-party UI / utility libraries (`lucide-react`, `recharts`).
3. Shared component layouts and views (`./components/Header`, `./components/MessagesView`).
4. Type definitions (`import { Message, QueueStats } from './types'`).
5. Internal service singletons (`import { api } from './services/api'`).

**Path Aliases:**
- Node/TypeScript: Relative path imports (`./components/...`, `../services/...`) defined in `Final-Project/frontend/tsconfig.json`.
- Python: Root-level package imports relying on repository root added to `sys.path` or editable install (`from messaging.db import get_db_session`).

---

## Error Handling

**Patterns:**
- **Custom Exception Hierarchies:** Explicit inheritance from domain base errors rather than catching generic `Exception`:
  - `CryptoError` -> `AuthenticationError`, `InvalidEnvelopeError` in `Final-Project/messaging/crypto_v2.py`.
  - `ValueError` -> `InvalidStateTransitionError` in `Final-Project/messaging/state_machine.py`.
  - `RuntimeError` -> `StarVSafetyLockoutError` in `Final-Project/integration/starv/adapter.py`.
- **API Boundary Sanitization:** Safe query parameter parsing preventing 500 errors on invalid inputs (e.g., `_safe_int(value, default)` in `Final-Project/messaging/api.py`).
- **Database Rollbacks:** Session context managers in `Final-Project/messaging/db.py` ensuring atomic rollbacks on exceptions and releasing pool connections.
- **Frontend Error Boundaries:** Promises handled with `.catch()` falling back to neutral states or descriptive error banners rather than unhandled rejections (e.g., `Final-Project/frontend/src/services/api.ts`).

---

## Logging

**Framework:**
- Standard Python `logging` module (`logging.getLogger("QueueWorker")`, `logging.getLogger("shadowcomm.transport.lpi_cgan")`).
- Console `console.error` and `console.warn` in frontend service layers (`Final-Project/frontend/src/services/api.ts`).

**Patterns:**
- Structured format with timestamp, level, and logger name: `logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")`.
- State transitions logged at `INFO`: `logger.info(f"Message {message_id} successfully DELIVERED to {recipient}")`.
- Exceptions logged with stack traces using `exc_info=True`: `logger.error(f"Unexpected error in worker loop: {e}", exc_info=True)`.

---

## Comments

**When to Comment:**
- Critical hardware safety constraints (e.g., STAR-V software lockout comments in `Final-Project/integration/starv/adapter.py`).
- Linker and architecture compatibility quirks (e.g., `import torch` pre-import explanation in `Final-Project/tests/conftest.py`).
- Cryptographic envelope format specifications (e.g., 96-bit nonce documentation in `Final-Project/messaging/crypto_v2.py`).

**JSDoc/TSDoc:**
- Used for service methods in `Final-Project/frontend/src/services/api.ts` and `Final-Project/frontend/src/services/outboxDb.ts` to describe API parameters, return types, and offline caching semantics.

---

## Function Design

**Size:**
- Single-responsibility functions under 50 lines for pure logic and math (`derive_key_256`, `encrypt_v2_gcm`).
- Complex orchestration and lifecycle methods encapsulated within service classes (`MessagingService`, `QueueWorker`, `TransportManager`).

**Parameters:**
- Type hints on all public interfaces: `def encrypt_v2_gcm(plaintext: str or bytes, key: bytes or str, associated_data: Optional[bytes] = None) -> bytes:`.
- Optional parameters positioned at end with defaults.

**Return Values:**
- Structured dictionaries or typed Pydantic/SQLAlchemy models: `{"success": True, "delivery_id": "...", "metrics": {...}}`.
- Strict boolean or explicit None returns for predicate checks.

---

## Module Design

**Exports:**
- Explicit symbols imported directly from modules (`from messaging.models import Message, Endpoint`).
- Clean Blueprint isolation for REST routes: `api_v1 = Blueprint("messaging_api_v1", __name__, url_prefix="/api/v1")` in `Final-Project/messaging/api.py`.

**Barrel Files:**
- Centralized TypeScript type export in `Final-Project/frontend/src/types/index.ts` re-exporting `MessageState`, `Message`, `InboxMessage`, `QueueStats`, `User`, `Endpoint`.
- Component directory exports in `Final-Project/frontend/src/components/`.

---

*Convention analysis: 2026-10-19*

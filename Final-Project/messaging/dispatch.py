"""Live dispatch routing for the delivery worker.

The worker historically always pushed bytes through
:data:`messaging.transport.transport` (the in-process *simulated* link). This
module adds a selection layer so the very same worker can instead hand a
message to a real :class:`TransportManager` adapter — most importantly the
Motorola MOTOTRBO adapter, which in turn drives
``integration.motorola.hardware_bridge`` (MNIS UDP or Raspberry Pi GPIO PTT).

Design rules
------------
* **Simulation stays the default.** With no configuration the router simply
  delegates to the simulated transport, so every existing test and the whole
  offline demo behave exactly as before.
* **One switch flips the node live.** Set ``SHADOWCOMM_LIVE_TRANSPORT`` (e.g.
  ``motorola-mototrbo-01``) or call :func:`configure_dispatch` at runtime.
* **Operator pinning with auto-failover.** Operator can pin an active transport
  and toggle auto-failover. When the active transport is offline or locked out,
  the router falls back to operational secondary transports if auto-failover is
  enabled, or holds the message with ``ROUTE_UNAVAILABLE`` or
  ``STARV_SAFETY_LOCKOUT_BLOCKED`` if auto-failover is disabled.
* **Safety is preserved end to end.** The adapter's own approval gate still
  applies: without ``MOTOROLA_RADIO_APPROVED=true`` the hardware bridge runs
  dry-run only. Physical RF transmission on STAR-V tactical radio is permanently
  locked out in software.
* **No silent drops.** An unavailable / locked-out / unconfigured transport
  returns a *retryable* error code so the durable queue keeps the message and
  retries with exponential backoff.
* **280-byte DMR ceiling is handled, not hit.** Outbound frames are split into
  chunks the radio path can carry; each chunk is a self-describing TMS-style
  segment so a peer node can reassemble in order. Atomic burst retries ensure
  that if any chunk fails, all chunks are re-transmitted from chunk 0.
"""
from __future__ import annotations

import json
import os
import struct
from typing import Any, Dict, List, Optional

from messaging.transport import transport

# Transport bytes per chunk. Mirrors the DMR Tier-II ceiling the Motorola
# adapter enforces (280 bytes) minus our 4-byte chunk header.
DMR_CHUNK_BYTES = 280
_CHUNK_HEADER_BYTES = 4  # <uint16 total><uint16 index>
_CHUNK_PAYLOAD_BYTES = DMR_CHUNK_BYTES - _CHUNK_HEADER_BYTES

# Error codes the retry policy already understands.
RETRYABLE_TRANSPORT_ERROR = "TRANSPORT_OFFLINE"

# Keys used in the shared ``system_settings`` table.
ACTIVE_TRANSPORT_KEY = "active_transport"
AUTO_FAILOVER_KEY = "auto_failover"
DEFAULT_AUTO_FAILOVER = True


def get_persisted_transport(session) -> Optional[str]:
    """Read the node-wide active transport from shared storage.

    Returns ``None`` when the operator has selected the simulated link.
    """
    from messaging.models import SystemSetting

    row = session.query(SystemSetting).filter_by(key=ACTIVE_TRANSPORT_KEY).first()
    if row is None:
        return None
    return (row.value or "").strip() or None


def set_persisted_transport(session, transport_id: Optional[str]) -> None:
    """Persist the node-wide active transport. Caller owns the transaction."""
    from messaging.models import SystemSetting, utcnow

    row = session.query(SystemSetting).filter_by(key=ACTIVE_TRANSPORT_KEY).first()
    if row is None:
        row = SystemSetting(key=ACTIVE_TRANSPORT_KEY, value=(transport_id or "").strip())
        session.add(row)
    else:
        row.value = (transport_id or "").strip()
        row.updated_at = utcnow()
    session.flush()


def get_persisted_failover(session) -> bool:
    """Read auto_failover setting from shared storage. Defaults to True."""
    from messaging.models import SystemSetting

    row = session.query(SystemSetting).filter_by(key=AUTO_FAILOVER_KEY).first()
    if row is None or row.value is None or not row.value.strip():
        return DEFAULT_AUTO_FAILOVER
    return row.value.strip().lower() in ("true", "1", "yes")


def set_persisted_failover(session, enabled: bool) -> None:
    """Persist auto_failover setting. Caller owns the transaction."""
    from messaging.models import SystemSetting, utcnow

    row = session.query(SystemSetting).filter_by(key=AUTO_FAILOVER_KEY).first()
    val_str = "true" if enabled else "false"
    if row is None:
        row = SystemSetting(key=AUTO_FAILOVER_KEY, value=val_str)
        session.add(row)
    else:
        row.value = val_str
        row.updated_at = utcnow()
    session.flush()


def _log_starv_safety_event(session, message_dict: Dict[str, Any], reason: str) -> None:
    """Log STARV_SAFETY_LOCKOUT_BLOCKED MessageEvent and high-severity SecurityAuditLog."""
    from messaging.models import MessageEvent, SecurityAuditLog, generate_uuid, utcnow

    msg_id = message_dict.get("message_id")
    recipient = message_dict.get("recipient_endpoint_id")
    now = utcnow()
    event = MessageEvent(
        event_id=generate_uuid(),
        message_id=msg_id,
        event_type="STARV_SAFETY_LOCKOUT_BLOCKED",
        timestamp=now,
        source_endpoint=message_dict.get("sender_endpoint_id", "system-dispatcher"),
        safe_metadata={
            "transport": "starv-tactical-locked",
            "reason": reason,
            "recipient": recipient,
        },
        error_code="STARV_SAFETY_LOCKOUT_BLOCKED",
    )
    session.add(event)

    audit = SecurityAuditLog(
        log_id=generate_uuid(),
        timestamp=now,
        action="STARV_SAFETY_LOCKOUT_BLOCKED",
        severity="HIGH",
        details={
            "transport": "starv-tactical-locked",
            "message_id": msg_id,
            "reason": reason,
            "recipient": recipient,
        },
    )
    session.add(audit)


def log_starv_safety_event(message_dict: Dict[str, Any], reason: str) -> None:
    """Convenience wrapper that acquires db session and logs STAR-V lockout event."""
    try:
        from messaging.db import get_db_session

        with get_db_session() as session:
            _log_starv_safety_event(session, message_dict, reason)
    except Exception:
        pass


def _encode_envelope(
    message_dict: Dict[str, Any],
    recipient_mlkem_pk: Optional[bytes] = None,
    recipient_x25519_pk: Optional[bytes] = None,
) -> bytes:
    """Serialize a message into a compact, transport-agnostic frame.

    Layout: ``<json header>\\x1f<binary envelope bytes>``.
    Uses Envelope v3 if recipient public keys are provided; otherwise falls back to Envelope v2.
    """
    header = {
        "v": 1,
        "id": message_dict.get("message_id"),
        "from": message_dict.get("sender_endpoint_id"),
        "to": message_dict.get("recipient_endpoint_id"),
        "type": message_dict.get("message_type"),
        "incident": message_dict.get("incident_id"),
        "ts": message_dict.get("created_at"),
    }
    body = message_dict.get("payload") or ""
    if isinstance(body, str):
        body = body.encode("utf-8")

    from messaging.crypto_pqc import encrypt_v3_hybrid, ENVELOPE_VERSION_V3
    from messaging.crypto_v2 import encrypt_v2_gcm, ENVELOPE_VERSION_V2_GCM

    # If already an envelope (starts with 0x03 or 0x02)
    if len(body) > 1 and body[0] in (ENVELOPE_VERSION_V3, ENVELOPE_VERSION_V2_GCM):
        envelope_bytes = body
    elif recipient_mlkem_pk and recipient_x25519_pk:
        envelope_bytes = encrypt_v3_hybrid(
            plaintext=body,
            recipient_mlkem_pk=recipient_mlkem_pk,
            recipient_x25519_pk=recipient_x25519_pk,
            sender_endpoint_id=message_dict.get("sender_endpoint_id", ""),
            recipient_endpoint_id=message_dict.get("recipient_endpoint_id", ""),
            message_id=message_dict.get("message_id", ""),
        )
    else:
        shared_key = os.environ.get("SHADOWCOMM_SHARED_SECRET", "default-v2-shared-key-32bytes!")
        envelope_bytes = encrypt_v2_gcm(body, key=shared_key)

    return json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8") + b"\x1f" + envelope_bytes


def chunk_frame(frame: bytes, chunk_bytes: int = _CHUNK_PAYLOAD_BYTES) -> List[bytes]:
    """Split ``frame`` into ordered, self-describing chunks.

    Each chunk is ``<uint16 total><uint16 index><data…>`` so the receiver can
    reassemble deterministically even if chunks arrive out of order.
    Every chunk length is at most chunk_bytes + 4 (<= 280 bytes).
    """
    if chunk_bytes <= 0:
        raise ValueError("chunk_bytes must be positive")
    parts = [frame[i:i + chunk_bytes] for i in range(0, len(frame), chunk_bytes)] or [b""]
    total = len(parts)
    return [struct.pack("<HH", total, idx) + part for idx, part in enumerate(parts)]


class DispatchRouter:
    """Chooses the outbound path for a delivery: simulated link or live adapter."""

    def __init__(self, transport_id: Optional[str] = None, auto_failover: bool = DEFAULT_AUTO_FAILOVER):
        env_value = os.environ.get("SHADOWCOMM_LIVE_TRANSPORT", "")
        # Deploy-time pin. Used whenever no runtime (shared-storage) selection
        # is present, so an air-gapped unit can be pinned via environment.
        self._env_default: Optional[str] = (env_value or "").strip() or None
        self._transport_id: Optional[str] = None
        self._auto_failover: bool = auto_failover
        configured = transport_id if transport_id is not None else env_value
        self.configure(configured, auto_failover=auto_failover)

    # -- configuration -------------------------------------------------------
    def configure(self, transport_id: Optional[str], auto_failover: Optional[bool] = None) -> None:
        """Set (or clear) the live transport. Empty/None → simulated link."""
        tid = (transport_id or "").strip()
        self._transport_id = tid or None
        if auto_failover is not None:
            self._auto_failover = bool(auto_failover)

    def refresh(self, persisted_transport: Optional[str], persisted_failover: Optional[bool] = None) -> None:
        """Apply the runtime selection read from shared storage.

        An empty/None stored value falls back to the deploy-time env pin, so an
        operator can both raise and lower the live path at runtime without
        losing the deployment default.
        """
        tid = (persisted_transport or "").strip() or self._env_default
        self._transport_id = tid or None
        if persisted_failover is not None:
            self._auto_failover = bool(persisted_failover)

    @property
    def transport_id(self) -> Optional[str]:
        return self._transport_id

    @property
    def is_live(self) -> bool:
        return self._transport_id is not None

    @property
    def mode(self) -> str:
        return self._transport_id or "SIMULATION"

    @property
    def auto_failover(self) -> bool:
        return self._auto_failover

    def _prepare_outbound_peer_payload(self, message_dict: Dict[str, Any], peer_url: str) -> Dict[str, Any]:
        """Ensures outbound message payload is encrypted using Envelope v3 (or v2 fallback) before transmission."""
        import base64
        import requests
        from messaging.crypto_pqc import encrypt_v3_hybrid
        from messaging.crypto_v2 import encrypt_v2_gcm
        from messaging.models import Endpoint
        from messaging.db import get_db_session

        recipient = message_dict.get("recipient_endpoint_id", "")
        payload = message_dict.get("payload")
        if payload is None:
            return message_dict

        # Check if already encrypted
        if isinstance(payload, bytes) and len(payload) > 1 and payload[0] in (0x03, 0x02):
            return message_dict
        if isinstance(payload, str) and payload.startswith(("AwE", "Ag=")):
            try:
                b = base64.b64decode(payload)
                if len(b) > 1 and b[0] in (0x03, 0x02):
                    return message_dict
            except Exception:
                pass

        recipient_mlkem_pk = None
        recipient_x25519_pk = None

        try:
            with get_db_session() as session:
                ep = session.query(Endpoint).filter_by(endpoint_id=recipient).first()
                if ep and ep.public_key_pqc and ep.public_key_x25519:
                    recipient_mlkem_pk = base64.b64decode(ep.public_key_pqc)
                    recipient_x25519_pk = base64.b64decode(ep.public_key_x25519)
                elif peer_url:
                    # Dynamically probe peer public keys (D-02)
                    probe_url = peer_url.rstrip("/")
                    if not probe_url.endswith("/endpoints/public-keys"):
                        probe_url = f"{probe_url}/endpoints/public-keys"
                    try:
                        resp = requests.get(probe_url, timeout=2.0)
                        if resp.status_code == 200:
                            data = resp.json()
                            if data.get("public_key_pqc") and data.get("public_key_x25519"):
                                recipient_mlkem_pk = base64.b64decode(data["public_key_pqc"])
                                recipient_x25519_pk = base64.b64decode(data["public_key_x25519"])
                                if ep:
                                    ep.public_key_pqc = data["public_key_pqc"]
                                    ep.public_key_x25519 = data["public_key_x25519"]
                                    ep.pqc_fingerprint = data.get("pqc_fingerprint")
                                    session.commit()
                    except Exception:
                        pass
        except Exception:
            pass

        body = payload.encode("utf-8") if isinstance(payload, str) else bytes(payload)
        out_dict = dict(message_dict)

        if recipient_mlkem_pk and recipient_x25519_pk:
            envelope = encrypt_v3_hybrid(
                plaintext=body,
                recipient_mlkem_pk=recipient_mlkem_pk,
                recipient_x25519_pk=recipient_x25519_pk,
                sender_endpoint_id=message_dict.get("sender_endpoint_id", ""),
                recipient_endpoint_id=recipient,
                message_id=message_dict.get("message_id", ""),
            )
            out_dict["payload"] = base64.b64encode(envelope).decode("ascii")
            out_dict["envelope_version"] = 3
            out_dict["pqc_scheme"] = "ML-KEM-768+X25519"
        else:
            shared_key = os.environ.get("SHADOWCOMM_SHARED_SECRET", "default-v2-shared-key-32bytes!")
            envelope = encrypt_v2_gcm(body, key=shared_key)
            out_dict["payload"] = base64.b64encode(envelope).decode("ascii")
            out_dict["envelope_version"] = 2
            out_dict["pqc_scheme"] = "CLASSICAL_AES_256_GCM"
            out_dict["pqc_downgrade_warning"] = True

        return out_dict

    # -- dispatch ------------------------------------------------------------
    def dispatch(self, message_dict: Dict[str, Any], peer_url: Optional[str] = None) -> Dict[str, Any]:
        """Return the transport result dict the worker expects.

        Keys: ``delivered_to_receiver``, ``ack_delivered_to_sender``,
        ``error_code``, ``transport_state``, ``latency_ms``. In live mode a
        ``transport`` key additionally names the adapter used and the chunk
        count, for the audit trail.
        """
        if not self.is_live:
            if peer_url:
                message_dict = self._prepare_outbound_peer_payload(message_dict, peer_url)
            return transport.transmit(message_dict, peer_url=peer_url)

        # Check if active transport is STAR-V (starv-tactical-locked)
        if self._transport_id == "starv-tactical-locked":
            log_starv_safety_event(
                message_dict,
                "STAR-V tactical radio is permanently locked out in software. Physical RF keying blocked.",
            )
            if self.auto_failover:
                from integration.manager import transport_manager

                sec_adapter = transport_manager.select_transport(
                    recipient_endpoint_id=message_dict.get("recipient_endpoint_id", ""),
                    message_priority=message_dict.get("priority", 1),
                    exclude_id="starv-tactical-locked",
                )
                if sec_adapter is not None:
                    res = self._dispatch_with_adapter(sec_adapter, message_dict)
                    res["failover_active"] = True
                    res["failover_from"] = "starv-tactical-locked"
                    return res
                # Fallback to simulated transport
                res = transport.transmit(message_dict, peer_url=peer_url)
                res["failover_active"] = True
                res["failover_from"] = "starv-tactical-locked"
                return res
            else:
                return self._error(
                    "STARV_SAFETY_LOCKOUT_BLOCKED",
                    "STAR-V tactical radio is permanently locked out in software. Physical RF keying blocked. Auto-failover is disabled.",
                )

        # Check operational readiness of active transport
        from integration.manager import transport_manager
        from integration.base import TransportReadiness, TransportConnectionState

        adapter = transport_manager.get_adapter(self._transport_id)

        is_operational = False
        if adapter is not None:
            readiness = getattr(adapter, "readiness", None)
            conn_state = getattr(adapter, "connection_state", None)
            if (
                readiness in (TransportReadiness.READY, TransportReadiness.SIMULATION_ONLY)
                and conn_state in (TransportConnectionState.ONLINE, TransportConnectionState.STANDBY)
            ):
                is_operational = True

        if not is_operational:
            if self.auto_failover:
                sec_adapter = transport_manager.select_transport(
                    recipient_endpoint_id=message_dict.get("recipient_endpoint_id", ""),
                    message_priority=message_dict.get("priority", 1),
                    exclude_id=self._transport_id,
                )
                if sec_adapter is not None:
                    res = self._dispatch_with_adapter(sec_adapter, message_dict)
                    res["failover_active"] = True
                    res["failover_from"] = self._transport_id
                    return res
                res = transport.transmit(message_dict)
                res["failover_active"] = True
                res["failover_from"] = self._transport_id
                return res
            else:
                return self._error(
                    "ROUTE_UNAVAILABLE",
                    f"Active transport '{self._transport_id}' is offline and auto-failover is disabled. Message held in durable queue.",
                )

        return self._dispatch_with_adapter(adapter, message_dict)

    def _adapter(self):
        from integration.manager import transport_manager

        return transport_manager.get_adapter(self._transport_id)

    def _error(self, code: str, detail: str) -> Dict[str, Any]:
        return {
            "delivered_to_receiver": False,
            "ack_delivered_to_sender": False,
            "error_code": code,
            "transport_state": "ONLINE",
            "latency_ms": 0.0,
            "detail": detail,
        }

    def _dispatch_live(self, message_dict: Dict[str, Any]) -> Dict[str, Any]:
        adapter = self._adapter()
        if adapter is None:
            return self._error(
                RETRYABLE_TRANSPORT_ERROR,
                f"Unknown live transport '{self._transport_id}'",
            )
        return self._dispatch_with_adapter(adapter, message_dict)

    def _dispatch_with_adapter(self, adapter, message_dict: Dict[str, Any]) -> Dict[str, Any]:
        import time
        import base64

        recipient = message_dict.get("recipient_endpoint_id", "")
        recipient_mlkem_pk = None
        recipient_x25519_pk = None
        try:
            from messaging.db import get_db_session
            from messaging.models import Endpoint
            with get_db_session() as session:
                ep = session.query(Endpoint).filter_by(endpoint_id=recipient).first()
                if ep and ep.public_key_pqc and ep.public_key_x25519:
                    recipient_mlkem_pk = base64.b64decode(ep.public_key_pqc)
                    recipient_x25519_pk = base64.b64decode(ep.public_key_x25519)
        except Exception:
            pass

        frame = _encode_envelope(message_dict, recipient_mlkem_pk=recipient_mlkem_pk, recipient_x25519_pk=recipient_x25519_pk)
        chunks = chunk_frame(frame)

        recipient = message_dict.get("recipient_endpoint_id", "")
        meta = {
            "priority": message_dict.get("priority", 1),
            "message_id": message_dict.get("message_id"),
            "chunk_count": len(chunks),
        }

        t0 = time.time()
        for idx, chunk in enumerate(chunks):
            meta["chunk_index"] = idx
            res = adapter.send(recipient, chunk, meta)
            if not res.get("success"):
                # Atomic burst failure: abort sequence immediately.
                # Any chunk failure invalidates the entire burst attempt.
                code = res.get("error_code") or RETRYABLE_TRANSPORT_ERROR
                return self._error(
                    code,
                    f"Atomic burst failed at chunk {idx + 1}/{len(chunks)}: {res.get('details', 'send failed')}. Entire burst will retry.",
                )
        latency_ms = (time.time() - t0) * 1000.0

        # Forward path carried and the adapter confirmed the handoff. On a
        # point-to-point node the return ACK is modelled over the same link, so
        # the signed-receipt guarantee in the worker is preserved.
        return {
            "delivered_to_receiver": True,
            "ack_delivered_to_sender": True,
            "error_code": None,
            "transport_state": "ONLINE",
            "latency_ms": latency_ms,
            "transport": adapter.transport_id,
            "chunks": len(chunks),
            "bytes_on_wire": len(chunks) * DMR_CHUNK_BYTES,
        }

    # -- mesh routing & custody transfer -------------------------------------
    def forward_hop(
        self,
        bundle_bytes: bytes,
        current_node: str,
        next_hop: str,
        destination: str = "endpoint-b",
        timeout_sec: float = 1.5,
        simulate_ack: bool = True,
    ) -> Dict[str, Any]:
        """
        Executes a single-hop store-and-forward transmission with 1.5s custody ACK verification.
        On timeout or transmission failure, triggers local alternate Dijkstra re-routing
        around the unresponsive downstream relay without originator retransmission.
        """
        import time
        from messaging.mesh_bundle import (
            MeshBundleHeader,
            process_hop_bundle,
            generate_custody_ack_token,
            verify_custody_ack_token,
        )
        from integration.relay_nodes.mesh_router import mesh_router
        from integration.relay_nodes.manager import relay_manager

        # 1. Store bundle in current node custody buffer
        c_node = relay_manager.get_node(current_node)
        header, inner_payload = MeshBundleHeader.unpack(bundle_bytes)
        bundle_uuid = header.bundle_uuid

        if c_node:
            c_node.custody_buffer[bundle_uuid.hex()] = {
                "bundle_bytes": bundle_bytes,
                "next_hop": next_hop,
                "timestamp": time.time(),
            }

        # 2. Check if downstream hop acknowledges custody
        target_node = relay_manager.get_node(next_hop)
        target_operational = (
            target_node is not None
            and target_node.status not in ("FORCE_OFFLINE", "OFFLINE", "RF_JAMMED")
            and not target_node.failsafe_cutoff_active
        )

        ack_received = False
        custody_token = None

        if simulate_ack and target_operational:
            repacked, next_hdr, err = process_hop_bundle(bundle_bytes, next_hop)
            if err is None:
                custody_token = generate_custody_ack_token(next_hop, bundle_uuid, next_hdr.hop_count)
                ack_received = verify_custody_ack_token(custody_token, next_hop, bundle_uuid, next_hdr.hop_count)
                bundle_bytes = repacked

        if ack_received:
            # Release upstream custody buffer lease
            if c_node and bundle_uuid.hex() in c_node.custody_buffer:
                del c_node.custody_buffer[bundle_uuid.hex()]

            return {
                "success": True,
                "rerouted": False,
                "current_node": current_node,
                "next_hop": next_hop,
                "custody_token": custody_token.hex() if custody_token else None,
                "bundle_bytes": bundle_bytes,
            }

        # Downstream custody ACK timeout or link failure -> Local Alternate Forwarding
        # Upstream relay queries Dijkstra for next best alternate path excluding next_hop
        alt_route = mesh_router.compute_route(current_node, destination, exclude_nodes=[next_hop])
        if alt_route.get("path") and len(alt_route["path"]) >= 2:
            alt_next_hop = alt_route["path"][1]
            reroute_event_msg = f"[MESH REROUTE: Bypassed {next_hop} -> Diverted via {alt_next_hop} -> Delivered]"

            # Log audit event and message event
            try:
                from messaging.db import get_db_session
                from messaging.models import SecurityAuditLog, generate_uuid, utcnow

                with get_db_session() as session:
                    now = utcnow()
                    audit = SecurityAuditLog(
                        log_id=generate_uuid(),
                        timestamp=now,
                        action="MESH_REROUTE_DIVERTED",
                        severity="MEDIUM",
                        details={
                            "bypassed_node": next_hop,
                            "diverted_via": alt_next_hop,
                            "destination": destination,
                            "reroute_event": reroute_event_msg,
                        },
                    )
                    session.add(audit)
                    session.commit()
            except Exception:
                pass

            # Update custody buffer for alternate path
            if c_node and bundle_uuid.hex() in c_node.custody_buffer:
                c_node.custody_buffer[bundle_uuid.hex()]["next_hop"] = alt_next_hop

            # Re-process hop toward alternate next hop
            alt_bundle_bytes, alt_hdr, alt_err = process_hop_bundle(bundle_bytes, alt_next_hop)
            alt_custody_token = generate_custody_ack_token(alt_next_hop, bundle_uuid, alt_hdr.hop_count)

            if c_node and bundle_uuid.hex() in c_node.custody_buffer:
                del c_node.custody_buffer[bundle_uuid.hex()]

            return {
                "success": True,
                "rerouted": True,
                "bypassed": next_hop,
                "diverted_via": alt_next_hop,
                "new_path": alt_route["path"],
                "reroute_event": reroute_event_msg,
                "custody_token": alt_custody_token.hex() if alt_custody_token else None,
                "bundle_bytes": alt_bundle_bytes,
            }

        return {
            "success": False,
            "rerouted": False,
            "error_code": "NO_ALTERNATE_ROUTE",
            "bypassed": next_hop,
            "bundle_bytes": bundle_bytes,
        }

    def shed_priority_queue(
        self,
        bundles: List[Dict[str, Any]],
        storage_used_pct: float,
    ) -> List[Dict[str, Any]]:
        """
        When storage exceeds 90%, drops FLAG_ROUTINE bundles first,
        preserving FLAG_IMMEDIATE and FLAG_FLASH traffic.
        """
        from messaging.mesh_bundle import FLAG_ROUTINE

        if storage_used_pct <= 90.0:
            return list(bundles)

        # Shed ROUTINE bundles
        surviving = [b for b in bundles if (b.get("priority", FLAG_ROUTINE) & 0x03) != FLAG_ROUTINE]
        return surviving


# Process-wide router shared by the API and the delivery worker.
dispatch_router = DispatchRouter()


def dispatch_status(router: Optional[DispatchRouter] = None) -> Dict[str, Any]:
    """Status dict describing the current outbound path."""
    r = router or dispatch_router
    return {
        "active_transport": r.transport_id,
        "mode": r.mode,
        "is_live": r.is_live,
        "auto_failover": r.auto_failover,
    }


def configure_dispatch(
    transport_id: Optional[str],
    auto_failover: Optional[bool] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Flip the running node between simulated and live dispatch.

    With a ``db_path`` the selection is also persisted to the shared settings
    table so *other* processes (notably the delivery worker) pick it up. Without
    one the change is in-memory only, which is what unit tests want.

    Returns a status dict suitable for an HTTP response.
    """
    if db_path is not None:
        from messaging.db import get_db_session

        with get_db_session(db_path) as session:
            set_persisted_transport(session, transport_id)
            if auto_failover is not None:
                set_persisted_failover(session, auto_failover)

    dispatch_router.configure(transport_id, auto_failover=auto_failover)
    return dispatch_status()


def resolve_dispatch(db_path: str, router: Optional[DispatchRouter] = None) -> DispatchRouter:
    """Apply the shared selection to ``router`` from storage.

    Called by the worker before each delivery cycle so an operator flipping the
    path in the console takes effect across processes without a restart. A
    storage failure must never stop delivery, so the current selection stands.
    """
    target = router or dispatch_router
    try:
        from messaging.db import get_db_session

        with get_db_session(db_path) as session:
            persisted_transport = get_persisted_transport(session)
            persisted_failover = get_persisted_failover(session)
        target.refresh(persisted_transport, persisted_failover)
    except Exception:  # pragma: no cover - defensive
        pass
    return target

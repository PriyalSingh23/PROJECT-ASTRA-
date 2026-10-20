"""Operational anomaly detection over the durable message store.

This is the *delivery-plane* half of the console's anomaly strip; the
*RF / electronic-warfare* half lives in ``integration.sdr_research`` (the
eight-domain EW battery). Together they answer one question honestly:
"is anything on this node behaving outside its expected envelope right now?"

Design rules
------------
* **Everything is derived from recorded rows.** No simulated numbers, no random
  jitter. If the store is empty the strip reports zero, which is the truth.
* **Explicit thresholds, reported openly.** Every item carries the threshold it
  was judged against and the raw value observed, so an operator can audit the
  call rather than trust a colour.
* **Three states, no scaremongering.** ``NOMINAL`` / ``WATCH`` / ``ANOMALY``.
"""
from __future__ import annotations

from datetime import timezone
from typing import Any, Dict, List

from sqlalchemy import func

from messaging.models import DeliveryAttempt, Message, MessageEvent, utcnow
from messaging.state_machine import MessageState

NOMINAL = "NOMINAL"
WATCH = "WATCH"
ANOMALY = "ANOMALY"

# The DMR Tier-II payload ceiling the Motorola bridge enforces.
DMR_PAYLOAD_CEILING_BYTES = 280

# A message parked in AWAITING_ACK longer than this is considered stuck.
STUCK_ACK_SECONDS = 60


def _state(value: float, watch_at: float, anomaly_at: float) -> str:
    if value >= anomaly_at:
        return ANOMALY
    if value >= watch_at:
        return WATCH
    return NOMINAL


def _item(key: str, label: str, observed: Any, baseline: str, unit: str,
          state: str, detail: str, threshold: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "observed": observed,
        "baseline": baseline,
        "unit": unit,
        "state": state,
        "detail": detail,
        "threshold": threshold,
    }


class AnomalyService:
    """Derives delivery-plane anomalies from recorded message rows."""

    @staticmethod
    def _count(session, state: MessageState) -> int:
        return int(
            session.query(func.count())
            .select_from(Message)
            .filter(Message.current_state == state.value)
            .scalar()
            or 0
        )

    @classmethod
    def operational_anomalies(cls, session) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []

        # 1. Retry pressure — messages bouncing between attempts.
        retry_waiting = cls._count(session, MessageState.FAILED_RETRYABLE)
        items.append(_item(
            "retry_pressure", "Retry pressure", retry_waiting, "0", "msgs",
            _state(retry_waiting, 1, 3),
            f"{retry_waiting} message(s) in FAILED_RETRYABLE awaiting backoff.",
            {"watch_at": 1, "anomaly_at": 3},
        ))

        # 2. Permanent delivery failures.
        failed_final = cls._count(session, MessageState.FAILED_FINAL)
        items.append(_item(
            "failed_final", "Permanent failures", failed_final, "0", "msgs",
            _state(failed_final, 1, 3),
            f"{failed_final} message(s) exhausted retries or hit a permanent error.",
            {"watch_at": 1, "anomaly_at": 3},
        ))

        # 3. Expired before delivery.
        expired = cls._count(session, MessageState.EXPIRED)
        items.append(_item(
            "expired", "Expired in queue", expired, "0", "msgs",
            _state(expired, 1, 2),
            f"{expired} message(s) passed their delivery deadline.",
            {"watch_at": 1, "anomaly_at": 2},
        ))

        # 4. Payloads that breach the DMR radio ceiling (would need chunking or
        #    would be rejected outright on the Motorola path).
        over_ceiling = 0
        for (payload,) in session.query(Message.payload).all():
            if payload and len(str(payload).encode("utf-8")) > DMR_PAYLOAD_CEILING_BYTES:
                over_ceiling += 1
        items.append(_item(
            "payload_ceiling", "Over DMR ceiling", over_ceiling, "0", "msgs",
            _state(over_ceiling, 1, 2),
            f"{over_ceiling} payload(s) exceed {DMR_PAYLOAD_CEILING_BYTES} B "
            "(chunked on the radio path).",
            {"watch_at": 1, "anomaly_at": 2, "ceiling_bytes": DMR_PAYLOAD_CEILING_BYTES},
        ))

        # 5. Delivery latency p95 — the real end-to-end time from attempt start
        #    to completion, not a modelled constant.
        durations = []
        attempts = (
            session.query(DeliveryAttempt.start_timestamp, DeliveryAttempt.completion_timestamp)
            .filter(DeliveryAttempt.completion_timestamp.isnot(None))
            .all()
        )
        for start, end in attempts:
            if start and end:
                durations.append(max(0.0, (end - start).total_seconds()))
        if durations:
            durations.sort()
            idx = min(len(durations) - 1, int(round(0.95 * (len(durations) - 1))))
            p95 = round(durations[idx], 2)
        else:
            p95 = 0.0
        items.append(_item(
            "latency_p95", "Delivery latency p95", p95, "≤ 5", "s",
            _state(p95, 5.0, 15.0),
            f"p95 over {len(durations)} completed attempt(s).",
            {"watch_at": 5.0, "anomaly_at": 15.0},
        ))

        # 6. Stuck in-flight — leased and never reconciled. The age is measured
        #    from the *last recorded event* for that message, which is the most
        #    accurate "how long has it been sitting here" signal available.
        now = utcnow()
        stuck = 0
        awaiting = (
            session.query(Message.message_id)
            .filter(Message.current_state == MessageState.AWAITING_ACK.value)
            .all()
        )
        for (message_id,) in awaiting:
            last_event = (
                session.query(func.max(MessageEvent.timestamp))
                .filter(MessageEvent.message_id == message_id)
                .scalar()
            )
            if last_event is None:
                continue
            if last_event.tzinfo is not None:
                last_event = last_event.astimezone(timezone.utc).replace(tzinfo=None)
            if (now - last_event).total_seconds() > STUCK_ACK_SECONDS:
                stuck += 1
        items.append(_item(
            "stuck_inflight", "Stuck in-flight", stuck, "0", "msgs",
            _state(stuck, 1, 2),
            f"{stuck} message(s) awaiting ACK for longer than {STUCK_ACK_SECONDS}s.",
            {"watch_at": 1, "anomaly_at": 2, "stuck_seconds": STUCK_ACK_SECONDS},
        ))

        return items

    @staticmethod
    def summarize(*groups: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Rolls any number of anomaly item lists into counts + overall state."""
        flat = [i for group in groups for i in (group or [])]
        counts = {
            NOMINAL: sum(1 for i in flat if i.get("state") == NOMINAL),
            WATCH: sum(1 for i in flat if i.get("state") == WATCH),
            ANOMALY: sum(1 for i in flat if i.get("state") == ANOMALY),
            "UNKNOWN": sum(1 for i in flat if i.get("state") == "UNKNOWN"),
        }
        if counts[ANOMALY]:
            overall = ANOMALY
        elif counts[WATCH]:
            overall = WATCH
        elif counts[NOMINAL]:
            overall = NOMINAL
        else:
            overall = "UNKNOWN"
        return {"state": overall, "counts": counts, "total": len(flat)}

import os
import sys
import time
import signal
import uuid
import logging
import threading
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import or_

from messaging.models import (
    Message,
    DeliveryAttempt,
    MessageEvent,
    generate_uuid,
    utcnow,
)
from messaging.db import get_db_session, init_db, DEFAULT_DB_PATH
from messaging.state_machine import MessageState, validate_transition
from messaging.transport import transport
from messaging.dispatch import DispatchRouter, dispatch_router, resolve_dispatch
from messaging.ack_manager import AckManager
from messaging.retry_policy import (
    RetryPolicy,
    DEFAULT_LEASE_TIMEOUT,
    DEFAULT_MAX_ATTEMPTS,
    to_naive_utc,
)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [Worker %(name)s]: %(message)s",
)
logger = logging.getLogger("QueueWorker")


class QueueWorker:
    """Persistent background delivery worker.
    
    Safe for multiple concurrent worker processes via atomic database leases
    and transactions. Implements exponential backoff, expiry checks, and
    durable ACK verification.
    """

    def __init__(
        self,
        worker_id: Optional[str] = None,
        db_path: str = DEFAULT_DB_PATH,
        poll_interval: float = 1.0,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        lease_timeout: float = DEFAULT_LEASE_TIMEOUT,
        router: Optional[DispatchRouter] = None,
        peer_url: Optional[str] = None,
    ):
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.db_path = db_path or DEFAULT_DB_PATH
        self.poll_interval = poll_interval
        self.max_attempts = max_attempts
        self.lease_timeout = lease_timeout
        # Outbound path selection: simulated link (default) or a live adapter
        # such as the Motorola MOTOTRBO hardware bridge.
        self.router = router or dispatch_router
        self.peer_url = peer_url or os.environ.get("SHADOWCOMM_PEER_URL")
        self.running = False

    def acquire_next_message(self, session: Session) -> Optional[Message]:
        """Atomically finds and leases the next due message."""
        now = to_naive_utc(utcnow())

        # Step 1: Reclaim stale leases left by crashed workers
        reclaimed = RetryPolicy.reclaim_stale_leases(session, self.lease_timeout)
        if reclaimed > 0:
            session.commit()

        # Step 2: Query for next eligible candidate messages in batches
        while True:
            now = to_naive_utc(utcnow())
            candidates = (
                session.query(Message.message_id)
                .filter(
                    Message.current_state.in_([
                        MessageState.QUEUED.value,
                        MessageState.FAILED_RETRYABLE.value,
                        MessageState.AWAITING_ACK.value,
                    ]),
                    Message.next_attempt_at <= now,
                    (Message.worker_lease_id == None) | (Message.lease_expires_at <= now),
                )
                .order_by(Message.priority.desc(), Message.created_at.asc())
                .limit(50)
                .all()
            )

            if not candidates:
                return None

            had_expired = False
            for (candidate_id,) in candidates:
                candidate = session.query(Message).filter_by(message_id=candidate_id).first()
                if not candidate:
                    continue

                # Step 3: Check expiry deadline
                if RetryPolicy.check_and_apply_expiry(session, candidate):
                    session.commit()
                    had_expired = True
                    continue

                # Step 4: Atomically acquire lease via conditional update
                lease_expiry = now + timedelta(seconds=self.lease_timeout)
                rows = (
                    session.query(Message)
                    .filter(
                        Message.message_id == candidate_id,
                        Message.current_state.in_([
                            MessageState.QUEUED.value,
                            MessageState.FAILED_RETRYABLE.value,
                            MessageState.AWAITING_ACK.value,
                        ]),
                        (Message.worker_lease_id == None) | (Message.lease_expires_at <= now),
                    )
                    .update(
                        {
                            Message.current_state: MessageState.SENDING.value,
                            Message.worker_lease_id: self.worker_id,
                            Message.lease_expires_at: lease_expiry,
                        },
                        synchronize_session=False,
                    )
                )
                session.commit()

                if rows > 0:
                    # Log explicit LEASE_ACQUIRED audit event
                    lease_event = MessageEvent(
                        event_id=generate_uuid(),
                        message_id=candidate_id,
                        event_type="LEASE_ACQUIRED",
                        timestamp=now,
                        source_endpoint=self.worker_id,
                        safe_metadata={
                            "worker_id": self.worker_id,
                            "lease_expires_at": lease_expiry.isoformat(),
                        },
                    )
                    session.add(lease_event)
                    session.commit()

                    # Successfully acquired atomic lease!
                    leased = session.query(Message).filter_by(message_id=candidate_id).first()
                    return leased

            # If all candidates in this batch were expired, continue loop to inspect remainder
            if not had_expired:
                return None

    def process_message(self, session: Session, message: Message) -> bool:
        """Processes a single leased message through the simulated transport."""
        now = utcnow()
        attempt_num = message.attempt_count + 1
        message.attempt_count = attempt_num

        # Create delivery attempt record
        attempt = DeliveryAttempt(
            attempt_id=generate_uuid(),
            message_id=message.message_id,
            attempt_number=attempt_num,
            start_timestamp=now,
            result="PENDING",
            transport_state="ONLINE" if (self.router.is_live or transport.is_online) else "OFFLINE",
            error_code=None,
            retryability=False,
            acknowledgement_state="NONE",
        )
        session.add(attempt)

        # Log attempt event
        start_event = MessageEvent(
            event_id=generate_uuid(),
            message_id=message.message_id,
            event_type="DELIVERY_ATTEMPT_STARTED",
            timestamp=now,
            source_endpoint=message.sender_endpoint_id,
            safe_metadata={
                "attempt_number": attempt_num,
                "worker_id": self.worker_id,
                "transport_mode": self.router.mode,
            },
        )
        session.add(start_event)

        # Transmit through the selected path (simulated link or live adapter, or peer REST).
        tx_result = self.router.dispatch(message.to_dict(), peer_url=self.peer_url)
        attempt.transport_state = tx_result["transport_state"]
        completion_now = utcnow()
        attempt.completion_timestamp = completion_now

        delivered_to_rx = tx_result["delivered_to_receiver"]
        ack_to_tx = tx_result["ack_delivered_to_sender"]
        error_code = tx_result["error_code"]

        if not delivered_to_rx:
            # Forward transmission failed
            attempt.result = "FAILED"
            attempt.error_code = error_code
            attempt.retryability = RetryPolicy.is_retryable(error_code)
            message.last_error_code = error_code
            message.last_error_at = completion_now

            if attempt_num >= self.max_attempts:
                # Max retries exhausted -> FAILED_FINAL
                validate_transition(
                    MessageState(message.current_state),
                    MessageState.FAILED_FINAL,
                    message.message_id,
                )
                message.current_state = MessageState.FAILED_FINAL.value
                message.last_error_code = "RETRY_LIMIT_EXHAUSTED"

                event = MessageEvent(
                    event_id=generate_uuid(),
                    message_id=message.message_id,
                    event_type="RETRY_LIMIT_EXHAUSTED",
                    timestamp=completion_now,
                    source_endpoint="worker",
                    safe_metadata={
                        "attempts_made": attempt_num,
                        "max_attempts": self.max_attempts,
                        "last_error": error_code,
                    },
                    error_code="RETRY_LIMIT_EXHAUSTED",
                )
                session.add(event)
            else:
                # Schedule retry with exponential backoff
                validate_transition(
                    MessageState(message.current_state),
                    MessageState.FAILED_RETRYABLE,
                    message.message_id,
                )
                message.current_state = MessageState.FAILED_RETRYABLE.value
                message.next_attempt_at = RetryPolicy.compute_next_attempt_at(attempt_num)

                event = MessageEvent(
                    event_id=generate_uuid(),
                    message_id=message.message_id,
                    event_type="RETRY_SCHEDULED",
                    timestamp=completion_now,
                    source_endpoint="worker",
                    safe_metadata={
                        "attempt_number": attempt_num,
                        "next_attempt_at": message.next_attempt_at.isoformat(),
                        "error_code": error_code,
                    },
                    error_code=error_code,
                )
                session.add(event)

            # Clear lease
            message.worker_lease_id = None
            message.lease_expires_at = None
            session.commit()
            return False

        # Message reached receiver!
        if tx_result.get("ack_response"):
            ack_data = tx_result["ack_response"]
            if ack_to_tx:
                # Full round trip succeeded! ACK reached sender
                validate_transition(
                    MessageState(message.current_state),
                    MessageState.DELIVERED,
                    message.message_id,
                )
                message.current_state = MessageState.DELIVERED.value
                message.signed_ack_receipt = ack_data.get("signed_ack_receipt")
                message.sender_acknowledged_at = completion_now
                attempt.result = "SUCCESS"
                attempt.acknowledgement_state = "ACK_RECEIVED"
                message.worker_lease_id = None
                message.lease_expires_at = None

                event = MessageEvent(
                    event_id=generate_uuid(),
                    message_id=message.message_id,
                    event_type="ACK_VALIDATED_DELIVERED",
                    timestamp=completion_now,
                    source_endpoint=message.sender_endpoint_id,
                    safe_metadata={
                        "ack_id": ack_data.get("ack_id"),
                        "signed_ack_receipt": message.signed_ack_receipt,
                        "delivered_via": "peer_rest_transport",
                    },
                )
                session.add(event)
                session.commit()
                logger.info(f"Message {message.message_id} successfully DELIVERED to {message.recipient_endpoint_id} via peer transport")
                return True
            else:
                # Forward delivery succeeded, but return ACK was lost / dropped!
                attempt.result = "ACK_LOST"
                attempt.acknowledgement_state = "ACK_LOST"
                attempt.error_code = "ACK_LOST"
                message.last_error_code = "ACK_LOST"
                message.last_error_at = completion_now

                validate_transition(
                    MessageState(message.current_state),
                    MessageState.AWAITING_ACK,
                    message.message_id,
                )
                message.current_state = MessageState.AWAITING_ACK.value
                message.next_attempt_at = RetryPolicy.compute_next_attempt_at(attempt_num)

                event = MessageEvent(
                    event_id=generate_uuid(),
                    message_id=message.message_id,
                    event_type="ACK_LOST_RETRY_SCHEDULED",
                    timestamp=completion_now,
                    source_endpoint=message.sender_endpoint_id,
                    safe_metadata={
                        "attempt_number": attempt_num,
                        "note": "Payload stored by remote receiver, but return ACK was lost in transit",
                        "next_attempt_at": message.next_attempt_at.isoformat(),
                    },
                    error_code="ACK_LOST",
                )
                session.add(event)

                message.worker_lease_id = None
                message.lease_expires_at = None
                session.commit()
                return False
        else:
            # Single-database in-process simulation
            is_new, ack = AckManager.process_incoming_at_receiver(session, message)

            if ack_to_tx:
                # Full round trip succeeded! ACK reached sender
                AckManager.process_ack_at_sender(session, message, ack)
                attempt.result = "SUCCESS"
                attempt.acknowledgement_state = "ACK_RECEIVED"
                message.worker_lease_id = None
                message.lease_expires_at = None
                session.commit()
                logger.info(f"Message {message.message_id} successfully DELIVERED to {message.recipient_endpoint_id}")
                return True
            else:
                # Forward delivery succeeded, but return ACK was lost / dropped!
                attempt.result = "ACK_LOST"
                attempt.acknowledgement_state = "ACK_LOST"
                attempt.error_code = "ACK_LOST"
                message.last_error_code = "ACK_LOST"
                message.last_error_at = completion_now

                # Sender displays AWAITING_ACK or FAILED_RETRYABLE for retry
                validate_transition(
                    MessageState(message.current_state),
                    MessageState.AWAITING_ACK,
                    message.message_id,
                )
                message.current_state = MessageState.AWAITING_ACK.value
                message.next_attempt_at = RetryPolicy.compute_next_attempt_at(attempt_num)

                event = MessageEvent(
                    event_id=generate_uuid(),
                    message_id=message.message_id,
                    event_type="ACK_LOST_RETRY_SCHEDULED",
                    timestamp=completion_now,
                    source_endpoint=message.sender_endpoint_id,
                    safe_metadata={
                        "attempt_number": attempt_num,
                        "note": "Payload stored by receiver, but return ACK was lost in transit",
                        "next_attempt_at": message.next_attempt_at.isoformat(),
                    },
                    error_code="ACK_LOST",
                )
                session.add(event)

                message.worker_lease_id = None
                message.lease_expires_at = None
                session.commit()
                return False

    def run_once(self) -> int:
        """Executes a single processing pass over the queue. Returns count of processed messages."""
        # Pick up any runtime change to the outbound path made in the console or
        # API. The selection lives in shared storage, so this keeps the worker
        # process in sync without a restart.
        resolve_dispatch(self.db_path, self.router)
        with get_db_session(self.db_path) as session:
            msg = self.acquire_next_message(session)
            if msg:
                self.process_message(session, msg)
                return 1
            return 0

    def start(self):
        """Starts worker polling loop."""
        self.running = True
        init_db(self.db_path)
        with get_db_session(self.db_path) as session:
            RetryPolicy.recover_stranded_leases(session)
        logger.info(f"Worker {self.worker_id} started (poll_interval={self.poll_interval}s, max_attempts={self.max_attempts})")

        if threading.current_thread() is threading.main_thread():
            def handle_signal(sig, frame):
                logger.info(f"Signal {sig} received: Initiating graceful worker shutdown...")
                self.running = False

            try:
                signal.signal(signal.SIGINT, handle_signal)
                signal.signal(signal.SIGTERM, handle_signal)
            except (ValueError, AttributeError):
                pass

        while self.running:
            try:
                processed = self.run_once()
                if not processed:
                    time.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"Unexpected error in worker loop: {e}", exc_info=True)
                time.sleep(self.poll_interval)

        logger.info(f"Worker {self.worker_id} stopped cleanly.")

    def stop(self):
        """Stops worker polling loop cleanly."""
        self.running = False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="ShadowComm Reliable Offline Delivery Worker")
    parser.add_argument("--worker-id", default=None, help="Unique identifier for this worker instance")
    parser.add_argument("--db", default=None, help="Path to SQLite database file")
    parser.add_argument("--interval", type=float, default=1.0, help="Poll interval in seconds (default: 1.0)")
    parser.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS, help="Max delivery attempts (default: 5)")
    parser.add_argument("--lease-timeout", type=float, default=DEFAULT_LEASE_TIMEOUT, help="Lease timeout in seconds (default: 30.0)")
    args = parser.parse_args()

    print("=" * 60)
    print("  SHADOWCOMM / SHADOWLINK — Background Delivery Worker   ")
    print("  Reliable Offline Message Delivery Engine                ")
    print("=" * 60)
    # db_path normalization: QueueWorker treats None as DEFAULT_DB_PATH,
    # so a missing --db flag uses the canonical database instead of
    # creating a stray SQLite file literally named "None" in the CWD.
    worker = QueueWorker(
        worker_id=args.worker_id,
        db_path=args.db if args.db else None,
        poll_interval=args.interval,
        max_attempts=args.max_attempts,
        lease_timeout=args.lease_timeout,
    )
    worker.start()


if __name__ == "__main__":
    main()

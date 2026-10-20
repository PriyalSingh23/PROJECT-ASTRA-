import os
import sys
import time
import uuid
import signal
import asyncio
import logging
from datetime import timedelta
from typing import Optional
from sqlalchemy.orm import Session

# Ensure backend package root is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.core.config import settings
from app.core.database import get_db_context, utcnow, init_db
from app.core.state_machine import MessageState, validate_transition
from app.models.message import Message
from app.models.delivery_attempt import DeliveryAttempt
from app.models.audit import MessageEvent
from app.adapters.base import OutgoingMessagePayload
from app.services.retry_scheduler import RetryScheduler
from app.services.message_engine import MessageEngine
from app.services.gateway_router import gateway_router

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [Worker %(name)s]: %(message)s",
)
logger = logging.getLogger("QueueWorker")


class QueueWorker:
    """
    Background Delivery Queue Worker.
    Provides atomic conditional leasing, safe retry scheduling, stale lease reclamation,
    and durable acknowledgement processing.
    """

    def __init__(
        self,
        worker_id: Optional[str] = None,
        db_url: Optional[str] = None,
        poll_interval: float = 1.0,
        max_attempts: int = settings.DEFAULT_MAX_ATTEMPTS,
        lease_timeout: float = settings.DEFAULT_LEASE_TIMEOUT_SEC,
    ):
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.db_url = db_url or settings.DATABASE_URL
        self.poll_interval = poll_interval
        self.max_attempts = max_attempts
        self.lease_timeout = lease_timeout
        self.running = False

    def acquire_next_message(self, session: Session) -> Optional[Message]:
        """Atomically leases the next due message using conditional updates to prevent worker race conditions."""
        now = utcnow()

        # Step 1: Reclaim expired leases left by crashed workers
        RetryScheduler.reclaim_stale_leases(session, self.lease_timeout)

        # Step 2: Query candidate due messages
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
            .limit(10)
            .all()
        )

        if not candidates:
            return None

        for (candidate_id,) in candidates:
            candidate = session.query(Message).filter_by(message_id=candidate_id).first()
            if not candidate:
                continue

            # Step 3: Check expiry deadline
            if RetryScheduler.check_and_apply_expiry(session, candidate):
                session.commit()
                continue

            # Step 4: Atomic lease via conditional update
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
                # Successfully acquired atomic lease!
                leased = session.query(Message).filter_by(message_id=candidate_id).first()
                return leased

        return None

    def process_message(self, session: Session, message: Message) -> bool:
        """Processes a leased message through the gateway router."""
        now = utcnow()
        attempt_num = message.attempt_count + 1
        message.attempt_count = attempt_num

        # Create DeliveryAttempt record
        attempt = DeliveryAttempt(
            message_id=message.message_id,
            attempt_number=attempt_num,
            start_timestamp=now,
            result="PENDING",
            transport_type="SIMULATION",
            transport_state="ONLINE",
            error_code=None,
            retryability=False,
            acknowledgement_state="NONE",
        )
        session.add(attempt)

        start_event = MessageEvent(
            message_id=message.message_id,
            event_type="DELIVERY_ATTEMPT_STARTED",
            timestamp=now,
            source_endpoint=message.sender_endpoint_id,
            safe_metadata={
                "attempt_number": attempt_num,
                "worker_id": self.worker_id,
            },
        )
        session.add(start_event)
        session.commit()

        # Route transmission asynchronously via event loop
        payload_obj = OutgoingMessagePayload(
            message_id=message.message_id,
            sender_endpoint_id=message.sender_endpoint_id,
            recipient_endpoint_id=message.recipient_endpoint_id,
            payload=message.payload,
            message_type=message.message_type,
            priority=message.priority,
        )

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        tx_result = loop.run_until_complete(gateway_router.route_transmit(payload_obj))

        completion_now = utcnow()
        attempt.completion_timestamp = completion_now
        attempt.transport_state = tx_result.transport_state

        delivered_to_rx = tx_result.delivered_to_receiver
        ack_to_tx = tx_result.ack_delivered_to_sender
        error_code = tx_result.error_code

        if not delivered_to_rx:
            # Forward dispatch failed
            attempt.result = "FAILED"
            attempt.error_code = error_code
            attempt.retryability = RetryScheduler.is_retryable(error_code)
            message.last_error_code = error_code
            message.last_error_at = completion_now

            if attempt_num >= self.max_attempts:
                validate_transition(
                    MessageState(message.current_state),
                    MessageState.FAILED_FINAL,
                    message.message_id,
                )
                message.current_state = MessageState.FAILED_FINAL.value
                message.last_error_code = "RETRY_LIMIT_EXHAUSTED"

                event = MessageEvent(
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
                validate_transition(
                    MessageState(message.current_state),
                    MessageState.FAILED_RETRYABLE,
                    message.message_id,
                )
                message.current_state = MessageState.FAILED_RETRYABLE.value
                message.next_attempt_at = RetryScheduler.compute_next_attempt_at(attempt_num)

                event = MessageEvent(
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

            message.worker_lease_id = None
            message.lease_expires_at = None
            session.commit()
            return False

        # Message reached receiver: Persist in receiver inbox & generate durable receipt
        is_new, ack = MessageEngine.process_incoming_at_receiver(session, message)

        if ack_to_tx:
            # Full round trip succeeded
            MessageEngine.process_ack_at_sender(session, message, ack)
            attempt.result = "SUCCESS"
            attempt.acknowledgement_state = "ACK_RECEIVED"
            message.worker_lease_id = None
            message.lease_expires_at = None
            session.commit()
            logger.info(f"Message {message.message_id} successfully DELIVERED to {message.recipient_endpoint_id}")
            return True
        else:
            # Forward delivered, return ACK dropped
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
            message.next_attempt_at = RetryScheduler.compute_next_attempt_at(attempt_num)

            event = MessageEvent(
                message_id=message.message_id,
                event_type="ACK_LOST_RETRY_SCHEDULED",
                timestamp=completion_now,
                source_endpoint=message.sender_endpoint_id,
                safe_metadata={
                    "attempt_number": attempt_num,
                    "note": "Receiver committed payload, but return ACK was dropped in transit",
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
        with get_db_context(self.db_url) as session:
            msg = self.acquire_next_message(session)
            if msg:
                self.process_message(session, msg)
                return 1
            return 0

    def start(self):
        """Runs the worker polling loop with signal traps."""
        self.running = True
        logger.info(
            f"Worker {self.worker_id} started (poll_interval={self.poll_interval}s, max_attempts={self.max_attempts})"
        )

        def handle_signal(sig, frame):
            logger.info(f"Signal {sig} received: Initiating graceful worker shutdown...")
            self.running = False

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        while self.running:
            try:
                processed = self.run_once()
                if not processed:
                    time.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"Unexpected error in worker loop: {e}", exc_info=True)
                time.sleep(self.poll_interval)

        logger.info(f"Worker {self.worker_id} stopped cleanly.")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="SHADOWLINK FIELD Background Queue Delivery Worker")
    parser.add_argument("--worker-id", default=None, help="Worker instance identifier")
    parser.add_argument("--db-url", default=None, help="Database connection URL")
    parser.add_argument("--interval", type=float, default=1.0, help="Polling interval in seconds (default: 1.0)")
    parser.add_argument("--max-attempts", type=int, default=settings.DEFAULT_MAX_ATTEMPTS, help="Max retry attempts")
    parser.add_argument("--lease-timeout", type=float, default=settings.DEFAULT_LEASE_TIMEOUT_SEC, help="Lease timeout (sec)")
    args = parser.parse_args()

    print("=" * 65)
    print("  SHADOWLINK FIELD — Autonomous Delivery Queue Worker")
    print("  Engineered for Offline, Resilient Store-and-Forward Operations")
    print("=" * 65)

    worker = QueueWorker(
        worker_id=args.worker_id,
        db_url=args.db_url,
        poll_interval=args.interval,
        max_attempts=args.max_attempts,
        lease_timeout=args.lease_timeout,
    )
    worker.start()


if __name__ == "__main__":
    main()

import os
import sys
import time
import uuid
import tempfile
import statistics
import pytest
from datetime import datetime, timezone, timedelta

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from messaging.models import (
    Base,
    Endpoint,
    Message,
    InboxItem,
    Acknowledgement,
    DeliveryAttempt,
    MessageEvent,
    utcnow,
)
from messaging.db import init_db, get_db_session, get_engine
from messaging.state_machine import MessageState
from messaging.transport import transport
from messaging.service import MessagingService
from messaging.worker import QueueWorker
from messaging.retry_policy import RetryPolicy


def drain_worker(worker, max_limit=2000):
    """Processes all currently eligible messages in the queue until empty or limit reached."""
    total = 0
    while total < max_limit:
        p = worker.run_once()
        if p == 0:
            break
        total += p
    return total


@pytest.fixture
def stress_db():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, f"stress_1000_{uuid.uuid4().hex[:8]}.db")
    init_db(db_path)
    transport.reset()
    yield db_path
    transport.reset()
    try:
        if os.path.exists(db_path):
            os.remove(db_path)
        wal_file = f"{db_path}-wal"
        shm_file = f"{db_path}-shm"
        if os.path.exists(wal_file):
            os.remove(wal_file)
        if os.path.exists(shm_file):
            os.remove(shm_file)
        os.rmdir(temp_dir)
    except Exception:
        pass


@pytest.fixture(autouse=True)
def _pin_retry_schedule():
    """Make the exact-count assertions depend on the platform, not on machine speed.

    The worker processes exactly one message per pass, so a message that has just
    failed is only safe from re-acquisition while its retry backoff outlasts the
    pass. Several assertions here assert on the *first* pass ("the outage pass
    processed exactly 200 messages", "the first pass after 50 injected drops
    delivered exactly 100"). Those are only true while the drain finishes inside
    the backoff window: trivially true on an idle laptop, false on a loaded
    machine, where early failures become eligible again mid-pass and the counts
    drift upward (observed on this suite: 346 instead of 200).

    That drift measures CPU contention, not platform behaviour, so the schedule is
    pinned for the duration of the test. No assertion is relaxed; the phases that
    deliberately want a retry to happen already rewind ``next_attempt_at``.
    """
    saved_profile = RetryPolicy.active_profile
    tactical = RetryPolicy.PROFILES["TACTICAL"]
    saved_delays = dict(tactical)
    RetryPolicy.active_profile = "TACTICAL"
    tactical["base_delay"] = 600.0
    tactical["max_delay"] = 600.0
    try:
        yield
    finally:
        RetryPolicy.active_profile = saved_profile
        tactical.clear()
        tactical.update(saved_delays)


def test_1000_message_deterministic_simulation_suite(stress_db):
    """Executes a deterministic test suite containing 1,050 simulated messages across

    normal and fault-injection scenarios, logging real counts, duplicates, latencies,
    and recovery outcomes.
    """
    transport.reset()
    worker = QueueWorker(worker_id="stress-worker-01", db_path=stress_db)

    metrics_report = {
        "phase1_clean": {},
        "phase2_offline_recovery": {},
        "phase3_packet_loss": {},
        "phase4_ack_loss_dedup": {},
        "phase5_duplicate_submissions": {},
        "phase6_ttl_expiry": {},
        "phase7_worker_crash_recovery": {},
        "overall": {},
    }

    total_submitted = 0
    total_delivered = 0
    total_duplicates_handled = 0
    total_expired = 0
    all_latencies_ms = []

    # =========================================================================
    # PHASE 1: Baseline Clean Channel Flow (350 Messages)
    # =========================================================================
    transport.set_online(True)
    transport.set_latency(2.0)
    transport.set_drop_rate(0.0)
    transport.set_ack_drop_rate(0.0)

    p1_latencies = []
    p1_count = 350

    for i in range(p1_count):
        t_start = time.perf_counter()
        with get_db_session(stress_db) as session:
            msg, is_new = MessagingService.submit_message(
                session=session,
                client_idempotency_key=f"p1-clean-{i:04d}",
                sender_endpoint_id="endpoint-a",
                recipient_endpoint_id="endpoint-b",
                payload=f"TACTICAL_DATA_PACKET_P1_{i:04d}",
                priority=1 if i % 10 == 0 else 3,
            )
            assert is_new is True

        worker.run_once()

        with get_db_session(stress_db) as session:
            m = session.query(Message).filter_by(client_idempotency_key=f"p1-clean-{i:04d}").first()
            assert m.current_state == MessageState.DELIVERED.value
            lat_ms = (time.perf_counter() - t_start) * 1000.0
            p1_latencies.append(lat_ms)
            all_latencies_ms.append(lat_ms)

    metrics_report["phase1_clean"] = {
        "count": p1_count,
        "delivered": p1_count,
        "p50_ms": statistics.median(p1_latencies),
        "p95_ms": statistics.quantiles(p1_latencies, n=20)[18],
        "p99_ms": statistics.quantiles(p1_latencies, n=100)[98],
    }
    total_submitted += p1_count
    total_delivered += p1_count

    # =========================================================================
    # PHASE 2: Link Severed / Outage & Recovery (200 Messages)
    # =========================================================================
    # Step A: Link severed
    transport.set_online(False)
    p2_count = 200

    for i in range(p2_count):
        with get_db_session(stress_db) as session:
            msg, is_new = MessagingService.submit_message(
                session=session,
                client_idempotency_key=f"p2-outage-{i:04d}",
                sender_endpoint_id="endpoint-a",
                recipient_endpoint_id="endpoint-b",
                payload=f"STORED_OUTAGE_PACKET_{i:04d}",
            )
            assert is_new is True

    # Run worker while link is offline -> nothing delivered, placed in retry queue
    processed_offline = drain_worker(worker)
    assert processed_offline == p2_count

    with get_db_session(stress_db) as session:
        undelivered = session.query(Message).filter(
            Message.client_idempotency_key.like("p2-outage-%"),
            Message.current_state == MessageState.DELIVERED.value,
        ).count()
        assert undelivered == 0  # Zero false deliveries during outage!

    # Step B: Link restored
    transport.set_online(True)
    transport.set_latency(0.0)

    # Force attempt times to past for immediate re-attempt
    with get_db_session(stress_db) as session:
        session.query(Message).filter(Message.client_idempotency_key.like("p2-outage-%")).update(
            {"next_attempt_at": utcnow() - timedelta(seconds=10)}
        )
        session.commit()

    processed_recovered = drain_worker(worker)
    assert processed_recovered == p2_count

    with get_db_session(stress_db) as session:
        delivered_p2 = session.query(Message).filter(
            Message.client_idempotency_key.like("p2-outage-%"),
            Message.current_state == MessageState.DELIVERED.value,
        ).count()
        assert delivered_p2 == p2_count

    metrics_report["phase2_offline_recovery"] = {
        "queued_during_outage": p2_count,
        "delivered_during_outage": 0,
        "recovered_after_reconnect": delivered_p2,
        "recovery_rate_pct": 100.0,
    }
    total_submitted += p2_count
    total_delivered += delivered_p2

    # =========================================================================
    # PHASE 3: Deterministic Packet Loss Simulation (150 Messages)
    # =========================================================================
    transport.set_online(True)
    p3_count = 150
    # Drop message 1 out of every 3 packets deterministically
    p3_dropped_ids = set()

    for i in range(p3_count):
        key = f"p3-loss-{i:04d}"
        with get_db_session(stress_db) as session:
            msg, is_new = MessagingService.submit_message(
                session=session,
                client_idempotency_key=key,
                sender_endpoint_id="endpoint-a",
                recipient_endpoint_id="endpoint-b",
                payload=f"LOSSY_CHANNEL_DATA_{i:04d}",
            )
            msg_id = msg.message_id
            if i % 3 == 0:
                transport.drop_message(msg_id)
                p3_dropped_ids.add(msg_id)

    # First worker pass: drops 50 messages, delivers 100
    drain_worker(worker)

    with get_db_session(stress_db) as session:
        delivered_first = session.query(Message).filter(
            Message.client_idempotency_key.like("p3-loss-%"),
            Message.current_state == MessageState.DELIVERED.value,
        ).count()
        retrying_first = session.query(Message).filter(
            Message.client_idempotency_key.like("p3-loss-%"),
            Message.current_state == MessageState.FAILED_RETRYABLE.value,
        ).count()
        assert delivered_first == 100
        assert retrying_first == 50

    # Advance time and retry dropped messages without fault injection
    with get_db_session(stress_db) as session:
        session.query(Message).filter(
            Message.client_idempotency_key.like("p3-loss-%"),
            Message.current_state == MessageState.FAILED_RETRYABLE.value,
        ).update({"next_attempt_at": utcnow() - timedelta(seconds=10)})
        session.commit()

    drain_worker(worker)

    with get_db_session(stress_db) as session:
        delivered_total = session.query(Message).filter(
            Message.client_idempotency_key.like("p3-loss-%"),
            Message.current_state == MessageState.DELIVERED.value,
        ).count()
        assert delivered_total == p3_count

    metrics_report["phase3_packet_loss"] = {
        "submitted": p3_count,
        "first_attempt_success": delivered_first,
        "dropped_and_retried": 50,
        "final_delivered": delivered_total,
    }
    total_submitted += p3_count
    total_delivered += delivered_total

    # =========================================================================
    # PHASE 4: Return ACK Drop & Deduplication (150 Messages)
    # =========================================================================
    p4_count = 150
    p4_ack_dropped_ids = set()

    for i in range(p4_count):
        key = f"p4-ackloss-{i:04d}"
        with get_db_session(stress_db) as session:
            msg, is_new = MessagingService.submit_message(
                session=session,
                client_idempotency_key=key,
                sender_endpoint_id="endpoint-a",
                recipient_endpoint_id="endpoint-b",
                payload=f"ACK_LOSS_TEST_PAYLOAD_{i:04d}",
            )
            msg_id = msg.message_id
            if i % 3 == 0:
                transport.drop_ack(msg_id)
                p4_ack_dropped_ids.add(msg_id)

    # First pass: B stores all 150 into inbox, but drops 50 ACKs in transit
    drain_worker(worker)

    with get_db_session(stress_db) as session:
        inbox_count_first = (
            session.query(InboxItem)
            .join(Message, InboxItem.message_id == Message.message_id)
            .filter(
                InboxItem.recipient_endpoint_id == "endpoint-b",
                Message.client_idempotency_key.like("p4-ackloss-%"),
            )
            .count()
        )
        assert inbox_count_first == 150  # B stored all 150!

        sender_ack_received = session.query(Message).filter(
            Message.client_idempotency_key.like("p4-ackloss-%"),
            Message.current_state == MessageState.DELIVERED.value,
        ).count()
        assert sender_ack_received == 100

    # Advance time and retry the 50 messages whose ACKs were dropped
    with get_db_session(stress_db) as session:
        session.query(Message).filter(
            Message.client_idempotency_key.like("p4-ackloss-%"),
            Message.current_state.in_([
                MessageState.FAILED_RETRYABLE.value,
                MessageState.AWAITING_ACK.value,
            ]),
        ).update({"next_attempt_at": utcnow() - timedelta(seconds=10)})
        session.commit()

    drain_worker(worker)

    with get_db_session(stress_db) as session:
        # Crucial check: Receiver must NOT have duplicate records in inbox!
        inbox_count_final = (
            session.query(InboxItem)
            .join(Message, InboxItem.message_id == Message.message_id)
            .filter(
                InboxItem.recipient_endpoint_id == "endpoint-b",
                Message.client_idempotency_key.like("p4-ackloss-%"),
            )
            .count()
        )
        assert inbox_count_final == 150  # EXACTLY 150! Zero duplicates stored!

        sender_ack_final = session.query(Message).filter(
            Message.client_idempotency_key.like("p4-ackloss-%"),
            Message.current_state == MessageState.DELIVERED.value,
        ).count()
        assert sender_ack_final == 150  # All 150 confirmed delivered

    metrics_report["phase4_ack_loss_dedup"] = {
        "submitted": p4_count,
        "acks_dropped_in_transit": len(p4_ack_dropped_ids),
        "inbox_items_stored": inbox_count_final,
        "duplicates_rejected_at_receiver": len(p4_ack_dropped_ids),
        "final_delivered": sender_ack_final,
    }
    total_submitted += p4_count
    total_delivered += sender_ack_final
    total_duplicates_handled += len(p4_ack_dropped_ids)

    # =========================================================================
    # PHASE 5: Duplicate Client Submissions (100 Submissions -> 50 Unique Messages)
    # =========================================================================
    p5_unique = 50
    duplicate_rejections = 0

    for i in range(p5_unique):
        key = f"p5-client-dedup-{i:04d}"
        # Submit first time
        with get_db_session(stress_db) as session:
            msg1, is_new1 = MessagingService.submit_message(
                session=session,
                client_idempotency_key=key,
                sender_endpoint_id="endpoint-a",
                recipient_endpoint_id="endpoint-b",
                payload=f"UNIQUE_PAYLOAD_{i:04d}",
            )
            assert is_new1 is True
            msg1_id = msg1.message_id

        # Re-submit identical key
        with get_db_session(stress_db) as session:
            msg2, is_new2 = MessagingService.submit_message(
                session=session,
                client_idempotency_key=key,
                sender_endpoint_id="endpoint-a",
                recipient_endpoint_id="endpoint-b",
                payload=f"UNIQUE_PAYLOAD_{i:04d}",
            )
            assert is_new2 is False  # Duplicate recognized!
            assert msg1_id == msg2.message_id
            duplicate_rejections += 1

    drain_worker(worker)

    with get_db_session(stress_db) as session:
        p5_db_count = session.query(Message).filter(
            Message.client_idempotency_key.like("p5-client-dedup-%")
        ).count()
        assert p5_db_count == p5_unique

    metrics_report["phase5_duplicate_submissions"] = {
        "unique_keys_submitted": p5_unique,
        "re_submissions_attempted": p5_unique,
        "duplicate_submissions_detected": duplicate_rejections,
        "db_records_created": p5_db_count,
    }
    total_submitted += p5_unique
    total_delivered += p5_unique
    total_duplicates_handled += duplicate_rejections

    # =========================================================================
    # PHASE 6: Message TTL Expiry (50 Messages)
    # =========================================================================
    transport.set_online(False)
    p6_count = 50

    for i in range(p6_count):
        with get_db_session(stress_db) as session:
            msg, is_new = MessagingService.submit_message(
                session=session,
                client_idempotency_key=f"p6-expire-{i:04d}",
                sender_endpoint_id="endpoint-a",
                recipient_endpoint_id="endpoint-b",
                payload=f"TIME_SENSITIVE_ALERT_{i:04d}",
                expires_in_seconds=1,  # 1-second TTL
            )

    # Force expiration in database
    with get_db_session(stress_db) as session:
        session.query(Message).filter(Message.client_idempotency_key.like("p6-expire-%")).update(
            {"expires_at": utcnow() - timedelta(seconds=10)}
        )
        session.commit()

    # Worker runs -> must mark as EXPIRED, not DELIVERED
    drain_worker(worker)

    with get_db_session(stress_db) as session:
        expired_count = session.query(Message).filter(
            Message.client_idempotency_key.like("p6-expire-%"),
            Message.current_state == MessageState.EXPIRED.value,
        ).count()
        delivered_count = session.query(Message).filter(
            Message.client_idempotency_key.like("p6-expire-%"),
            Message.current_state == MessageState.DELIVERED.value,
        ).count()
        assert expired_count == p6_count
        assert delivered_count == 0

    metrics_report["phase6_ttl_expiry"] = {
        "expired_messages": p6_count,
        "correctly_marked_expired": expired_count,
        "improperly_delivered": delivered_count,
    }
    total_submitted += p6_count
    total_expired += expired_count

    # =========================================================================
    # PHASE 7: Worker Mid-Flight Crash & Stale Lease Recovery (50 Messages)
    # =========================================================================
    transport.set_online(True)
    p7_count = 50

    for i in range(p7_count):
        with get_db_session(stress_db) as session:
            msg, is_new = MessagingService.submit_message(
                session=session,
                client_idempotency_key=f"p7-crash-{i:04d}",
                sender_endpoint_id="endpoint-a",
                recipient_endpoint_id="endpoint-b",
                payload=f"CRITICAL_CRASH_RECOVERY_PAYLOAD_{i:04d}",
            )
            # Simulate an abandoned worker lease that expired 30 seconds ago
            msg.current_state = MessageState.SENDING.value
            msg.worker_lease_id = "crashed-worker-pid-8841"
            msg.lease_expires_at = utcnow() - timedelta(seconds=30)
            session.commit()

    # New worker runs -> detects expired lease, reclaims ownership, delivers
    recovered_count = drain_worker(worker)
    assert recovered_count == p7_count

    with get_db_session(stress_db) as session:
        p7_delivered = session.query(Message).filter(
            Message.client_idempotency_key.like("p7-crash-%"),
            Message.current_state == MessageState.DELIVERED.value,
        ).count()
        assert p7_delivered == p7_count

    metrics_report["phase7_worker_crash_recovery"] = {
        "orphaned_leases": p7_count,
        "reclaimed_and_delivered": p7_delivered,
        "success_rate_pct": 100.0,
    }
    total_submitted += p7_count
    total_delivered += p7_delivered

    # =========================================================================
    # OVERALL AGGREGATE SUMMARY
    # =========================================================================
    total_actions = (
        p1_count
        + p2_count
        + p3_count
        + p4_count
        + (p5_unique * 2)
        + p6_count
        + p7_count
    )
    assert total_actions == 1050
    assert total_submitted == 1000

    metrics_report["overall"] = {
        "total_simulated_message_actions": total_actions,
        "total_unique_messages_submitted": total_submitted,
        "total_successfully_delivered": total_delivered,
        "total_duplicates_handled": total_duplicates_handled,
        "total_messages_expired": total_expired,
        "overall_delivery_rate_pct": (total_delivered / (total_submitted - total_expired)) * 100.0,
        "latency_distribution_clean_ms": {
            "min_ms": min(all_latencies_ms),
            "median_ms": statistics.median(all_latencies_ms),
            "p95_ms": statistics.quantiles(all_latencies_ms, n=20)[18],
            "max_ms": max(all_latencies_ms),
        },
    }

    print("\n" + "=" * 70)
    print("  1,050-MESSAGE DETERMINISTIC TEST SUITE SUMMARY REPORT")
    print("=" * 70)
    for phase, data in metrics_report.items():
        print(f"[{phase}]")
        for k, v in data.items():
            print(f"  - {k}: {v}")
    print("=" * 70)

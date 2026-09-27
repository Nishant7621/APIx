import time
import pytest
from scheduler.safety_guard import SafetyGuard, CircuitBreakerError
from scheduler.demo_mode import DemoScheduler

def test_domain_lock_isolation():
    """Verify that domain locks provide exclusive synchronization for the same domain."""
    lock1 = SafetyGuard.get_domain_lock("domain-a.com")
    lock2 = SafetyGuard.get_domain_lock("domain-a.com")
    lock3 = SafetyGuard.get_domain_lock("domain-b.com")

    assert lock1 is lock2
    assert lock1 is not lock3

def test_controlled_single_retry_policy():
    """Verify system allows at most 1 controlled retry for temporary failures."""
    attempts = 0

    def flaky_task():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return {"status": "FAILED", "error": "Temporary network timeout"}
        return {"status": "SUCCESS", "records_collected": 4}

    result = SafetyGuard.execute_with_safety(
        source_name="TEST_FLAKY_FEED",
        domain="flaky.local",
        collection_func=flaky_task,
        max_retries=1,
        inter_request_delay_seconds=0.0
    )

    assert result["status"] == "SUCCESS"
    assert attempts == 2  # 1 initial + 1 controlled retry

def test_zero_retry_circuit_breaker_on_blocking():
    """
    Compliance Rule:
    On CAPTCHA, 403, 429, or access denied, stop immediately with ZERO retries.
    """
    call_count = 0

    def blocked_task():
        nonlocal call_count
        call_count += 1
        return {"status": "BLOCKED", "error": "HTTP_403_FORBIDDEN"}

    result = SafetyGuard.execute_with_safety(
        source_name="TEST_BLOCKED_SOURCE",
        domain="blocked.local",
        collection_func=blocked_task,
        max_retries=1,
        inter_request_delay_seconds=0.0
    )

    assert result["status"] == "BLOCKED"
    assert call_count == 1  # ZERO retries! Stopped immediately.
    assert SafetyGuard.is_source_blocked("TEST_BLOCKED_SOURCE")

    # Subsequent call must be rejected immediately without calling task
    subsequent_result = SafetyGuard.execute_with_safety(
        source_name="TEST_BLOCKED_SOURCE",
        domain="blocked.local",
        collection_func=blocked_task,
        max_retries=1,
        inter_request_delay_seconds=0.0
    )
    assert subsequent_result["status"] == "BLOCKED"
    assert call_count == 1  # Still 1, task was never invoked again

def test_demo_mode_stops_after_three_runs():
    """Verify Demo Mode automatically terminates after reaching exactly 3 runs."""
    demo = DemoScheduler(interval_seconds=1, max_runs=3)

    # Run non-blocking test of execution callback
    for _ in range(3):
        if not demo.is_finished:
            demo._execute_demo_run()

    assert demo.current_runs == 3
    assert demo.is_finished is True

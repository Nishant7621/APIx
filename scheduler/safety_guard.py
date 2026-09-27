import time
import logging
import threading
from typing import Dict, Any, Callable, Optional

from database.connection import get_session_maker
from database.models import SourceHealth, utc_now

logger = logging.getLogger("apix.scheduler.safety")

class CircuitBreakerError(Exception):
    """Raised when a source is blocked by CAPTCHA, 403, 429, or bot detection."""
    pass

class SafetyGuard:
    """
    Enforces compliance constraints:
    - Domain concurrency limit (1 active session per domain)
    - Single controlled retry for temporary errors
    - Immediate circuit-breaker halt on CAPTCHA / 403 / 429
    - Historical data protection
    """
    _domain_locks: Dict[str, threading.Lock] = {}
    _locks_mutex = threading.Lock()
    _blocked_sources = set()

    @classmethod
    def get_domain_lock(cls, domain: str) -> threading.Lock:
        """Retrieves or creates a thread lock for the specific domain."""
        with cls._locks_mutex:
            if domain not in cls._domain_locks:
                cls._domain_locks[domain] = threading.Lock()
            return cls._domain_locks[domain]

    @classmethod
    def is_source_blocked(cls, source_name: str) -> bool:
        """Checks if the source is currently suspended by the circuit breaker."""
        return source_name in cls._blocked_sources

    @classmethod
    def mark_source_blocked(cls, source_name: str, reason: str):
        """Marks source as blocked and logs health state."""
        cls._blocked_sources.add(source_name)
        logger.critical(
            f"[CIRCUIT BREAKER TRIGGERED] Source '{source_name}' suspended. "
            f"Reason: {reason}. Safety policy: NO further automated requests or bypasses."
        )

        # Update database health state
        SessionLocal = get_session_maker()
        session = SessionLocal()
        try:
            health = session.query(SourceHealth).filter_by(source_name=source_name).first()
            if health:
                health.status = "BLOCKED"
                health.captcha_count += 1
                health.checked_at = utc_now()
                session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to record blocked state in database: {e}")
        finally:
            session.close()

    @classmethod
    def execute_with_safety(
        cls,
        source_name: str,
        domain: str,
        collection_func: Callable[[], Dict[str, Any]],
        max_retries: int = 1,
        inter_request_delay_seconds: float = 2.0
    ) -> Dict[str, Any]:
        """
        Executes collection wrapped in domain locks, rate limits, and controlled retry rules.
        """
        if cls.is_source_blocked(source_name):
            logger.warning(f"Skipping collection for '{source_name}': circuit breaker is OPEN (blocked).")
            return {"status": "BLOCKED", "reason": "Circuit breaker is active for this source."}

        lock = cls.get_domain_lock(domain)
        with lock:
            # Conservative pause before engaging target domain
            time.sleep(inter_request_delay_seconds)

            attempt = 0
            while attempt <= max_retries:
                attempt += 1
                try:
                    result = collection_func()

                    # Check for explicit circuit breaker response
                    if result.get("status") == "BLOCKED":
                        cls.mark_source_blocked(source_name, result.get("error", "Access restricted"))
                        return result

                    if result.get("status") == "SUCCESS":
                        return result

                    # If ordinary failure and we have retries left:
                    if attempt <= max_retries:
                        logger.warning(
                            f"Attempt {attempt} failed for '{source_name}' ({result.get('error')}). "
                            "Retrying ONCE after conservative 3-second delay..."
                        )
                        time.sleep(3.0)
                        continue
                    else:
                        logger.error(f"Collection failed after {attempt} attempts for '{source_name}'. Halting.")
                        return result

                except Exception as e:
                    err_msg = str(e).lower()
                    if any(term in err_msg for term in ["captcha", "403", "429", "forbidden", "access denied"]):
                        cls.mark_source_blocked(source_name, str(e))
                        raise CircuitBreakerError(f"Halted due to access control on '{source_name}': {e}") from e

                    if attempt <= max_retries:
                        logger.warning(f"Exception on attempt {attempt} for '{source_name}': {e}. Retrying once...")
                        time.sleep(3.0)
                    else:
                        logger.error(f"Permanent failure for '{source_name}' on attempt {attempt}: {e}")
                        raise e

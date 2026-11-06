import time
import asyncio
from typing import Callable, Any, Optional

class CircuitBreakerOpenError(Exception):
    pass

class CircuitBreaker:
    """
    Implements Circuit Breaker pattern for upstream tools/APIs.
    States: CLOSED (normal), OPEN (broken, fast-fail), HALF_OPEN (trial).
    """
    def __init__(self, failure_threshold: int = 5, recovery_timeout_seconds: float = 30.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout_seconds
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = "CLOSED"

    def record_success(self):
        self.failure_count = 0
        self.state = "CLOSED"

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"

    def can_execute(self) -> bool:
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
                return True
            return False
        if self.state == "HALF_OPEN":
            return True
        return False

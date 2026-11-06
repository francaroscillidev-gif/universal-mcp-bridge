import time
from collections import deque
from universal_mcp.models import RateLimitPolicy

class RateLimitExceededError(Exception):
    pass

class RateLimiter:
    def __init__(self, policy: RateLimitPolicy):
        self.policy = policy
        self.timestamps = deque()

    def check_and_record(self):
        now = time.time()
        # Evict old entries
        while self.timestamps and self.timestamps[0] <= now - self.policy.window_seconds:
            self.timestamps.popleft()

        if len(self.timestamps) >= self.policy.max_requests:
            raise RateLimitExceededError(
                f"Rate limit exceeded: maximum {self.policy.max_requests} requests per {self.policy.window_seconds}s"
            )

        self.timestamps.append(now)

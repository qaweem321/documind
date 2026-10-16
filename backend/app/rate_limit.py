import time
from collections import defaultdict, deque


class RateLimiter:
    """Sliding-window limit per key (client IP), in memory. Enough for one instance; several
    instances behind a load balancer would each count separately."""

    def __init__(self, limit: int, window_seconds: float = 60.0) -> None:
        self.limit, self.window = limit, window_seconds
        self._hits: defaultdict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        hits = self._hits[key]
        while hits and hits[0] <= now - self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True

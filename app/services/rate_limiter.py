"""
Abuse Protection & Rate Limiting Service.
Implements an in-memory sliding window algorithm per IP and per Widget.
Prevents rapid floods with HTTP 429 while allowing normal traffic from other clients.
"""

import time
from collections import defaultdict, deque
from typing import Tuple, Dict
from app.config import settings


class SlidingWindowRateLimiter:
    def __init__(
        self,
        burst_max: int = settings.RATE_LIMIT_BURST_MAX,
        burst_window_seconds: int = settings.RATE_LIMIT_BURST_WINDOW_SECONDS,
        minute_max: int = settings.RATE_LIMIT_PER_MINUTE_IP,
    ):
        self.burst_max = burst_max
        self.burst_window_seconds = burst_window_seconds
        self.minute_max = minute_max
        self.minute_window_seconds = 60

        # Memory store: key -> deque of timestamps
        self._ip_history: Dict[str, deque] = defaultdict(deque)
        self._widget_history: Dict[str, deque] = defaultdict(deque)

    def _clean_and_check(
        self,
        history: deque,
        now: float,
        burst_limit: int,
        burst_window: int,
        minute_limit: int,
        minute_window: int
    ) -> Tuple[bool, int]:
        # Evict timestamps older than 60 seconds
        while history and history[0] <= now - minute_window:
            history.popleft()

        # Check minute window limit
        if len(history) >= minute_limit:
            oldest = history[0]
            retry_after = max(1, int(oldest + minute_window - now))
            return False, retry_after

        # Count requests inside the burst window
        burst_start = now - burst_window
        burst_count = sum(1 for ts in history if ts > burst_start)

        if burst_count >= burst_limit:
            # Find the oldest entry in the burst window
            for ts in history:
                if ts > burst_start:
                    retry_after = max(1, int(ts + burst_window - now))
                    return False, retry_after
            return False, burst_window

        # Record this request
        history.append(now)
        return True, 0

    def check_rate_limit(self, client_ip: str, widget_id: str) -> Tuple[bool, int, str]:
        """
        Check rate limit for both client IP and widget.
        Returns: (allowed, retry_after_seconds, reason)
        """
        now = time.time()

        # Check IP limit
        allowed_ip, retry_ip = self._clean_and_check(
            self._ip_history[client_ip],
            now,
            burst_limit=self.burst_max,
            burst_window=self.burst_window_seconds,
            minute_limit=self.minute_max,
            minute_window=self.minute_window_seconds
        )
        if not allowed_ip:
            return False, retry_ip, f"Rate limit exceeded for IP. Please wait {retry_ip} seconds."

        # Check Widget limit (higher volume allowed across distinct widgets)
        allowed_widget, retry_widget = self._clean_and_check(
            self._widget_history[widget_id],
            now,
            burst_limit=self.burst_max * 3,
            burst_window=self.burst_window_seconds,
            minute_limit=settings.RATE_LIMIT_PER_MINUTE_WIDGET,
            minute_window=self.minute_window_seconds
        )
        if not allowed_widget:
            return False, retry_widget, f"Rate limit exceeded for Widget. Please wait {retry_widget} seconds."

        return True, 0, ""

    def reset(self) -> None:
        """Clear all rate limit history (useful for test resets)."""
        self._ip_history.clear()
        self._widget_history.clear()


rate_limiter = SlidingWindowRateLimiter()

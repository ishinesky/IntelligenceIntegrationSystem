# Tools/RateLimiter.py
"""
轻量级内存限流器。

适用于：
  - 按 IP 的滑动窗口速率限制
  - 全局并发信号量（带超时）

注意：
  - 数据仅存于进程内存，多进程部署时不共享。
  - 适用于“防止滥用”而非严格安全审计。
"""

import time
import threading
from collections import deque
from typing import Optional


class SlidingWindowRateLimiter:
    """
    基于滑动窗口的速率限制器。

    每个 key 维护一个时间戳队列，判断窗口内请求数是否超过上限。
    """

    def __init__(self, window_sec: float = 60.0, max_requests: int = 10, cleanup_interval_sec: float = 300.0):
        self.window_sec = window_sec
        self.max_requests = max_requests
        self.cleanup_interval_sec = cleanup_interval_sec

        self._records: dict = {}
        self._lock = threading.RLock()
        self._last_cleanup = time.time()

    def is_allowed(self, key: str) -> bool:
        """返回该 key 是否允许继续请求；如果允许，会记录本次请求。"""
        now = time.time()

        with self._lock:
            self._maybe_cleanup(now)

            queue = self._records.get(key)
            if queue is None:
                queue = deque()
                self._records[key] = queue

            # 移除窗口外记录
            while queue and queue[0] < now - self.window_sec:
                queue.popleft()

            if len(queue) >= self.max_requests:
                return False

            queue.append(now)
            return True

    def remaining(self, key: str) -> int:
        """返回当前窗口内该 key 还剩多少次可用。"""
        now = time.time()
        with self._lock:
            queue = self._records.get(key)
            if not queue:
                return self.max_requests
            while queue and queue[0] < now - self.window_sec:
                queue.popleft()
            return max(0, self.max_requests - len(queue))

    def _maybe_cleanup(self, now: float):
        if now - self._last_cleanup < self.cleanup_interval_sec:
            return
        self._last_cleanup = now
        expired_keys = []
        for key, queue in self._records.items():
            while queue and queue[0] < now - self.window_sec:
                queue.popleft()
            if not queue:
                expired_keys.append(key)
        for key in expired_keys:
            self._records.pop(key, None)


class TimedSemaphore:
    """
    带超时的信号量封装。

    用于限制全局并发数；超过容量时返回 False，调用方应直接返回 503。
    """

    def __init__(self, max_concurrent: int):
        self._semaphore = threading.Semaphore(max_concurrent)

    def acquire(self, timeout: float = 0.0) -> bool:
        """
        尝试获取信号量。

        Args:
            timeout: 等待秒数。0 表示不等待，立即返回。

        Returns:
            bool: True 表示获取成功，False 表示资源不足。
        """
        if timeout <= 0:
            return self._semaphore.acquire(blocking=False)
        return self._semaphore.acquire(timeout=timeout)

    def release(self):
        self._semaphore.release()

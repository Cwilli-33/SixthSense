"""HTTP client utilities for web harvesting.

Provides rate limiting, retry logic, and browser-like request handling
for scraping public data sources.
"""

import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable

import httpx


@dataclass
class RateLimiter:
    """Rate limiter for HTTP requests.

    Implements token bucket algorithm with jitter to avoid
    detection patterns.
    """

    requests_per_minute: int = 30
    min_delay_seconds: float = 1.0
    max_delay_seconds: float = 3.0
    jitter: float = 0.5  # Random variance factor

    _last_request_time: datetime = field(default_factory=lambda: datetime.min)
    _request_count: int = 0
    _window_start: datetime = field(default_factory=datetime.now)

    def wait(self) -> None:
        """Wait appropriate time before next request."""
        now = datetime.now()

        # Reset window if needed
        if (now - self._window_start).total_seconds() >= 60:
            self._window_start = now
            self._request_count = 0

        # Check rate limit
        if self._request_count >= self.requests_per_minute:
            sleep_time = 60 - (now - self._window_start).total_seconds()
            if sleep_time > 0:
                time.sleep(sleep_time)
            self._window_start = datetime.now()
            self._request_count = 0

        # Calculate delay with jitter
        time_since_last = (now - self._last_request_time).total_seconds()
        base_delay = random.uniform(self.min_delay_seconds, self.max_delay_seconds)
        jitter_amount = base_delay * self.jitter * random.uniform(-1, 1)
        target_delay = base_delay + jitter_amount

        if time_since_last < target_delay:
            time.sleep(target_delay - time_since_last)

        self._last_request_time = datetime.now()
        self._request_count += 1


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_retries: int = 3
    base_delay: float = 2.0  # seconds
    max_delay: float = 60.0  # seconds
    exponential_base: float = 2.0
    retryable_status_codes: tuple[int, ...] = (429, 500, 502, 503, 504)
    retryable_exceptions: tuple[type, ...] = (
        httpx.TimeoutException,
        httpx.NetworkError,
        httpx.ConnectError,
    )


class HarvestHTTPClient:
    """HTTP client optimized for web harvesting.

    Features:
    - Browser-like headers to avoid detection
    - Rate limiting to be respectful
    - Retry logic with exponential backoff
    - Session management for cookies
    """

    # Browser-like headers
    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
    }

    def __init__(
        self,
        timeout: float = 30.0,
        rate_limiter: RateLimiter | None = None,
        retry_config: RetryConfig | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        """Initialize the HTTP client.

        Args:
            timeout: Request timeout in seconds
            rate_limiter: Rate limiter configuration
            retry_config: Retry configuration
            logger: Logger instance
        """
        self.timeout = timeout
        self.rate_limiter = rate_limiter or RateLimiter()
        self.retry_config = retry_config or RetryConfig()
        self.logger = logger or logging.getLogger(__name__)
        self._client: httpx.Client | None = None
        self._session_cookies: dict[str, str] = {}

    def __enter__(self) -> "HarvestHTTPClient":
        """Enter context manager."""
        self._client = httpx.Client(
            timeout=self.timeout,
            headers=self.DEFAULT_HEADERS,
            follow_redirects=True,
        )
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager."""
        if self._client:
            self._client.close()
            self._client = None

    @property
    def client(self) -> httpx.Client:
        """Get the HTTP client, creating if needed."""
        if self._client is None:
            self._client = httpx.Client(
                timeout=self.timeout,
                headers=self.DEFAULT_HEADERS,
                follow_redirects=True,
            )
        return self._client

    def get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Make a GET request with rate limiting and retries.

        Args:
            url: URL to request
            params: Query parameters
            headers: Additional headers

        Returns:
            HTTP response

        Raises:
            httpx.HTTPStatusError: If request fails after retries
        """
        return self._request("GET", url, params=params, headers=headers)

    def post(
        self,
        url: str,
        data: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Make a POST request with rate limiting and retries.

        Args:
            url: URL to request
            data: Form data
            json: JSON body
            params: Query parameters
            headers: Additional headers

        Returns:
            HTTP response

        Raises:
            httpx.HTTPStatusError: If request fails after retries
        """
        return self._request("POST", url, data=data, json=json, params=params, headers=headers)

    def _request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make an HTTP request with rate limiting and retries.

        Args:
            method: HTTP method
            url: URL to request
            **kwargs: Additional request arguments

        Returns:
            HTTP response

        Raises:
            httpx.HTTPStatusError: If request fails after retries
        """
        last_exception: Exception | None = None

        for attempt in range(self.retry_config.max_retries + 1):
            try:
                # Apply rate limiting
                self.rate_limiter.wait()

                # Make request
                self.logger.debug(f"Request {method} {url} (attempt {attempt + 1})")
                response = self.client.request(method, url, **kwargs)

                # Check for retryable status codes
                if response.status_code in self.retry_config.retryable_status_codes:
                    if attempt < self.retry_config.max_retries:
                        delay = self._calculate_retry_delay(attempt, response)
                        self.logger.warning(
                            f"Received {response.status_code}, retrying in {delay:.1f}s"
                        )
                        time.sleep(delay)
                        continue

                # Raise for other error status codes
                response.raise_for_status()

                # Update session cookies
                self._session_cookies.update(response.cookies)

                return response

            except self.retry_config.retryable_exceptions as e:
                last_exception = e
                if attempt < self.retry_config.max_retries:
                    delay = self._calculate_retry_delay(attempt)
                    self.logger.warning(
                        f"Request failed with {type(e).__name__}, retrying in {delay:.1f}s"
                    )
                    time.sleep(delay)
                    continue
                raise

        # Should not reach here, but just in case
        if last_exception:
            raise last_exception
        raise RuntimeError("Request failed after all retries")

    def _calculate_retry_delay(
        self,
        attempt: int,
        response: httpx.Response | None = None,
    ) -> float:
        """Calculate delay before retry using exponential backoff.

        Args:
            attempt: Current attempt number (0-based)
            response: Response object (for Retry-After header)

        Returns:
            Delay in seconds
        """
        # Check for Retry-After header
        if response and "Retry-After" in response.headers:
            try:
                return float(response.headers["Retry-After"])
            except ValueError:
                pass

        # Exponential backoff with jitter
        delay = self.retry_config.base_delay * (
            self.retry_config.exponential_base ** attempt
        )
        delay = min(delay, self.retry_config.max_delay)

        # Add jitter (±25%)
        jitter = delay * 0.25 * random.uniform(-1, 1)
        delay += jitter

        return max(0.1, delay)

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            self._client.close()
            self._client = None

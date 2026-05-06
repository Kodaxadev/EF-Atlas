from __future__ import annotations

import random
import time
import urllib.error
import urllib.request
from typing import Optional


def fetch_bytes(
    url: str,
    *,
    timeout_s: float,
    user_agent: str,
    max_retries: int,
    base_delay_s: float,
    polite_delay_s: float,
) -> bytes:
    headers = {
        "User-Agent": user_agent,
        "Accept": "text/plain,text/markdown,text/html;q=0.9,*/*;q=0.8",
    }

    last_err: Optional[BaseException] = None
    for attempt in range(max_retries + 1):
        if attempt > 0:
            backoff = base_delay_s * (2 ** (attempt - 1))
            jitter = random.random() * 0.25 * backoff
            time.sleep(backoff + jitter)

        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                status = getattr(resp, "status", None)
                body = resp.read()
                if status is not None and status >= 400:
                    raise urllib.error.HTTPError(url, status, "HTTP error", resp.headers, None)
                if polite_delay_s > 0:
                    time.sleep(polite_delay_s)
                return body
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            last_err = e
            continue

    assert last_err is not None
    raise last_err


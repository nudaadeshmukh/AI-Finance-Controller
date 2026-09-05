"""HTTP, auth, pagination, retry for the live Razorpay adapter — §27.

Auth: HTTP Basic from `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET`. Pagination:
`count`/`skip`, drain until short page. Retry: 3 attempts, exponential
backoff with jitter, on 5xx and 429 only — never on 4xx, since a 401 is a
config error and retrying hides it. Raises `SourceUnavailable` on exhaustion.

Stub in Phase 1; implemented (as a documented stub or a real client,
per the VERIFY task in §27) in Phase 2.
"""

from __future__ import annotations

from collections.abc import Iterator


def fetch_recon(
    year: int, month: int, day: int | None = None, *, page_size: int = 100
) -> Iterator[dict]:
    """§20.4. Live-adapter pagination over the recon endpoint."""
    raise NotImplementedError

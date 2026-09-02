# VERIFY: test-mode recon endpoint behaviour — see reference/master_specification.md
# section 27. Per docs/project-progress.md, this was checked 1 September 2026:
# GET /v1/settlements/recon/combined authenticates with test-mode keys and returns
# a valid empty collection ({"entity":"collection","count":0,"items":[]}) - test
# mode generates no settlements since they require real money movement to a
# verified bank account. There is nothing for a live adapter to return in this
# environment, so it ships as this documented stub rather than a fabricated
# integration (PROJECT_RULES.md rule 11).
"""Live Razorpay adapter. Every method raises `SourceUnavailable` immediately."""

from __future__ import annotations

from collections.abc import Iterator

from recon.errors import SourceUnavailable

_NOT_IMPLEMENTED = "live adapter not implemented"


class RazorpayAdapter:
    """`SourceAdapter` backed by the live Razorpay API. Documented stub — see
    the module comment above and section 27's VERIFY note.
    """

    def __init__(self, **kwargs: object) -> None:
        del kwargs  # accepted for signature compatibility with get_adapter(**kw)

    def orders(self) -> Iterator[dict]:
        raise SourceUnavailable(_NOT_IMPLEMENTED)

    def recon_lines(self) -> Iterator[dict]:
        raise SourceUnavailable(_NOT_IMPLEMENTED)

    def bank_txns(self) -> Iterator[dict]:
        raise SourceUnavailable(_NOT_IMPLEMENTED)

    def ledger_entries(self) -> Iterator[dict]:
        raise SourceUnavailable(_NOT_IMPLEMENTED)

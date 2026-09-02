"""The complete Python exception taxonomy for this project — §21, CLAUDE.md rule 10.

Exactly three classes exist. Data defects and business ambiguity are never raised
as Python exceptions — they are `Exception_` records written to the database by
`ingest/` and `verify/`. A pipeline that dies on row 217 of 400 is useless; one
that quarantines it and reports it is the product.
"""

from __future__ import annotations


class ReconError(Exception):
    """Base class for the three configured failure modes. Never raised directly."""


class ConfigurationError(ReconError):
    """Invalid or missing configuration that prevents the pipeline from starting.

    Fails fast, before any write. Exit code 1.
    """


class SourceUnavailable(ReconError):
    """A source adapter could not be read. Fails before any write. Exit code 2."""


class ScoringError(ReconError):
    """An internal error during scoring, distinct from a missing/absent answer key
    (a missing key omits metrics; it does not raise). Exit code 3.
    """

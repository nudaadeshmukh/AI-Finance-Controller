"""§20.1 — shared type aliases. Zero internal imports (stdlib only), so every
other model module can depend on this one without ever creating a cycle.

`models/sources.py` deliberately does NOT host these: sources.py describes the
four raw external schemas and should stay a leaf with no dependents of its
own, rather than becoming an unrelated import every other model module needs
just to get `RecordKey`.
"""

from __future__ import annotations

RecordKey = str  # "<source>:<id>", source ∈ order | recon | bank | ledger
RunId = str  # "clean-august"
GroupId = str  # "grp_<settlement_suffix>"
Paise = int  # enforced by tests/test_money.py — never a float

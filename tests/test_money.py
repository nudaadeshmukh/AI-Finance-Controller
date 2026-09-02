"""§4.1, PROJECT_RULES.md rule 1 — all money is `int` paise. No floats, no `Decimal`,
anywhere. ₹1,000.00 is `100000`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from recon.models.facts import FeeSlab
from recon.models.pipeline import ArithmeticProof
from recon.models.sources import BankTxn, LedgerEntry, Order, ReconLine

MONEY_FIELDS: dict[type, tuple[str, ...]] = {
    Order: ("amount",),
    ReconLine: ("debit", "credit", "amount", "fee", "tax"),
    BankTxn: ("credit", "debit", "balance"),
    LedgerEntry: ("debit", "credit"),
    ArithmeticProof: ("gross", "fees", "tax", "refunds", "expected_net", "observed_net", "delta"),
    FeeSlab: ("inferred_bps",),  # basis points: an int rate, not rupees, but still integral
}


def _annotation_is_int_or_optional_int(annotation: object) -> bool:
    text = str(annotation)
    # Accept `int`, `int | None` — reject anything mentioning float or Decimal.
    return "float" not in text and "Decimal" not in text and "int" in text


def test_money_fields_are_int_typed() -> None:
    violations: list[str] = []
    for model, field_names in MONEY_FIELDS.items():
        for field_name in field_names:
            field_info = model.model_fields[field_name]
            if not _annotation_is_int_or_optional_int(field_info.annotation):
                violations.append(f"{model.__name__}.{field_name}: {field_info.annotation!r}")

    assert not violations, (
        "All money fields must be int paise, never float/Decimal (§4.1). Violations:\n"
        + "\n".join(violations)
    )


def test_no_float_construction_from_money_fields() -> None:
    """A quick sanity check that pydantic actually rejects a float where a
    money field expects int, rather than silently coercing and losing the
    "always paise" guarantee at the boundary.
    """
    with pytest.raises(ValidationError):
        Order(
            order_id="order_test",
            receipt="",
            customer_id="cust_test",
            amount=100.5,  # type: ignore[arg-type]
            currency="INR",
            status="paid",
            created_at=0,
            notes={},
        )


def test_committed_results_json_has_no_floats_on_money_fields() -> None:
    """If any `data/<run>/results.json` is already committed, its known money
    fields must be JSON integers, never JSON floats. No-op until Phase 5
    starts committing these.
    """
    money_paths = [
        ("summary", "matched"),
        ("summary", "false_matches"),
        ("summary", "unresolved"),
        ("summary", "excluded"),
        ("source_totals", "orders_gross"),
        ("source_totals", "recon_net"),
        ("source_totals", "bank_credited"),
        ("source_totals", "ledger_revenue"),
    ]

    for results_file in Path("data").glob("*/results.json"):
        data = json.loads(results_file.read_text(encoding="utf-8"))
        for top, key in money_paths:
            if top in data and key in data[top]:
                value = data[top][key]
                assert isinstance(value, int), (
                    f"{results_file}: {top}.{key} = {value!r} is not an int (§4.1)"
                )

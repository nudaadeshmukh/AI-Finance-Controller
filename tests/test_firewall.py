"""CLAUDE.md rule 2 / master spec §4.2 — the most important rule in this
codebase. `match/`, `hypothesize/` and `verify/` must NEVER import from
`recon/generate/`. No shared constants, no shared helpers, no exceptions.

A slab-inference or calendar function that quietly imports the generator's
own constants would make the fee-reversal (or timing) result invalid without
anything visibly breaking — this test is the thing that catches it.
"""

from __future__ import annotations

import ast
from pathlib import Path

FIREWALLED_PACKAGES = ["match", "hypothesize", "verify"]
RECON_ROOT = Path(__file__).parent.parent / "recon"


def _imported_module_names(py_file: Path) -> set[str]:
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _references_generate(module_name: str) -> bool:
    return module_name == "recon.generate" or module_name.startswith("recon.generate.")


def test_no_generator_imports_in_firewalled_packages() -> None:
    violations: list[str] = []
    for package in FIREWALLED_PACKAGES:
        package_dir = RECON_ROOT / package
        assert package_dir.is_dir(), f"expected recon/{package}/ to exist"
        for py_file in package_dir.rglob("*.py"):
            for module_name in _imported_module_names(py_file):
                if _references_generate(module_name):
                    rel = py_file.relative_to(RECON_ROOT.parent)
                    violations.append(f"{rel} imports {module_name!r}")

    assert not violations, (
        "match/, hypothesize/ and verify/ must never import from recon/generate/ "
        "(CLAUDE.md rule 2, §4.2). Violations:\n" + "\n".join(violations)
    )


def test_generate_package_is_never_imported_by_the_pipeline() -> None:
    """Belt-and-suspenders: no module anywhere under recon/ (outside
    recon/generate/ itself) imports recon.generate — §3.3: "generate ←
    imported by NOTHING".
    """
    violations: list[str] = []
    for py_file in RECON_ROOT.rglob("*.py"):
        if py_file.is_relative_to(RECON_ROOT / "generate"):
            continue
        for module_name in _imported_module_names(py_file):
            if _references_generate(module_name):
                rel = py_file.relative_to(RECON_ROOT.parent)
                violations.append(f"{rel} imports {module_name!r}")

    assert not violations, (
        "recon/generate/ must be imported by NOTHING in the pipeline (§3.3). Violations:\n"
        + "\n".join(violations)
    )

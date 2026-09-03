"""Environment configuration — §22. Every variable is optional.

A fresh clone with no `.env` must run the full deterministic pipeline over the
frozen datasets and emit complete results. Nothing in this module may raise for
a missing variable; absence means "use the default" or "skip the optional stage."
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_ENV_LOADED = False


def _load_dotenv_once() -> None:
    """Best-effort `.env` loader. No third-party dependency for this — five
    runtime dependencies is the budget and dotenv isn't one of them.
    Missing or malformed `.env` is silently ignored; real env vars always win.
    """
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True

    env_path = Path(".env")
    if not env_path.is_file():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class Config:
    """Every field has a default. Nothing here is required to run."""

    groq_api_key: str | None
    recon_llm_model: str
    recon_llm_timeout_s: int
    razorpay_key_id: str | None
    razorpay_key_secret: str | None
    recon_db_path: str | None
    recon_out_path: str | None


def load_config() -> Config:
    """Read configuration from the environment (and `.env`, if present)."""
    _load_dotenv_once()
    return Config(
        groq_api_key=os.environ.get("GROQ_API_KEY") or None,
        recon_llm_model=os.environ.get("RECON_LLM_MODEL", "openai/gpt-oss-20b"),
        recon_llm_timeout_s=int(os.environ.get("RECON_LLM_TIMEOUT_S", "20")),
        razorpay_key_id=os.environ.get("RAZORPAY_KEY_ID") or None,
        razorpay_key_secret=os.environ.get("RAZORPAY_KEY_SECRET") or None,
        recon_db_path=os.environ.get("RECON_DB_PATH") or None,
        recon_out_path=os.environ.get("RECON_OUT_PATH") or None,
    )


def db_path_for(run_id: str, config: Config | None = None) -> Path:
    """Default: `data/<run_id>/run.db` — §22."""
    config = config or load_config()
    return Path(config.recon_db_path) if config.recon_db_path else Path("data") / run_id / "run.db"


def out_path_for(run_id: str, config: Config | None = None) -> Path:
    """Default: `data/<run_id>/results.json` — §22."""
    config = config or load_config()
    return (
        Path(config.recon_out_path)
        if config.recon_out_path
        else Path("data") / run_id / "results.json"
    )

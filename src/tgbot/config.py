from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    gemini_api_key: str
    catalog_json_path: Path
    order_recipient_phone_number: str
    order_recipient_chat_id: int | None = None
    gemini_model: str = "gemini-2.5-flash"
    catalog_max_candidates: int = 25
    telegram_connect_timeout: float = 30.0
    telegram_read_timeout: float = 30.0
    telegram_write_timeout: float = 30.0
    telegram_pool_timeout: float = 30.0
    telegram_proxy_url: str | None = None


def load_settings() -> Settings:
    load_dotenv()

    catalog_path = os.getenv("CATALOG_JSON_PATH", "./catalog.json")
    max_candidates = int(os.getenv("CATALOG_MAX_CANDIDATES", "25"))

    return Settings(
        telegram_bot_token=_required_env("TELEGRAM_BOT_TOKEN"),
        gemini_api_key=_required_env("GEMINI_API_KEY"),
        catalog_json_path=Path(catalog_path),
        order_recipient_phone_number=_required_env("ORDER_RECIPIENT_PHONE_NUMBER"),
        order_recipient_chat_id=_optional_int_env("ORDER_RECIPIENT_CHAT_ID"),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        catalog_max_candidates=max_candidates,
        telegram_connect_timeout=_float_env("TELEGRAM_CONNECT_TIMEOUT", 30.0),
        telegram_read_timeout=_float_env("TELEGRAM_READ_TIMEOUT", 30.0),
        telegram_write_timeout=_float_env("TELEGRAM_WRITE_TIMEOUT", 30.0),
        telegram_pool_timeout=_float_env("TELEGRAM_POOL_TIMEOUT", 30.0),
        telegram_proxy_url=os.getenv("TELEGRAM_PROXY_URL") or None,
    )


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a number, got: {value}") from exc


def _optional_int_env(name: str) -> int | None:
    value = os.getenv(name)
    if not value:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer, got: {value}") from exc

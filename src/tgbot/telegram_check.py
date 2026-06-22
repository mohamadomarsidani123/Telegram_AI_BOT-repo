from __future__ import annotations

import asyncio
import argparse
import logging

from telegram import Bot
from telegram.error import InvalidToken, NetworkError, TimedOut
from telegram.request import HTTPXRequest

from .config import Settings, load_settings


async def check_telegram(settings: Settings) -> int:
    request = HTTPXRequest(
        connect_timeout=settings.telegram_connect_timeout,
        read_timeout=settings.telegram_read_timeout,
        write_timeout=settings.telegram_write_timeout,
        pool_timeout=settings.telegram_pool_timeout,
        proxy=settings.telegram_proxy_url,
    )
    bot = Bot(settings.telegram_bot_token, request=request)

    try:
        me = await bot.get_me()
    except InvalidToken:
        print("Telegram check failed: TELEGRAM_BOT_TOKEN is invalid.")
        return 2
    except TimedOut:
        print("Telegram check failed: timed out connecting to api.telegram.org.")
        print("If your browser or network cannot reach Telegram, set TELEGRAM_PROXY_URL in .env.")
        return 3
    except NetworkError as exc:
        print(f"Telegram check failed: network error: {exc}")
        print("Check internet, DNS, firewall, VPN, or TELEGRAM_PROXY_URL.")
        return 4

    print(f"Telegram check passed: connected as @{me.username or me.first_name}.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Telegram Bot API connectivity with the current .env settings.")
    parser.add_argument(
        "--timeout",
        type=float,
        help="Override all Telegram timeout values for this check only.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)
    settings = load_settings()
    if args.timeout is not None:
        settings = Settings(
            telegram_bot_token=settings.telegram_bot_token,
            gemini_api_key=settings.gemini_api_key,
            catalog_json_path=settings.catalog_json_path,
            order_recipient_phone_number=settings.order_recipient_phone_number,
            order_recipient_chat_id=settings.order_recipient_chat_id,
            gemini_model=settings.gemini_model,
            catalog_max_candidates=settings.catalog_max_candidates,
            telegram_connect_timeout=args.timeout,
            telegram_read_timeout=args.timeout,
            telegram_write_timeout=args.timeout,
            telegram_pool_timeout=args.timeout,
            telegram_proxy_url=settings.telegram_proxy_url,
        )

    raise SystemExit(asyncio.run(check_telegram(settings)))

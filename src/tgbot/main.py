from __future__ import annotations

import logging

from telegram import Update
from telegram.error import NetworkError, TimedOut

from .bot import OrderingBot
from .catalog import Catalog
from .config import load_settings
from .gemini_client import GeminiOrderingClient
from .orders import OrderStore


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("google_genai").setLevel(logging.WARNING)
    settings = load_settings()

    catalog = Catalog.load(settings.catalog_json_path)
    gemini = GeminiOrderingClient(api_key=settings.gemini_api_key, model=settings.gemini_model)
    bot = OrderingBot(
        catalog=catalog,
        gemini=gemini,
        store=OrderStore(),
        max_candidates=settings.catalog_max_candidates,
        order_recipient_phone_number=settings.order_recipient_phone_number,
        order_recipient_chat_id=settings.order_recipient_chat_id,
    )

    application = bot.build_application(
        settings.telegram_bot_token,
        connect_timeout=settings.telegram_connect_timeout,
        read_timeout=settings.telegram_read_timeout,
        write_timeout=settings.telegram_write_timeout,
        pool_timeout=settings.telegram_pool_timeout,
        proxy_url=settings.telegram_proxy_url,
    )

    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES, bootstrap_retries=3)
    except TimedOut as exc:
        raise SystemExit(
            "Telegram API connection timed out during startup. "
            "Run `tgbot-check-telegram` to verify the token/network. "
            "If your network blocks api.telegram.org, set TELEGRAM_PROXY_URL in .env."
        ) from exc
    except NetworkError as exc:
        raise SystemExit(
            "Telegram API network error during startup. "
            "Run `tgbot-check-telegram` and check internet/DNS/proxy settings."
        ) from exc


if __name__ == "__main__":
    main()

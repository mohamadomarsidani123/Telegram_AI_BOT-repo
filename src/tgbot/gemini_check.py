from __future__ import annotations

import argparse
import asyncio
import logging

from google.genai import errors as genai_errors

from .config import load_settings


async def check_gemini(prompt: str) -> int:
    settings = load_settings()

    from google import genai

    client = genai.Client(api_key=settings.gemini_api_key)
    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=settings.gemini_model,
            contents=prompt,
        )
    except genai_errors.APIError as exc:
        message = str(exc)
        print("Gemini check failed.")
        if "API_KEY_SERVICE_BLOCKED" in message:
            print("Reason: API_KEY_SERVICE_BLOCKED.")
            print("Fix: enable Generative Language API for this Google Cloud project, or use a Gemini API key without this service restriction.")
        else:
            print(message)
        return 2

    print("Gemini check passed.")
    print((response.text or "").strip())
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Gemini API connectivity with the current .env settings.")
    parser.add_argument("--prompt", default="Reply with: ok", help="Prompt to send to Gemini.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)
    raise SystemExit(asyncio.run(check_gemini(args.prompt)))

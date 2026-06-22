from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from google.genai import errors as genai_errors
from pydantic import ValidationError

from .catalog import CatalogStats, SearchMatch
from .orders import DraftOrder
from .schemas import BotActionPlan, BotIntent, SearchKeywordPlan


SYSTEM_PROMPT = """You are an ordering assistant inside a Telegram bot.
Use only the provided catalog candidates. Do not invent item ids, SKUs, prices, or availability.
Return structured JSON matching the schema.

Rules:
- A single user message may contain multiple requests. Return each request as a separate action in order.
- If one request names several products, include every product in the same action's items list. For example, "add meat rice and Pepsi" should return one add_items action with three items.
- For remove/change requests naming several products, include every product in the remove_items action's items list. Do not stop after the first resolved item.
- If the user is asking what is available, answer from the candidates.
- If the user wants to order and one candidate clearly matches, return add_items.
- If the user asks for a price range, cheapest item, lowest price, most expensive item, or items under/over a price, use only the provided candidates. They may already be locally filtered and sorted by price.
- Do not recommend or add an item outside the requested price constraint. If candidates are empty, say no matching catalog items were found for that price constraint.
- Catalog candidates include a unit field from Base Unit of Measure. When unit is KG, quantity means kilograms and may be decimal. Parse weights such as 0.5 kg, half kilo, half kg, 500g, 500 g, نص كيلو, نص كيلوغرام as quantity 0.5; parse 250g as 0.25; parse 1.5 kg as 1.5.
- For candidates whose unit is not KG, quantity must be a whole item count. Do not use decimal quantities for unit/package items.
- Users may mix English, Arabic, Arabizi, and Lebanese slang. Treat common Lebanese names as search hints, for example meat/lahme/لحمة, chicken/farouj/فروج, Pepsi/بيبسي/ببسي, Pepsi/Mirinda/Seven Up abo jambo/ابو جمبو for large bottles, and jambo/jumbo/جامبو for 1.25L when the candidate size confirms it.
- Prefer matching by provided item id or SKU. Use slang and translations to choose among candidates, but never invent an unavailable size, brand, item id, SKU, price, or stock status.
- If the request is ambiguous, return needs_clarification and ask a short question.
- If the user confirms the current draft, return confirm_order.
- If the user cancels, return cancel_order.
- Keep answers concise for Telegram.
"""

SEARCH_KEYWORD_PROMPT = """You generate local catalog search keywords for a Lebanese grocery ordering bot.
Return structured JSON matching the schema.

Rules:
- Include the original user phrase first.
- Generate broad but relevant keyword variants in English, Arabic, Lebanese Arabic, and Arabizi.
- Include likely brand spellings, common misspellings, singular/plural forms, and Lebanese slang.
- For sizes or package hints, include compact and spaced forms such as 1.25L, 1.25 L, 2L, 2 L, 330ml, and 330 ml when relevant.
- For Lebanese slang, include likely catalog words too. Examples: lahme/lahmeh/la7me/لحمة/لحم/meat/beef/lamb, farouj/djej/فروج/دجاج/chicken, Pepsi/bebsi/بيبسي/ببسي, Mirinda/Miranda/ميرندا/ميراندا, Seven Up/7up/7 up/سفن اب, abo jambo/abo jumbo/ابو جمبو for large soft drink bottles, jambo/jumbo/جامبو for 1.25L.
- Do not include unrelated categories. Prefer recall, but keep enough precision that a catalog fuzzy search is not flooded with random products.
- Return at most 15 keywords.
"""


class GeminiOrderingClient:
    def __init__(self, api_key: str, model: str):
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self._model = model

    async def interpret_text(
        self,
        message: str,
        matches: list[SearchMatch],
        draft: DraftOrder,
        catalog_stats: CatalogStats,
        recent_history: list[dict[str, str]],
    ) -> BotActionPlan:
        return await asyncio.to_thread(
            self._interpret_text_sync,
            message,
            matches,
            draft,
            catalog_stats,
            recent_history,
        )

    async def suggest_search_queries(
        self,
        message: str,
        catalog_stats: CatalogStats,
        recent_history: list[dict[str, str]],
    ) -> list[str]:
        return await asyncio.to_thread(
            self._suggest_search_queries_sync,
            message,
            catalog_stats,
            recent_history,
        )

    async def interpret_audio(
        self,
        audio_path: Path,
    ) -> str:
        return await asyncio.to_thread(self._transcribe_audio_sync, audio_path)

    def _interpret_text_sync(
        self,
        message: str,
        matches: list[SearchMatch],
        draft: DraftOrder,
        catalog_stats: CatalogStats,
        recent_history: list[dict[str, str]],
    ) -> BotActionPlan:
        prompt = self._prompt(message, matches, draft, catalog_stats, recent_history)
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_json_schema": BotActionPlan.model_json_schema(),
                },
            )
        except genai_errors.APIError as exc:
            raise GeminiServiceError.from_api_error(exc) from exc
        return _parse_action_plan(response.text)

    def _suggest_search_queries_sync(
        self,
        message: str,
        catalog_stats: CatalogStats,
        recent_history: list[dict[str, str]],
    ) -> list[str]:
        payload: dict[str, Any] = {
            "user_message": message,
            "catalog_summary": catalog_stats.to_prompt_dict(),
            "recent_chat_history": recent_history[-5:],
        }
        prompt = f"{SEARCH_KEYWORD_PROMPT}\n\nContext JSON:\n{json.dumps(payload, ensure_ascii=False)}"
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_json_schema": SearchKeywordPlan.model_json_schema(),
                },
            )
        except genai_errors.APIError as exc:
            raise GeminiServiceError.from_api_error(exc) from exc

        try:
            return _parse_search_keyword_plan(response.text).keywords[:15]
        except (json.JSONDecodeError, ValidationError, ValueError):
            return []

    def _transcribe_audio_sync(self, audio_path: Path) -> str:
        try:
            uploaded_file = self._client.files.upload(file=str(audio_path))
            response = self._client.models.generate_content(
                model=self._model,
                contents=["Transcribe this Telegram voice note. Return only the spoken words.", uploaded_file],
            )
        except genai_errors.APIError as exc:
            raise GeminiServiceError.from_api_error(exc) from exc
        return response.text.strip()

    def _prompt(
        self,
        user_message: str,
        matches: list[SearchMatch],
        draft: DraftOrder,
        catalog_stats: CatalogStats,
        recent_history: list[dict[str, str]],
    ) -> str:
        payload: dict[str, Any] = {
            "user_message": user_message,
            "catalog_summary": catalog_stats.to_prompt_dict(),
            "catalog_candidates": [match.to_prompt_dict() for match in matches],
            "current_draft": draft.to_payload(user={})["items"],
            "recent_chat_history": recent_history[-10:],
        }
        return f"{SYSTEM_PROMPT}\n\nContext JSON:\n{json.dumps(payload, ensure_ascii=False)}"


def _parse_action_plan(text: str) -> BotActionPlan:
    data = json.loads(text)
    if isinstance(data, dict) and "intent" in data:
        return BotActionPlan(actions=[BotIntent.model_validate(data)])
    try:
        return BotActionPlan.model_validate(data)
    except ValidationError:
        return BotActionPlan(actions=[BotIntent.model_validate_json(text)])


def _parse_search_keyword_plan(text: str) -> SearchKeywordPlan:
    try:
        return SearchKeywordPlan.model_validate_json(text)
    except ValidationError:
        data = json.loads(text)
        if isinstance(data, list):
            return SearchKeywordPlan(keywords=[str(item) for item in data])
        return SearchKeywordPlan.model_validate(data)


class GeminiServiceError(RuntimeError):
    def __init__(self, user_message: str, detail: str):
        super().__init__(detail)
        self.user_message = user_message
        self.detail = detail

    @classmethod
    def from_api_error(cls, exc: genai_errors.APIError) -> "GeminiServiceError":
        status_code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
        message = str(exc)
        if "API_KEY_SERVICE_BLOCKED" in message or "generativelanguage.googleapis.com" in message:
            return cls(
                "Gemini is blocked for the configured API key. Enable the Generative Language API for the key's Google Cloud project, or use an unrestricted Gemini API key.",
                message,
            )
        if status_code in {401, 403}:
            return cls(
                "Gemini rejected the configured API key. Check GEMINI_API_KEY permissions and API restrictions.",
                message,
            )
        return cls("Gemini is unavailable right now. Please try again shortly.", message)

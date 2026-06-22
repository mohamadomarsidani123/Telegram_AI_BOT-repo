from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from .catalog import Catalog, build_lebanese_search_queries, parse_price_filter
from .gemini_client import GeminiOrderingClient, GeminiServiceError
from .orders import (
    OrderStore,
    format_quantity,
    normalize_order_quantity,
    resolve_intent_item,
    resolve_intent_item_with_confidence,
)
from .schemas import BotActionPlan, BotIntent

logger = logging.getLogger(__name__)


class OrderingBot:
    def __init__(
        self,
        catalog: Catalog,
        gemini: GeminiOrderingClient,
        store: OrderStore,
        max_candidates: int,
        order_recipient_phone_number: str,
        order_recipient_chat_id: int | None,
    ) -> None:
        self.catalog = catalog
        self.gemini = gemini
        self.store = store
        self.max_candidates = max_candidates
        self.order_recipient_phone_number = order_recipient_phone_number
        self.order_recipient_chat_id = order_recipient_chat_id

    def build_application(
        self,
        telegram_token: str,
        *,
        connect_timeout: float,
        read_timeout: float,
        write_timeout: float,
        pool_timeout: float,
        proxy_url: str | None,
    ) -> Application:
        builder = (
            Application.builder()
            .token(telegram_token)
            .connect_timeout(connect_timeout)
            .read_timeout(read_timeout)
            .write_timeout(write_timeout)
            .pool_timeout(pool_timeout)
            .get_updates_connect_timeout(connect_timeout)
            .get_updates_read_timeout(read_timeout)
            .get_updates_write_timeout(write_timeout)
            .get_updates_pool_timeout(pool_timeout)
        )
        if proxy_url:
            builder = builder.proxy(proxy_url).get_updates_proxy(proxy_url)

        application = builder.build()
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("help", self.help))
        application.add_handler(CommandHandler("chatid", self.chatid))
        application.add_handler(CommandHandler("draft", self.draft))
        application.add_handler(CommandHandler("cancel", self.cancel))
        application.add_handler(MessageHandler(filters.VOICE, self.voice_message))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.text_message))
        application.add_error_handler(self.error_handler)
        return application

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.effective_message.reply_text(
            "Send an item question or an order request. Voice notes are supported too."
        )

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.effective_message.reply_text(
            "Ask about available items, say what you want to order, then reply 'confirm' when the draft is correct."
        )

    async def chatid(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.effective_message.reply_text(f"This chat id is: {update.effective_chat.id}")

    async def draft(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        draft = self.store.get(update.effective_chat.id)
        await update.effective_message.reply_text(draft.summary())

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        self.store.clear(update.effective_chat.id)
        await update.effective_message.reply_text("Order draft cancelled.")

    async def text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message.text or ""
        chat_id = update.effective_chat.id
        if self.store.is_awaiting_full_name(chat_id):
            await self._submit_confirmed_order(update, context, customer_name=message.strip())
            return

        draft = self.store.get(chat_id)
        search_queries = await self._build_search_queries(message, chat_id)
        price_filter = parse_price_filter(message)
        matches = self.catalog.search_matches(search_queries, limit=self.max_candidates, price_filter=price_filter)
        try:
            plan = await self.gemini.interpret_text(
                message,
                matches,
                draft,
                self.catalog.stats,
                self.store.history(chat_id),
            )
        except GeminiServiceError as exc:
            logger.warning("Gemini text request failed: %s", exc.detail)
            await update.effective_message.reply_text(exc.user_message)
            return
        await self._apply_action_plan(update, context, plan)

    async def voice_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        chat_id = update.effective_chat.id
        if self.store.is_awaiting_full_name(chat_id):
            await self._reply(update, "Please send your full name as text to finish the order.")
            return

        draft = self.store.get(chat_id)

        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / f"{message.voice.file_unique_id}.ogg"
            telegram_file = await context.bot.get_file(message.voice.file_id)
            await telegram_file.download_to_drive(custom_path=str(audio_path))
            try:
                transcript = await self.gemini.interpret_audio(audio_path)
            except GeminiServiceError as exc:
                logger.warning("Gemini audio request failed: %s", exc.detail)
                await update.effective_message.reply_text(exc.user_message)
                return

        search_queries = await self._build_search_queries(transcript, chat_id)
        price_filter = parse_price_filter(transcript)
        matches = self.catalog.search_matches(search_queries, limit=self.max_candidates, price_filter=price_filter)
        try:
            plan = await self.gemini.interpret_text(
                transcript,
                matches,
                draft,
                self.catalog.stats,
                self.store.history(chat_id),
            )
        except GeminiServiceError as exc:
            logger.warning("Gemini text request failed after audio transcription: %s", exc.detail)
            await update.effective_message.reply_text(exc.user_message)
            return

        await self._apply_action_plan(update, context, plan)

    async def _build_search_queries(self, message: str, chat_id: int) -> list[str]:
        search_queries = build_lebanese_search_queries(message)
        try:
            model_queries = await self.gemini.suggest_search_queries(
                message,
                self.catalog.stats,
                self.store.history(chat_id),
            )
        except GeminiServiceError as exc:
            logger.warning("Gemini search keyword request failed: %s", exc.detail)
            return search_queries

        return _merge_search_queries(search_queries, model_queries)

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.exception("Unhandled Telegram update error", exc_info=context.error)
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text("Something went wrong while processing that message.")

    async def _reply(self, update: Update, text: str) -> None:
        await update.effective_message.reply_text(text)
        user_text = update.effective_message.text or "<voice>"
        self.store.record_chat(update.effective_chat.id, user=user_text, bot=text)

    async def _apply_action_plan(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        plan: BotActionPlan,
    ) -> None:
        actions = plan.actions or [BotIntent(intent="needs_clarification", clarification_question="What would you like to do?")]
        replies: list[str] = []
        for action in actions:
            reply = await self._apply_intent(update, context, action)
            if reply:
                replies.append(reply)
            if action.intent in {"confirm_order", "cancel_order", "needs_clarification"}:
                break

        await self._reply(update, "\n\n".join(replies) if replies else "Done.")

    async def _apply_intent(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent: BotIntent,
    ) -> str:
        chat_id = update.effective_chat.id
        draft = self.store.get(chat_id)

        if intent.intent == "answer_catalog_question":
            return intent.answer or "I found matching catalog items."

        if intent.intent == "needs_clarification":
            return intent.clarification_question or intent.answer or "Which exact item did you mean?"

        if intent.intent == "show_draft":
            return draft.summary()

        if intent.intent == "cancel_order":
            self.store.clear(chat_id)
            return "Order draft cancelled."

        if intent.intent == "remove_items":
            removed_any = False
            invalid_quantities: list[str] = []
            for intent_item in intent.items:
                item = resolve_intent_item(self.catalog, intent_item)
                if item:
                    quantity = normalize_order_quantity(item, intent_item.quantity)
                    if quantity is None:
                        invalid_quantities.append(item.description)
                        continue
                    removed_any = draft.remove(item.id, quantity) or removed_any
            if invalid_quantities:
                return "Please use whole quantities for non-KG items:\n- " + "\n- ".join(invalid_quantities)
            return draft.summary() if removed_any else "I could not find that item in your draft."

        if intent.intent == "add_items":
            added: list[str] = []
            ambiguous: list[str] = []
            unresolved: list[str] = []
            for intent_item in intent.items:
                resolution = resolve_intent_item_with_confidence(self.catalog, intent_item)
                if resolution.status == "resolved" and resolution.item:
                    quantity = normalize_order_quantity(resolution.item, intent_item.quantity)
                    if quantity is None:
                        ambiguous.append(f"{resolution.item.description}: please use a whole quantity unless the item is sold by KG.")
                        continue
                    draft.add(resolution.item, quantity)
                    added.append(
                        f"{format_quantity(resolution.item, quantity)} x {resolution.item.description} ({resolution.item.sku})"
                    )
                elif resolution.status == "ambiguous":
                    suggestions = ", ".join(
                        f"{item.description} ({item.sku})" for item in resolution.suggestions[:3]
                    )
                    ambiguous.append(f"{resolution.requested}: did you mean {suggestions}?")
                else:
                    unresolved.append(resolution.requested)

            response_parts: list[str] = []
            if added:
                response_parts.append("Added:\n- " + "\n- ".join(added))
            if ambiguous:
                response_parts.append("I need you to clarify:\n- " + "\n- ".join(ambiguous))
            if unresolved:
                response_parts.append("I could not find:\n- " + "\n- ".join(unresolved))
            if draft.is_empty():
                response_parts.append("No items were added yet.")
            else:
                response_parts.append(draft.summary())

            return "\n\n".join(response_parts)

        if intent.intent == "confirm_order":
            if draft.is_empty():
                return "Your order is empty. Tell me what you want to order first."

            self.store.mark_awaiting_full_name(chat_id)
            return "Please send your full name to finish the order."

        return "I could not understand that. Please rephrase."

    async def _submit_confirmed_order(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        *,
        customer_name: str,
    ) -> None:
        chat_id = update.effective_chat.id
        draft = self.store.get(chat_id)

        if not customer_name:
            await self._reply(update, "Please send your full name to finish the order.")
            return
        if draft.is_empty():
            self.store.clear(chat_id)
            await self._reply(update, "Your order is empty. Tell me what you want to order first.")
            return
        if self.order_recipient_chat_id is None:
            await self._reply(
                update,
                "Order recipient chat is not configured. Set ORDER_RECIPIENT_CHAT_ID so I can route orders.",
            )
            return

        message = draft.order_message(
            customer_name=customer_name,
            customer=_telegram_user(update),
            recipient_phone=self.order_recipient_phone_number,
        )
        try:
            await context.bot.send_message(chat_id=self.order_recipient_chat_id, text=message)
        except Exception:
            logger.exception("Order routing failed")
            await self._reply(update, "I could not route the order. Please try again.")
            return

        self.store.clear(chat_id)
        await self._reply(update, "Order sent.")


def _telegram_user(update: Update) -> dict[str, object]:
    user = update.effective_user
    if not user:
        return {}
    return {
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
    }


def _merge_search_queries(*query_groups: list[str], limit: int = 60) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for queries in query_groups:
        for query in queries:
            text = str(query).strip()
            key = text.lower()
            if text and key not in seen:
                seen.add(key)
                merged.append(text)
                if len(merged) >= limit:
                    return merged
    return merged

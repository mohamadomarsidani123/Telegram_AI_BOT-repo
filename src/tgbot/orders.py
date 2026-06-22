from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Deque

from .catalog import Catalog, CatalogItem, SearchMatch, build_lebanese_search_queries
from .schemas import IntentItem


CONFIDENT_MATCH_SCORE = 55
AMBIGUOUS_MATCH_SCORE = 25
QUANTITY_EPSILON = Decimal("0.000001")


@dataclass
class DraftLine:
    item: CatalogItem
    quantity: Decimal

    @property
    def subtotal(self) -> Decimal | None:
        try:
            return Decimal(self.item.price) * self.quantity
        except InvalidOperation:
            return None


@dataclass
class DraftOrder:
    lines: dict[str, DraftLine] = field(default_factory=dict)

    def add(self, item: CatalogItem, quantity: Decimal) -> None:
        existing = self.lines.get(item.id)
        if existing:
            existing.quantity += quantity
            return
        self.lines[item.id] = DraftLine(item=item, quantity=quantity)

    def remove(self, item_id: str, quantity: Decimal | None = None) -> bool:
        existing = self.lines.get(item_id)
        if not existing:
            return False
        if quantity is None or quantity >= existing.quantity - QUANTITY_EPSILON:
            del self.lines[item_id]
        else:
            existing.quantity -= quantity
        return True

    def clear(self) -> None:
        self.lines.clear()

    def is_empty(self) -> bool:
        return not self.lines

    def summary(self) -> str:
        if not self.lines:
            return "Your order is empty."

        lines: list[str] = ["Current order:"]
        total_by_currency: dict[str, Decimal] = {}

        for line in self.lines.values():
            item = line.item
            price = format_unit_price(item)
            lines.append(f"- {format_quantity(item, line.quantity)} x {item.description} ({item.sku}) at {price}")
            if line.subtotal is not None and item.currency:
                total_by_currency[item.currency] = total_by_currency.get(item.currency, Decimal("0")) + line.subtotal

        if total_by_currency:
            totals = ", ".join(f"{amount} {currency}" for currency, amount in total_by_currency.items())
            lines.append(f"Estimated total: {totals}")

        lines.append("Reply 'confirm' to submit, or tell me what to change.")
        return "\n".join(lines)

    def to_payload(self, user: dict[str, object]) -> dict[str, object]:
        return {
            "telegram_user": user,
            "items": [
                {
                    "id": line.item.id,
                    "sku": line.item.sku,
                    "description": line.item.description,
                    "quantity": str(_clean_decimal(line.quantity)),
                    "unit": line.item.unit,
                    "unit_price": line.item.price,
                    "currency": line.item.currency,
                }
                for line in self.lines.values()
            ],
            "source": "telegram_bot",
        }

    def order_message(self, *, customer_name: str, customer: dict[str, object], recipient_phone: str) -> str:
        lines = [
            "New order",
            f"Customer: {customer_name}",
            f"Recipient phone: {recipient_phone}",
        ]
        username = customer.get("username")
        user_id = customer.get("id")
        if username:
            lines.append(f"Telegram: @{username}")
        elif user_id:
            lines.append(f"Telegram user id: {user_id}")

        lines.append("")
        lines.append("Items:")
        total_by_currency: dict[str, Decimal] = {}
        for line in self.lines.values():
            item = line.item
            price = format_unit_price(item)
            lines.append(f"- {format_quantity(item, line.quantity)} x {item.description} ({item.sku}) at {price}")
            if line.subtotal is not None and item.currency:
                total_by_currency[item.currency] = total_by_currency.get(item.currency, Decimal("0")) + line.subtotal

        if total_by_currency:
            totals = ", ".join(f"{amount} {currency}" for currency, amount in total_by_currency.items())
            lines.append("")
            lines.append(f"Estimated total: {totals}")

        return "\n".join(lines)


class OrderStore:
    def __init__(self) -> None:
        self._drafts: dict[int, DraftOrder] = {}
        self._history: dict[int, Deque[dict[str, str]]] = {}
        self._awaiting_full_name: set[int] = set()

    def get(self, chat_id: int) -> DraftOrder:
        if chat_id not in self._drafts:
            self._drafts[chat_id] = DraftOrder()
        return self._drafts[chat_id]

    def clear(self, chat_id: int) -> None:
        self._drafts.pop(chat_id, None)
        self._awaiting_full_name.discard(chat_id)

    def mark_awaiting_full_name(self, chat_id: int) -> None:
        self._awaiting_full_name.add(chat_id)

    def is_awaiting_full_name(self, chat_id: int) -> bool:
        return chat_id in self._awaiting_full_name

    def clear_awaiting_full_name(self, chat_id: int) -> None:
        self._awaiting_full_name.discard(chat_id)

    def history(self, chat_id: int) -> list[dict[str, str]]:
        return list(self._history.get(chat_id, deque()))

    def record_chat(self, chat_id: int, *, user: str, bot: str) -> None:
        if chat_id not in self._history:
            self._history[chat_id] = deque(maxlen=10)
        self._history[chat_id].append({"user": user, "bot": bot})


@dataclass(frozen=True)
class ItemResolution:
    status: str
    requested: str
    item: CatalogItem | None = None
    suggestions: tuple[CatalogItem, ...] = ()


def resolve_intent_item(catalog: Catalog, intent_item: IntentItem) -> CatalogItem | None:
    resolution = resolve_intent_item_with_confidence(catalog, intent_item)
    return resolution.item if resolution.status == "resolved" else None


def resolve_intent_item_with_confidence(catalog: Catalog, intent_item: IntentItem) -> ItemResolution:
    requested = intent_item.item_id or intent_item.sku or intent_item.description or "requested item"

    if intent_item.item_id:
        item = catalog.get(intent_item.item_id)
        if item:
            return ItemResolution(status="resolved", requested=requested, item=item)

    if intent_item.sku:
        matches = catalog.search_matches(build_lebanese_search_queries(intent_item.sku), limit=3)
        resolution = _resolution_from_matches(requested, matches)
        if resolution.status != "not_found":
            return resolution

    if intent_item.description:
        matches = catalog.search_matches(build_lebanese_search_queries(intent_item.description), limit=3)
        return _resolution_from_matches(requested, matches)

    return ItemResolution(status="not_found", requested=requested)


def normalize_order_quantity(item: CatalogItem, quantity: Decimal) -> Decimal | None:
    quantity = Decimal(str(quantity))
    if quantity <= 0:
        return None
    if is_weight_item(item):
        return _clean_decimal(quantity)
    if quantity == quantity.to_integral_value():
        return quantity
    return None


def is_weight_item(item: CatalogItem) -> bool:
    return item.unit.strip().upper() == "KG"


def format_quantity(item: CatalogItem, quantity: Decimal) -> str:
    quantity_text = str(_clean_decimal(quantity))
    if is_weight_item(item):
        return f"{quantity_text} KG"
    return quantity_text


def format_unit_price(item: CatalogItem) -> str:
    price = f"{item.price} {item.currency}".strip()
    if is_weight_item(item):
        return f"{price}/KG"
    return price


def _resolution_from_matches(requested: str, matches: list[SearchMatch]) -> ItemResolution:
    if not matches:
        return ItemResolution(status="not_found", requested=requested)

    best = matches[0]
    if best.match_type in {"exact_id", "exact_sku"} or best.score >= CONFIDENT_MATCH_SCORE:
        return ItemResolution(status="resolved", requested=requested, item=best.item)
    if best.score >= AMBIGUOUS_MATCH_SCORE:
        return ItemResolution(
            status="ambiguous",
            requested=requested,
            suggestions=tuple(match.item for match in matches),
        )
    return ItemResolution(status="not_found", requested=requested)


def _clean_decimal(value: Decimal) -> Decimal:
    value = value.normalize()
    if value == value.to_integral_value():
        return value.quantize(Decimal("1"))
    return value

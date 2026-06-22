from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


IntentType = Literal[
    "answer_catalog_question",
    "add_items",
    "remove_items",
    "show_draft",
    "confirm_order",
    "cancel_order",
    "needs_clarification",
]


class IntentItem(BaseModel):
    item_id: str = Field(default="", description="Catalog item id if resolved.")
    sku: str = Field(default="", description="Catalog SKU/code if resolved.")
    description: str = Field(default="", description="Catalog description or user phrase.")
    quantity: Decimal = Field(
        default=Decimal("1"),
        gt=0,
        description="Whole count for unit items, or kilogram weight for KG items. KG items may use decimals.",
    )


class BotIntent(BaseModel):
    intent: IntentType
    answer: str = Field(default="", description="Natural language answer for the user.")
    items: list[IntentItem] = Field(default_factory=list)
    clarification_question: str = ""


class BotActionPlan(BaseModel):
    actions: list[BotIntent] = Field(
        default_factory=list,
        description="Ordered actions to execute for the user's message.",
    )


class SearchKeywordPlan(BaseModel):
    keywords: list[str] = Field(
        default_factory=list,
        description="Search keyword variants for local catalog search.",
    )

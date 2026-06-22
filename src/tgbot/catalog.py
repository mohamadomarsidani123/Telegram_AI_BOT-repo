from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Sequence


TOKEN_RE = re.compile(r"[^\W_]+(?:[./-][^\W_]+)*", re.IGNORECASE | re.UNICODE)
STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "for",
    "have",
    "i",
    "in",
    "is",
    "it",
    "me",
    "of",
    "on",
    "or",
    "please",
    "show",
    "the",
    "to",
    "want",
    "with",
    "you",
    "l",
    "lt",
    "ltr",
    "liter",
    "liters",
    "ml",
    "g",
    "kg",
    "بدي",
    "بدنا",
    "اريد",
    "عايز",
    "من",
    "عن",
    "على",
    "في",
    "و",
    "مع",
    "لو",
    "اذا",
    "عندك",
    "عندكن",
    "اعطيني",
    "هات",
    "شوف",
    "ورجيني",
}
LEBANESE_SEARCH_ALIASES: tuple[tuple[str, ...], ...] = (
    ("meat", "beef", "veal", "lamb", "lahme", "lahmeh", "la7me", "لحمة", "لحمه", "لحم", "غنم", "بقر", "عجل"),
    ("chicken", "poultry", "farouj", "frouj", "dejaj", "djej", "دجاج", "جاج", "فروج", "فراخ"),
    ("fish", "seafood", "samak", "سمك", "بحري"),
    ("milk", "haleeb", "7alib", "حليب", "حليپ"),
    ("yogurt", "laban", "لبن", "روب"),
    ("cheese", "jibne", "jebne", "جبنة", "جبن"),
    ("bread", "khobez", "khobz", "خبز", "ربطة"),
    ("rice", "rez", "riz", "ارز", "رز"),
    ("sugar", "sokar", "سكر"),
    ("salt", "mele7", "melh", "ملح"),
    ("oil", "zeit", "زيت"),
    ("water", "may", "maye", "مي", "مياه", "ماء"),
    ("soda", "soft drink", "soft drinks", "مشروب", "مشروبات", "غازية"),
    ("pepsi", "bebsi", "bipsi", "بيبسي", "ببسي", "بپسي"),
    ("pepsi 2l", "pepsi 2 l", "pepsi 2 liter", "pepsi 2 liters", "2.25l", "2.25 l", "pepsi 2.25l", "pepsi 2.25 l", "pepsi 2.25 liter", "pepsi abo jambo", "abo jambo", "abu jambo", "abo jumbo", "abu jumbo", "ابو جمبو", "أبو جمبو", "بيبسي ابو جمبو", "ببسي ابو جمبو"),
    ("1.25l", "1.25 l", "pepsi 1.25l", "pepsi 1.25 l", "pepsi 1.25 liter", "pepsi 1.25 liters", "jambo", "jumbo", "جامبو", "جمبو", "بيبسي جامبو", "ببسي جامبو"),
    ("mirinda", "miranda", "ميرندا", "ميراندا", "مرندا"),
    ("mirinda 2l", "mirinda 2 l", "mirinda 2 liter", "mirinda 2 liters", "2.25l", "2.25 l", "1.5l", "1.5 l", "mirinda 2.25l", "mirinda 2.25 l", "mirinda 2.25 liter", "mirinda 1.5l", "mirinda 1.5 l", "miranda 1.5l", "miranda 1.5 l", "mirinda abo jambo", "mirinda abo jumbo", "mirinda abu jambo", "mirinda abu jumbo", "miranda abo jambo", "miranda abo jumbo", "miranda abu jambo", "miranda abu jumbo", "ميرندا ابو جمبو", "ميراندا ابو جمبو"),
    ("1.25l", "1.25 l", "mirinda 1.25l", "mirinda 1.25 l", "mirinda 1.25 liter", "mirinda 1.25 liters", "miranda 1.25l", "miranda 1.25 l", "miranda 1.25 liter", "miranda 1.25 liters", "mirinda jambo", "mirinda jumbo", "miranda jambo", "miranda jumbo", "ميرندا جامبو", "ميراندا جامبو"),
    ("coke", "coca cola", "coca-cola", "كوكا كولا", "كولا"),
    ("sprite", "سبرايت", "سبرایت"),
    ("seven up", "7up", "7 up", "sevenup", "سفن اب", "سفن أب"),
    ("seven up 2l", "seven up 2 l", "seven up 2 liter", "seven up 2 liters", "7 up 2l", "7 up 2 l", "7up 2l", "7up 2.25l", "2.25l", "2.25 l", "seven up 2.25l", "seven up 2.25 l", "7 up 2.25l", "7 up 2.25 l", "seven up abo jambo", "seven up abo jumbo", "seven up abu jambo", "seven up abu jumbo", "7 up abo jambo", "7 up abo jumbo", "7up abo jambo", "7up abo jumbo", "سفن اب ابو جمبو", "سفن أب ابو جمبو"),
    ("1.25l", "1.25 l", "seven up 1.25l", "seven up 1.25 l", "7 up 1.25l", "7 up 1.25 l", "7up 1.25l", "7up 1.25 l", "seven up jambo", "seven up jumbo", "7 up jambo", "7 up jumbo", "7up jambo", "7up jumbo", "سفن اب جامبو", "سفن أب جامبو"),
    ("juice", "asir", "عصير", "جوس"),
    ("coffee", "cafe", "nescafe", "قهوة", "كافي", "نسكافيه"),
    ("tea", "shai", "شاي"),
    ("eggs", "egg", "bayd", "بيض"),
    ("tuna", "ton", "تونا", "طون"),
    ("pasta", "macaroni", "معكرونة", "مكرونة", "باستا"),
    ("detergent", "cleaner", "تنظيف", "منظف", "مسحوق"),
    ("diapers", "diaper", "حفاض", "حفاضات", "بامبرز"),
    ("baby", "infant", "بيبي", "اطفال", "أطفال"),
)
SOFT_DRINK_BRANDS: dict[str, tuple[str, ...]] = {
    "pepsi": ("pepsi", "bebsi", "bipsi", "بيبسي", "ببسي", "بپسي"),
    "mirinda": ("mirinda", "miranda", "ميرندا", "ميراندا", "مرندا"),
    "seven_up": ("seven up", "sevenup", "7 up", "7up", "سفن اب", "سفن أب"),
}
FIELD_WEIGHTS = {
    "id": 120,
    "sku": 90,
    "description": 35,
    "family": 25,
    "category": 22,
    "product_group": 18,
    "division": 12,
    "vendor": 8,
}
PRICE_NUMBER_RE = re.compile(r"(?<![a-z0-9])(?:\$|usd|lbp)?\s*(\d+(?:[.,]\d+)?)\s*(?:\$|usd|lbp)?", re.IGNORECASE)
PRICE_FILTER_WORDS = {
    "price",
    "priced",
    "cost",
    "costs",
    "cheap",
    "cheaper",
    "cheapest",
    "expensive",
    "priciest",
    "under",
    "below",
    "less",
    "than",
    "maximum",
    "max",
    "over",
    "above",
    "more",
    "minimum",
    "min",
    "between",
    "from",
    "range",
    "usd",
    "lbp",
    "dollar",
    "dollars",
    "lira",
    "liras",
    "ليرة",
    "دولار",
    "سعر",
    "ارخص",
    "رخيص",
    "غالي",
    "اقل",
    "أقل",
    "اكتر",
    "أكتر",
    "اكثر",
    "أكثر",
    "بين",
    "تحت",
    "فوق",
}


@dataclass(frozen=True)
class CatalogItem:
    id: str
    sku: str
    description: str
    unit: str
    vendor_no: str
    category_code: str
    product_group_code: str
    division_code: str
    family_code: str
    price: str
    currency: str

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> "CatalogItem":
        return cls(
            id=str(raw.get("Id") or raw.get("id") or "").strip(),
            sku=str(raw.get("No.") or raw.get("No") or raw.get("sku") or "").strip(),
            description=str(raw.get("Description") or raw.get("description") or "").strip(),
            unit=str(raw.get("Base Unit of Measure") or raw.get("unit") or "").strip(),
            vendor_no=str(raw.get("Vendor No.") or raw.get("vendor_no") or "").strip(),
            category_code=str(raw.get("Item Category Code") or raw.get("category") or "").strip(),
            product_group_code=str(raw.get("Product Group Code") or "").strip(),
            division_code=str(raw.get("Division Code") or "").strip(),
            family_code=str(raw.get("Item Family Code") or "").strip(),
            price=_normalize_price(raw.get("Sales Price") or raw.get("price") or ""),
            currency=str(raw.get("Currency Code") or raw.get("currency") or "").strip(),
        )

    @property
    def searchable_text(self) -> str:
        return " ".join(
            [
                self.id,
                self.sku,
                self.description,
                self.vendor_no,
                self.category_code,
                self.product_group_code,
                self.division_code,
                self.family_code,
            ]
        )

    def to_prompt_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "sku": self.sku,
            "description": self.description,
            "unit": self.unit,
            "category": self.category_code,
            "product_group": self.product_group_code,
            "family": self.family_code,
            "unit_price": self.price,
            "currency": self.currency,
        }


@dataclass(frozen=True)
class SearchMatch:
    item: CatalogItem
    score: float
    matched_terms: tuple[str, ...]
    match_type: str

    def to_prompt_dict(self) -> dict[str, object]:
        payload = self.item.to_prompt_dict()
        payload.update(
            {
                "match_score": round(self.score, 2),
                "match_type": self.match_type,
                "matched_terms": list(self.matched_terms),
            }
        )
        return payload


@dataclass(frozen=True)
class CatalogStats:
    total_items: int
    category_counts: dict[str, int]
    family_counts: dict[str, int]
    currency_counts: dict[str, int]

    def to_prompt_dict(self) -> dict[str, object]:
        return {
            "total_items": self.total_items,
            "top_categories": _top_counts(self.category_counts),
            "top_families": _top_counts(self.family_counts),
            "currencies": self.currency_counts,
        }


@dataclass(frozen=True)
class PriceFilter:
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    currency: str = ""
    sort: str = ""

    @property
    def active(self) -> bool:
        return bool(self.min_price is not None or self.max_price is not None or self.sort)


class Catalog:
    def __init__(self, items: list[CatalogItem]):
        self.items = items
        self._by_id = {item.id: item for item in items if item.id}
        self._by_sku = {item.sku.lower(): item for item in items if item.sku}
        self._field_tokens: dict[str, dict[str, set[str]]] = {}
        self._item_tokens: dict[str, set[str]] = {}
        self._inverted_index: dict[str, set[str]] = defaultdict(set)
        self._token_vocab: set[str] = set()
        self.stats = self._build_stats(items)
        self._build_indexes(items)

    @classmethod
    def load(cls, path: Path) -> "Catalog":
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)

        if isinstance(payload, list):
            raw_items = payload
        elif isinstance(payload, dict) and isinstance(payload.get("items"), list):
            raw_items = payload["items"]
        else:
            raise ValueError("Catalog JSON must be a list or an object with an 'items' list.")

        items = [CatalogItem.from_raw(raw) for raw in raw_items if isinstance(raw, dict)]
        return cls(items)

    def get(self, item_id: str) -> CatalogItem | None:
        return self._by_id.get(item_id)

    def search(
        self,
        query: str | Sequence[str],
        limit: int = 25,
        *,
        price_filter: PriceFilter | None = None,
    ) -> list[CatalogItem]:
        return [match.item for match in self.search_matches(query, limit=limit, price_filter=price_filter)]

    def search_matches(
        self,
        query: str | Sequence[str],
        limit: int = 25,
        *,
        price_filter: PriceFilter | None = None,
    ) -> list[SearchMatch]:
        queries = _normalize_queries(query)
        search_limit = len(self.items) if price_filter and price_filter.active else limit
        if len(queries) > 1:
            matches = self._search_many(queries, limit=search_limit)
        else:
            query = queries[0] if queries else ""
            if price_filter and price_filter.active and _is_price_only_query(query):
                matches = [
                    SearchMatch(item=item, score=0, matched_terms=(), match_type="price_filter")
                    for item in self.items
                ]
            else:
                matches = self._search_one(query, limit=search_limit)

        if price_filter and price_filter.active:
            matches = apply_price_filter(matches, price_filter)
        return matches[:limit]

    def _search_many(self, queries: Sequence[str], limit: int) -> list[SearchMatch]:
        merged: dict[str, SearchMatch] = {}
        coverage: list[str] = []
        original_tokens = _meaningful_tokens(queries[0]) if queries else set()
        search_limit = min(len(self.items), max(limit * 4, limit))
        for index, query in enumerate(queries):
            variant_weight = 1.0 if index == 0 else 0.88
            query_tokens = _meaningful_tokens(query)
            query_matches = self._search_one(query, limit=search_limit, fallback_to_all=False)
            for match in query_matches:
                existing = merged.get(match.item.id)
                weighted_score = match.score * variant_weight
                matched_terms = set(match.matched_terms)
                matched_terms.add(query.lower())
                if existing:
                    weighted_score = max(existing.score, weighted_score) + min(existing.score, weighted_score) * 0.08
                    matched_terms.update(existing.matched_terms)
                    match_type = existing.match_type if existing.score >= match.score else match.match_type
                else:
                    match_type = match.match_type
                merged[match.item.id] = SearchMatch(
                    item=match.item,
                    score=weighted_score,
                    matched_terms=tuple(sorted(matched_terms)),
                    match_type="multi_query" if match_type not in {"exact_id", "exact_sku"} else match_type,
                )

            if index != 0 and not (query_tokens and query_tokens <= original_tokens):
                continue
            for match in query_matches[:3]:
                if match.item.id not in coverage:
                    coverage.append(match.item.id)

        if not merged:
            return self._search_one(queries[0], limit=limit)

        scored = list(merged.values())
        scored.sort(key=lambda match: (-match.score, match.item.description.lower()))
        by_id = {match.item.id: match for match in scored}
        diverse: list[SearchMatch] = []
        seen: set[str] = set()

        for match in scored[: max(3, limit // 3)]:
            diverse.append(match)
            seen.add(match.item.id)

        for item_id in coverage:
            if item_id in by_id and item_id not in seen:
                diverse.append(by_id[item_id])
                seen.add(item_id)
            if len(diverse) >= limit:
                return diverse

        for match in scored:
            if match.item.id not in seen:
                diverse.append(match)
                seen.add(match.item.id)
            if len(diverse) >= limit:
                return diverse

        return diverse

    def _search_one(self, query: str, limit: int = 25, *, fallback_to_all: bool = True) -> list[SearchMatch]:
        query = query.strip()
        if not query:
            return [
                SearchMatch(item=item, score=0, matched_terms=(), match_type="browse")
                for item in self.items[:limit]
            ]

        lowered = query.lower()
        if lowered in self._by_sku:
            return [SearchMatch(self._by_sku[lowered], 500, (lowered,), "exact_sku")]
        if query in self._by_id:
            return [SearchMatch(self._by_id[query], 500, (query,), "exact_id")]

        query_tokens = _meaningful_tokens(query)
        expanded_terms = self._expand_terms(query_tokens)
        candidate_ids = self._candidate_ids(expanded_terms)
        if not candidate_ids:
            if not fallback_to_all:
                return []
            candidate_ids = set(self._by_id)

        scored: list[SearchMatch] = []
        for item_id in candidate_ids:
            item = self._by_id[item_id]
            matched_terms: set[str] = set()
            score = 0.0
            field_tokens = self._field_tokens.get(item_id, {})

            for field, weight in FIELD_WEIGHTS.items():
                tokens = field_tokens.get(field, set())
                direct_matches = query_tokens & tokens
                if direct_matches:
                    matched_terms.update(direct_matches)
                    score += len(direct_matches) * weight

                fuzzy_matches = expanded_terms & tokens
                fuzzy_matches -= direct_matches
                if fuzzy_matches:
                    matched_terms.update(fuzzy_matches)
                    score += len(fuzzy_matches) * weight * 0.55

            searchable = item.searchable_text.lower()
            if lowered in searchable:
                score += 25
                matched_terms.add(lowered)
            compact_query = lowered.replace(" ", "")
            if compact_query and compact_query in searchable.replace(" ", ""):
                score += 20
                matched_terms.add(compact_query)
            if item.sku and item.sku.lower().startswith(lowered.replace(" ", "")):
                score += 60
                matched_terms.add(item.sku.lower())
            if item.description:
                similarity = SequenceMatcher(None, lowered, item.description.lower()).ratio()
                if similarity >= 0.45:
                    score += similarity * 35

            if score:
                match_type = "close" if not (query_tokens & self._item_tokens.get(item_id, set())) else "direct"
                scored.append(
                    SearchMatch(
                        item=item,
                        score=score,
                        matched_terms=tuple(sorted(matched_terms)),
                        match_type=match_type,
                    )
                )

        scored.sort(key=lambda match: (-match.score, match.item.description.lower()))
        return scored[:limit]

    def count(self, query: str = "", *, category: str = "", family: str = "") -> int:
        matches = self.search_matches(query, limit=len(self.items)) if query else [
            SearchMatch(item=item, score=0, matched_terms=(), match_type="browse")
            for item in self.items
        ]
        return sum(1 for match in matches if _matches_filter(match.item, category=category, family=family))

    def _build_indexes(self, items: list[CatalogItem]) -> None:
        for item in items:
            field_tokens = {
                "id": set(_tokens(item.id)),
                "sku": set(_tokens(item.sku)),
                "description": set(_tokens(item.description)),
                "family": set(_tokens(item.family_code)),
                "category": set(_tokens(item.category_code)),
                "product_group": set(_tokens(item.product_group_code)),
                "division": set(_tokens(item.division_code)),
                "vendor": set(_tokens(item.vendor_no)),
            }
            self._field_tokens[item.id] = field_tokens
            item_tokens = set().union(*field_tokens.values())
            self._item_tokens[item.id] = item_tokens
            self._token_vocab.update(item_tokens)
            for token in item_tokens:
                self._inverted_index[token].add(item.id)

    def _expand_terms(self, query_tokens: set[str]) -> set[str]:
        expanded = set(query_tokens)
        for query_token in query_tokens:
            close_count = 0
            for close_term in self._token_vocab:
                if _is_close(query_token, close_term):
                    expanded.add(close_term)
                    close_count += 1
                    if close_count >= 8:
                        break
        return expanded

    def _candidate_ids(self, terms: set[str]) -> set[str]:
        ids: set[str] = set()
        for term in terms:
            ids.update(self._inverted_index.get(term, set()))
        return ids

    @staticmethod
    def _build_stats(items: list[CatalogItem]) -> CatalogStats:
        return CatalogStats(
            total_items=len(items),
            category_counts=dict(Counter(item.category_code for item in items if item.category_code)),
            family_counts=dict(Counter(item.family_code for item in items if item.family_code)),
            currency_counts=dict(Counter(item.currency for item in items if item.currency)),
        )


def _tokens(value: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_RE.finditer(value)]


def _meaningful_tokens(value: str) -> set[str]:
    return {token for token in _tokens(value) if token not in STOP_WORDS}


def build_lebanese_search_queries(message: str, *, max_queries: int = 40) -> list[str]:
    queries = [message.strip()]
    normalized_message = message.lower()
    message_tokens = _meaningful_tokens(message)
    for aliases in LEBANESE_SEARCH_ALIASES:
        if _matches_alias_group(normalized_message, message_tokens, aliases):
            queries.extend(aliases)

    return _normalize_queries(queries)[:max_queries]


def parse_price_filter(message: str) -> PriceFilter | None:
    lowered = message.lower()
    currency = _parse_currency(lowered)
    numbers = _parse_price_numbers(lowered)
    sort = ""
    min_price: Decimal | None = None
    max_price: Decimal | None = None

    if _contains_any(lowered, ("cheapest", "lowest price", "least expensive", "best price", "ارخص", "أرخص")):
        sort = "asc"
    elif _contains_any(lowered, ("most expensive", "highest price", "priciest", "اغلى", "أغلى")):
        sort = "desc"

    if _contains_any(lowered, ("between", "from", "range", "بين")) and len(numbers) >= 2:
        min_price, max_price = sorted(numbers[:2])
    elif _contains_any(lowered, ("under", "below", "less than", "maximum", "max", "up to", "تحت", "اقل من", "أقل من")) and numbers:
        max_price = numbers[0]
    elif _contains_any(lowered, ("over", "above", "more than", "minimum", "min", "at least", "فوق", "اكتر من", "أكتر من", "اكثر من", "أكثر من")) and numbers:
        min_price = numbers[0]

    price_filter = PriceFilter(min_price=min_price, max_price=max_price, currency=currency, sort=sort)
    return price_filter if price_filter.active else None


def apply_price_filter(matches: Sequence[SearchMatch], price_filter: PriceFilter) -> list[SearchMatch]:
    filtered = [
        match
        for match in matches
        if _matches_price_filter(match.item, price_filter)
    ]
    if price_filter.sort and any(match.score for match in filtered):
        filtered = [match for match in filtered if match.score >= 25]
    if price_filter.sort == "asc":
        filtered.sort(key=lambda match: (_item_price(match.item) or Decimal("Infinity"), -match.score))
    elif price_filter.sort == "desc":
        filtered.sort(key=lambda match: (_item_price(match.item) or Decimal("-Infinity"), match.score), reverse=True)
    return filtered


def _normalize_queries(query: str | Sequence[str]) -> list[str]:
    raw_queries = [query] if isinstance(query, str) else list(query)
    queries: list[str] = []
    seen: set[str] = set()
    for raw_query in raw_queries:
        text = str(raw_query).strip()
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            queries.append(text)
    return queries


def _parse_currency(lowered: str) -> str:
    if "$" in lowered or "usd" in lowered or "dollar" in lowered or "دولار" in lowered:
        return "USD"
    if "lbp" in lowered or "lira" in lowered or "ليرة" in lowered:
        return "LBP"
    return ""


def _parse_price_numbers(lowered: str) -> list[Decimal]:
    numbers: list[Decimal] = []
    for match in PRICE_NUMBER_RE.finditer(lowered):
        try:
            numbers.append(Decimal(match.group(1).replace(",", ".")))
        except InvalidOperation:
            continue
    return numbers


def _contains_any(text: str, needles: Sequence[str]) -> bool:
    return any(needle in text for needle in needles)


def _matches_price_filter(item: CatalogItem, price_filter: PriceFilter) -> bool:
    price = _item_price(item)
    if price is None:
        return False
    if price_filter.currency and item.currency.upper() != price_filter.currency:
        return False
    if price_filter.min_price is not None and price < price_filter.min_price:
        return False
    if price_filter.max_price is not None and price > price_filter.max_price:
        return False
    return True


def _item_price(item: CatalogItem) -> Decimal | None:
    try:
        return Decimal(item.price)
    except InvalidOperation:
        return None


def _is_price_only_query(query: str) -> bool:
    meaningful_tokens = _meaningful_tokens(query)
    return bool(meaningful_tokens) and meaningful_tokens <= PRICE_FILTER_WORDS


def _matches_alias_group(normalized_message: str, message_tokens: set[str], aliases: tuple[str, ...]) -> bool:
    group_brand = _soft_drink_group_brand(aliases)
    if group_brand and _has_conflicting_soft_drink_brand(normalized_message, message_tokens, group_brand):
        return False
    if _mentions_abo_jumbo(message_tokens) and _is_bare_jumbo_group(aliases):
        return False

    for alias in aliases:
        normalized_alias = alias.lower().strip()
        alias_tokens = _meaningful_tokens(alias)
        if not alias_tokens:
            continue
        if normalized_message == normalized_alias:
            return True
        if len(alias_tokens) == 1 and next(iter(alias_tokens)) in message_tokens:
            return True
        if len(alias_tokens) > 1 and (normalized_alias in normalized_message or alias_tokens <= message_tokens):
            return True
    return False


def _mentions_abo_jumbo(message_tokens: set[str]) -> bool:
    return bool({"abo", "abu", "ابو", "أبو"} & message_tokens)


def _is_bare_jumbo_group(aliases: tuple[str, ...]) -> bool:
    has_jumbo = any(_meaningful_tokens(alias) & {"jambo", "jumbo", "جامبو", "جمبو"} for alias in aliases)
    has_abo = any(_meaningful_tokens(alias) & {"abo", "abu", "ابو", "أبو"} for alias in aliases)
    return has_jumbo and not has_abo


def _soft_drink_group_brand(aliases: tuple[str, ...]) -> str:
    for brand, brand_aliases in SOFT_DRINK_BRANDS.items():
        for alias in aliases:
            normalized_alias = alias.lower()
            alias_tokens = _meaningful_tokens(alias)
            for brand_alias in brand_aliases:
                if brand_alias in normalized_alias or _meaningful_tokens(brand_alias) <= alias_tokens:
                    return brand
    return ""


def _has_conflicting_soft_drink_brand(
    normalized_message: str,
    message_tokens: set[str],
    group_brand: str,
) -> bool:
    mentioned_brands = {
        brand
        for brand, brand_aliases in SOFT_DRINK_BRANDS.items()
        if any(
            brand_alias in normalized_message or _meaningful_tokens(brand_alias) <= message_tokens
            for brand_alias in brand_aliases
        )
    }
    return bool(mentioned_brands and group_brand not in mentioned_brands)


def _is_close(left: str, right: str) -> bool:
    if len(left) <= 2 or len(right) <= 2:
        return False
    if any(character.isdigit() for character in left + right):
        return left == right or left in right or right in left
    ratio = SequenceMatcher(None, left, right).ratio()
    return ratio >= 0.78 or left in right or right in left


def _matches_filter(item: CatalogItem, *, category: str, family: str) -> bool:
    if category and category.lower() not in item.category_code.lower():
        return False
    if family and family.lower() not in item.family_code.lower():
        return False
    return True


def _top_counts(counts: dict[str, int], limit: int = 10) -> list[dict[str, object]]:
    return [
        {"name": name, "count": count}
        for name, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))[:limit]
    ]


def _normalize_price(value: Any) -> str:
    text = str(value).strip()
    if not text:
        return ""
    try:
        return str(Decimal(text))
    except InvalidOperation:
        return text

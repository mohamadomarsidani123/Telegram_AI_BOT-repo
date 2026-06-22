# Telegram Gemini Ordering Bot Codebase Documentation

## 1. Project Overview

This project is a Python Telegram bot that lets users search a product catalog and build an order through natural conversation. The user can send text messages or Telegram voice notes. The bot uses Gemini to understand the user's intent, but it does not rely on Gemini to search the full catalog directly. Instead, the bot searches the local JSON catalog efficiently first, then sends only the best matching catalog candidates to Gemini.

The main use case is:

1. A customer asks what items are available.
2. The bot searches the catalog and answers through Gemini.
3. The customer asks to add one or more items.
4. The bot resolves items locally, adds confident matches, and asks for clarification when names are close but not exact.
5. The customer confirms the draft order.
6. The bot asks for the customer's full name.
7. The bot sends the final order details to a configured Telegram recipient chat.

The bot uses Telegram long polling. It does not use webhooks, WebSocket updates, a database, or an HTTP order endpoint in the current version.

## 2. Main Technologies

- Python 3.11+
- `python-telegram-bot` for Telegram Bot API integration
- `google-genai` for Gemini text and audio processing
- `pydantic` for strict Gemini response schemas
- `python-dotenv` for `.env` configuration
- `pytest` for tests

The project configuration is in `pyproject.toml`.

## 3. Runtime Configuration

Configuration is loaded from environment variables by `src/tgbot/config.py`.

Required variables:

- `TELEGRAM_BOT_TOKEN`: Telegram token from BotFather.
- `GEMINI_API_KEY`: Gemini API key.
- `CATALOG_JSON_PATH`: path to the local product catalog JSON file.
- `ORDER_RECIPIENT_PHONE_NUMBER`: business/order phone number shown in the routed order message.
- `ORDER_RECIPIENT_CHAT_ID`: Telegram chat id that receives completed orders.

Optional variables:

- `GEMINI_MODEL`: defaults to `gemini-2.5-flash`.
- `CATALOG_MAX_CANDIDATES`: number of catalog matches sent to Gemini, default `25`.
- `TELEGRAM_CONNECT_TIMEOUT`, `TELEGRAM_READ_TIMEOUT`, `TELEGRAM_WRITE_TIMEOUT`, `TELEGRAM_POOL_TIMEOUT`: network timeout tuning.
- `TELEGRAM_PROXY_URL`: optional proxy if Telegram is blocked on the network.

Important Telegram limitation:

Telegram bots cannot send messages directly to a raw phone number. The bot must send to a Telegram `chat_id`. The recipient can get this id by sending `/chatid` to the bot. That value goes into `ORDER_RECIPIENT_CHAT_ID`.

## 4. File Structure

### `src/tgbot/main.py`

This is the application entrypoint used by the `tgbot` command.

Responsibilities:

- Configure logging.
- Load settings from `.env`.
- Load the catalog from the configured JSON file.
- Create the Gemini client.
- Create the in-memory order store.
- Build the Telegram application.
- Start long polling.

It also catches Telegram startup network errors and prints cleaner messages.

### `src/tgbot/config.py`

This file defines the `Settings` dataclass and the `load_settings()` function.

It reads environment variables, validates required values, converts numeric fields, and exposes one typed settings object to the rest of the application.

### `src/tgbot/bot.py`

This is the main Telegram bot orchestration file.

Responsibilities:

- Register Telegram handlers:
  - `/start`
  - `/help`
  - `/chatid`
  - `/draft`
  - `/cancel`
  - text messages
  - voice messages
- Handle text order conversations.
- Download voice notes and pass them to Gemini for transcription.
- Search catalog candidates before calling Gemini.
- Execute Gemini action plans.
- Maintain the customer draft order.
- Ask for full name after confirmation.
- Send completed orders to `ORDER_RECIPIENT_CHAT_ID`.
- Record the last 10 chat exchanges.
- Handle unexpected errors cleanly.

The most important flow is:

```text
Telegram message
-> local catalog search
-> Gemini action plan
-> execute ordered actions
-> reply to customer
```

### `src/tgbot/catalog.py`

This file handles catalog loading, normalization, indexing, searching, and counts.

The catalog supports JSON in either of these shapes:

```json
[
  { "Id": "1327", "No.": "BBCARE-133", "Description": "..." }
]
```

or:

```json
{
  "items": [
    { "Id": "1327", "No.": "BBCARE-133", "Description": "..." }
  ]
}
```

Each raw item is converted to `CatalogItem`, with normalized fields:

- `id` from `Id`
- `sku` from `No.`
- `description` from `Description`
- `unit` from `Base Unit of Measure`
- `vendor_no` from `Vendor No.`
- `category_code` from `Item Category Code`
- `product_group_code` from `Product Group Code`
- `division_code` from `Division Code`
- `family_code` from `Item Family Code`
- `price` from `Sales Price`
- `currency` from `Currency Code`

#### Search Algorithm

The catalog search is local and efficient. It does not send the whole catalog to Gemini.

At startup, `Catalog` builds:

- lookup by id
- lookup by SKU
- field token indexes
- an inverted index from token to item ids
- a vocabulary for fuzzy matching
- catalog statistics such as category and family counts

Field weights:

- id: highest weight
- SKU: very high weight
- description: strong weight
- family/category/product group: medium weights
- division/vendor: lower weights

When searching:

1. The query is tokenized.
2. stop words like `the`, `and`, `please`, `want` are removed.
3. close/fuzzy token matches are added using `difflib.SequenceMatcher`.
4. candidate item ids are pulled from the inverted index.
5. each candidate receives a score based on exact terms, fuzzy terms, substring match, SKU prefix, and description similarity.
6. results are sorted by score.

Search returns `SearchMatch` objects containing:

- item
- score
- matched terms
- match type: `exact_id`, `exact_sku`, `direct`, `close`, or `browse`

This lets the bot show close results and avoid requiring exact names.

### `src/tgbot/gemini_client.py`

This file isolates all Gemini API usage.

Responsibilities:

- Send text prompts to Gemini.
- Send voice files to Gemini for transcription.
- Request structured JSON responses.
- Parse Gemini responses into Pydantic models.
- Convert Gemini API failures into user-friendly errors.

Gemini receives a compact context JSON with:

- the current user message
- catalog summary
- ranked catalog candidates from local search
- current draft order
- recent chat history, limited to the last 10 exchanges

Gemini does not receive the full catalog.

### `src/tgbot/schemas.py`

This file defines the structured output schema Gemini must return.

Main models:

- `IntentItem`: one item request, with item id, SKU, description, and quantity.
- `BotIntent`: one action such as search, add item, remove item, show draft, confirm, cancel, or ask clarification.
- `BotActionPlan`: an ordered list of `BotIntent` actions.

The bot supports several intents in one message. For example:

```text
show me bottles, add 2 diapers, and show my draft
```

Gemini should return an ordered action plan, and the bot executes each action in order.

### `src/tgbot/orders.py`

This file manages draft orders, chat history, full-name pending state, and item resolution.

Important classes:

- `DraftLine`: one item and quantity.
- `DraftOrder`: the current order draft.
- `OrderStore`: in-memory storage per Telegram chat.
- `ItemResolution`: result of resolving a requested item.

`OrderStore` keeps:

- draft orders by chat id
- the last 10 user/bot exchanges per chat
- which chats are waiting for a full name

There is no database. If the process restarts, draft orders and chat history are lost.

#### Price and Currency

The bot does not perform currency conversion.

Each line subtotal is:

```python
Decimal(item.price) * quantity
```

Totals are grouped by the item currency. If all items are USD, the bot shows one USD total. If items use different currencies, it shows separate totals by currency.

#### Item Resolution Confidence

When Gemini asks to add items, the bot does not blindly trust unclear names.

Resolution rules:

- exact id or exact SKU: resolved
- high search score: resolved
- weak close match: ambiguous
- no useful match: not found

If the user asks for three items and one is unclear:

- confident items are added
- ambiguous items are listed with suggestions
- missing items are listed as not found
- the updated draft is shown if anything was added

### `src/tgbot/telegram_check.py`

Provides the `tgbot-check-telegram` command.

It calls Telegram `getMe` using the current `.env` network settings. This helps diagnose:

- invalid token
- Telegram timeout
- proxy/network problems

### `src/tgbot/gemini_check.py`

Provides the `tgbot-check-gemini` command.

It sends a small prompt to Gemini to verify that the API key and model work.

It also explains the common `API_KEY_SERVICE_BLOCKED` error, which means the Google project/API key is blocked from calling `generativelanguage.googleapis.com`.

### `tests/`

The test suite verifies the important non-network logic:

- catalog normalization
- fuzzy catalog search
- result ranking
- count/stat behavior
- draft order totals
- order message formatting
- chat history limit of 10
- full-name pending state
- item resolution confidence
- multiple-action Gemini schema parsing

Current command:

```bash
.venv/bin/python -m pytest
```

## 5. Full Customer Flow

### Step 1: User sends text

Example:

```text
do you have wide neck feeding bottles and add 2 diapers
```

`bot.py` receives the message in `text_message()`.

### Step 2: Local search

The bot calls:

```python
self.catalog.search_matches(message, limit=self.max_candidates)
```

This returns the best local catalog candidates.

### Step 3: Gemini action plan

The bot sends Gemini:

- user message
- catalog candidates
- current draft
- catalog summary
- recent chat history

Gemini returns a `BotActionPlan`, for example:

```json
{
  "actions": [
    {
      "intent": "answer_catalog_question",
      "answer": "I found several wide neck feeding bottles."
    },
    {
      "intent": "add_items",
      "items": [
        {
          "item_id": "1327",
          "quantity": 2
        }
      ]
    },
    {
      "intent": "show_draft"
    }
  ]
}
```

### Step 4: Execute actions

The bot executes actions in order.

It stops early for:

- clarification
- cancellation
- confirmation

This prevents confusing behavior like continuing to modify the order after the user has confirmed it.

### Step 5: Confirmation

When the user confirms:

```text
confirm
```

The bot does not immediately route the order. It first asks:

```text
Please send your full name to finish the order.
```

### Step 6: Full name

The next text message is treated as the customer name.

### Step 7: Route order

The bot formats the order and sends it to `ORDER_RECIPIENT_CHAT_ID`.

The routed message includes:

- customer full name
- configured recipient phone number
- Telegram username or id
- item descriptions
- SKUs
- quantities
- unit prices
- estimated totals

## 6. Voice Note Flow

Voice notes use the same order logic after transcription.

Flow:

1. Telegram voice note is received.
2. The bot downloads the `.ogg` voice file to a temporary directory.
3. Gemini transcribes the audio.
4. The transcript is searched against the catalog.
5. Gemini interprets the transcript into an action plan.
6. The bot executes the actions exactly like a text message.

If the bot is waiting for the user's full name, it asks the user to send the name as text instead of voice.

## 7. Why Local Search Is Used Before Gemini

The catalog can be very large. Sending the full JSON list to Gemini on every message would be inefficient, expensive, and less reliable.

The implemented design is better because:

- local search is fast
- only relevant candidate items are sent to Gemini
- the bot controls exact ids, SKUs, prices, and totals
- Gemini is used for language understanding, not as a database
- close matches and typo tolerance are handled locally

This separation is important:

- Python code handles deterministic data operations.
- Gemini handles natural-language interpretation.

## 8. Important Commands

Install:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run bot:

```bash
tgbot
```

Check Telegram:

```bash
tgbot-check-telegram
```

Check Gemini:

```bash
tgbot-check-gemini
```

Run tests:

```bash
.venv/bin/python -m pytest
```

Get recipient chat id:

```text
/chatid
```

The recipient sends this command to the bot, then copies the returned id into `.env`.

## 9. Example `.env`

```env
TELEGRAM_BOT_TOKEN=123456:telegram-token
GEMINI_API_KEY=your-gemini-key
CATALOG_JSON_PATH=./catalog.json
ORDER_RECIPIENT_PHONE_NUMBER=+96100000000
ORDER_RECIPIENT_CHAT_ID=123456789
GEMINI_MODEL=gemini-2.5-flash
CATALOG_MAX_CANDIDATES=25
```

## 10. Limitations

- Draft orders are stored in memory only. They disappear after process restart.
- No user authentication is implemented.
- The bot cannot send to a raw phone number; it sends to Telegram chat ids.
- Currency conversion is not implemented.
- Availability/stock is only as accurate as the catalog JSON.
- Gemini API must be enabled and unrestricted for the configured key.
- The bot uses polling, not webhook deployment.

## 11. Likely Defense Questions and Answers

### Why did you not send the full catalog to Gemini?

Because the catalog can be very large. Sending the full JSON would waste tokens, slow responses, and increase cost. The code searches locally first and sends only relevant candidates to Gemini.

### What is Gemini responsible for?

Gemini understands the user's natural language and returns structured actions. It decides whether the user is asking a question, adding items, removing items, confirming, cancelling, or asking something ambiguous.

### What is Python responsible for?

Python owns deterministic operations: loading the catalog, searching, resolving item ids, calculating totals, storing drafts, and routing the final order.

### How does the bot handle spelling mistakes?

The catalog search tokenizes the query, expands terms with fuzzy matching using `SequenceMatcher`, scores candidates, and returns close results. Weak matches are not automatically added; the bot asks for clarification.

### What happens if the user asks for multiple things in one message?

Gemini returns a `BotActionPlan` containing multiple ordered actions. The bot executes them one by one and returns a combined response.

### What happens if one item is found and another is not?

The found item is added. Ambiguous items are shown with suggestions. Missing items are listed separately. The updated draft is shown if any item was added.

### How are totals calculated?

The bot multiplies `Sales Price` by quantity using `Decimal`, then groups totals by `Currency Code`. There is no currency conversion.

### How does voice ordering work?

The bot downloads the Telegram voice note, sends it to Gemini for transcription, then processes the transcript like a normal text message.

### Why is full name requested after confirmation?

The name is needed in the final routed order message so the order recipient knows who placed the order.

### Why do we need `ORDER_RECIPIENT_CHAT_ID` if we already have a phone number?

Telegram bots cannot message raw phone numbers. They can message only chat ids where the bot has access. The phone number is included as business/order metadata, but Telegram delivery requires chat id.

### What happens on restart?

The bot reloads the catalog, but active draft orders and chat history are lost because they are stored in memory.

### How is the last 10 chats requirement implemented?

`OrderStore` stores a `deque(maxlen=10)` per chat. When a new exchange is added, old exchanges automatically drop off.

## 12. Suggested Future Improvements

- Store drafts and chat history in SQLite or Postgres.
- Add inline Telegram buttons for confirm/edit/cancel.
- Add stock availability if the catalog includes quantity.
- Add admin commands to reload catalog without restarting.
- Add currency conversion if a reliable exchange-rate source is provided.
- Add webhook deployment for production hosting.
- Add audit logs for submitted orders.
- Add direct integration with WhatsApp/SMS if true phone-number delivery is required.

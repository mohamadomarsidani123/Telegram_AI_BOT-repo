# 🤖 Telegram AI Order Bot

An intelligent Telegram chatbot built with **Python** and **Google Gemini AI** that helps users browse products, understand natural language requests, and submit orders directly through Telegram.

This project demonstrates AI integration, Telegram bot development, clean software architecture, and conversational user experiences.

---

## 🚀 Features

* 💬 Natural language conversations
* 🤖 Google Gemini AI integration
* 🎤 Voice message support
* 📦 Product catalog search
* 🛒 Interactive order creation
* ✅ Order confirmation workflow
* 👤 Customer information collection
* 📩 Automatic order forwarding via Telegram
* ⚙️ Environment-based configuration
* 🧩 Modular Python architecture

---

## 📸 Screenshots

### Menu Screen

![Welcome Screen](https://github.com/mohamadomarsidani123/Telegram_AI_BOT-repo/blob/4a56c55d633913f4fc09f0e16a79146ca536bf40/WhatsApp%20Image%202026-06-23%20at%204.31.38%20AM.jpeg)

### Product Search

![Product Search](https://github.com/mohamadomarsidani123/Telegram_AI_BOT-repo/blob/858e40eb265a562599ee9f0b0b06914576707970/WhatsApp%20Image%202026-06-23%20at%204.39.13%20AM.jpeg)

### AI Response

![AI Response](https://github.com/mohamadomarsidani123/Telegram_AI_BOT-repo/blob/da8fe0ed1558df2b5c0be9da1f3679d9d2778297/WhatsApp%20Image%202026-06-22%20at%2011.19.30%20PM.jpeg)

### Order Confirmation

![Order Confirmation](https://github.com/mohamadomarsidani123/Telegram_AI_BOT-repo/blob/3ec70541a30e7e2bd56c88ae9cb6775c1c6758b6/WhatsApp%20Image%202026-06-22%20at%2011.19.29%20PM.jpeg)

### Remove Product

![Remove Product](https://github.com/mohamadomarsidani123/Telegram_AI_BOT-repo/blob/da8fe0ed1558df2b5c0be9da1f3679d9d2778297/WhatsApp%20Image%202026-06-22%20at%2011.19.32%20PM.jpeg)



---

## 🛠️ Tech Stack

* Python 3.11+
* python-telegram-bot
* Google Gemini API
* Pydantic
* JSON
* Poetry
* Git
* GitHub

---

## 📂 Project Structure

```text
.
├── src/
│   └── tgbot/
│       ├── main.py
│       ├── config.py
│       ├── catalog.py
│       ├── orders.py
│       ├── schemas.py
│       ├── gemini_client.py
│       ├── gemini_check.py
│       ├── telegram_check.py
│       └── screenshots/
├── README.md
├── pyproject.toml
└── .env.example
```

---

## ⚡ Installation

### Clone the Repository

```bash
git clone https://github.com/mohamadomarsidani123/Telegram_AI_BOT-repo.git
cd Telegram_AI_BOT-repo
```

### Create a Virtual Environment

#### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

#### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Install Dependencies

```bash
pip install -e .
```

---

## 🔑 Environment Variables

Create a `.env` file:

```env
BOT_TOKEN=your_telegram_bot_token
GEMINI_API_KEY=your_gemini_api_key
ADMIN_CHAT_ID=your_chat_id
```

---

## ▶️ Run the Bot

```bash
python -m src.tgbot.main
```

or

```bash
tgbot
```

---

## 💡 How It Works

1. User sends a text or voice message.
2. Voice messages are converted to text.
3. Gemini AI understands the user's request.
4. The bot searches the product catalog.
5. The user confirms the order.
6. Customer details are collected.
7. The order is forwarded to the administrator through Telegram.

---

## 📚 Skills Demonstrated

* Python Development
* Object-Oriented Programming
* AI Integration (Google Gemini)
* Telegram Bot Development
* JSON Data Processing
* Environment Configuration
* Software Architecture
* Git & GitHub
* API Integration

---

## 🔒 Security

Sensitive information such as API keys, chat IDs, and bot tokens are stored in environment variables and are **never committed** to the repository.

---

## 🧪 Future Improvements

* Docker support
* PostgreSQL integration
* Order history
* Admin dashboard
* Payment processing
* Multi-language support
* Cloud deployment (AWS / Azure)
* User accounts and authentication

---

## 👨‍💻 Author

**Mohamad Omar Sidani**

Software Engineer

GitHub: https://github.com/mohamadomarsidani123

---

## ⭐ Support

If you found this project useful, consider giving it a star on GitHub.

---

## 📄 License

This project is licensed under the MIT License.

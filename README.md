# 🤖 Telegram AI Order Bot

An intelligent Telegram chatbot built with **Python** that helps users browse a product catalog, understand natural language requests using **Google Gemini AI**, and submit orders through Telegram.

This project demonstrates AI integration, API development, clean software architecture, and conversational user interaction.

---

## 🚀 Features

- 💬 Natural language conversations
- 🤖 Google Gemini AI integration
- 🎤 Voice message support
- 📦 Product catalog search
- 🛒 Interactive order creation
- ✅ Order confirmation workflow
- 👤 Customer information collection
- 📩 Automatic order forwarding via Telegram
- ⚙️ Environment-based configuration
- 🧩 Modular Python architecture

---

## 🛠️ Tech Stack

- Python 3.11+
- python-telegram-bot
- Google Gemini API
- JSON
- Pydantic
- Poetry
- Git
- GitHub

---

## 📂 Project Structure

```
.
├── src/
│   └── tgbot/
│       ├── handlers/
│       ├── services/
│       ├── models/
│       ├── utils/
│       └── main.py
├── tests/
├── pyproject.toml
├── .env.example
├── README.md
└── CODEBASE_DOCUMENTATION.md
```

---

## ⚡ Installation

### Clone the repository

```bash
git clone https://github.com/mohamadomarsidani123/Telegram_AI_BOT-repo.git
```

Enter the project

```bash
cd Telegram_AI_BOT-repo
```

Create a virtual environment

### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies

```bash
pip install -e .
```

---

## 🔑 Environment Variables

Create a `.env` file using the provided template.

Example:

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

- Python Development
- Object-Oriented Programming
- REST API Integration
- AI Integration (Google Gemini)
- Telegram Bot Development
- JSON Data Processing
- Environment Configuration
- Git & GitHub
- Clean Project Architecture

---

## 🔒 Security

Sensitive information such as API keys and bot tokens are stored in environment variables and are **never committed** to the repository.

---

## 🧪 Future Improvements

- Docker support
- PostgreSQL database
- User authentication
- Order history
- Admin dashboard
- Payment integration
- Multi-language support
- Deployment on AWS or Azure

---

## 👨‍💻 Author

**Mohamad Omar Sidani**

Fresh Graduate Software Engineer

GitHub:
https://github.com/mohamadomarsidani123

---

## 📄 License

This project is licensed under the MIT License.

---

⭐ If you found this project useful, consider giving it a star!

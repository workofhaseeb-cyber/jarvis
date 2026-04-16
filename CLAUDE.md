# Jarvis — Claude Code Guide

This file provides essential context for Claude Code when working in this repository.

## Project Overview

Jarvis is a local AI personal assistant powered by Claude (Anthropic). It runs as a Python FastAPI server with a desktop overlay and a web frontend. It integrates with email, calendar, browser automation, memory, task planning, and now Telegram.

## Repository Layout

| File / Folder | Purpose |
|---|---|
| `server.py` | Main FastAPI server — the central brain (~119 KB) |
| `memory.py` | Persistent memory store and retrieval |
| `planner.py` | Multi-step task planning and execution |
| `actions.py` | Executable actions (file ops, system commands, etc.) |
| `mail_access.py` | Gmail / IMAP email integration |
| `calendar_access.py` | Google Calendar integration |
| `browser.py` | Playwright-based browser automation |
| `evolution.py` | Self-improvement / learning feedback loop |
| `conversation.py` | Conversation history and context management |
| `screen.py` | Screen capture and vision utilities |
| `monitor.py` | System monitoring (CPU, RAM, etc.) |
| `notes_access.py` | Notes creation and retrieval |
| `work_mode.py` | Focus / work-mode session management |
| `learning.py` | Learning and knowledge-base updates |
| `tracking.py` | Activity and habit tracking |
| `suggestions.py` | Proactive suggestion engine |
| `ab_testing.py` | A/B testing framework for prompts |
| `dispatch_registry.py` | Central action dispatch registry |
| `qa.py` | QA and self-testing utilities |
| `templates.py` | Prompt and response templates |
| `telegram_integration.py` | **NEW** — Telegram Bot integration (send/receive) |
| `frontend/` | Web UI (HTML/CSS/JS) |
| `desktop-overlay/` | Floating desktop overlay app |
| `data/` | Persistent data storage |
| `helpers/` | Shared utility helpers |
| `templates/` | Jinja2 / text templates |
| `tests/` | Test suite |

## Environment Variables (`.env`)

Copy `.env.example` to `.env` and fill in your keys:

```
ANTHROPIC_API_KEY=       # Required — your Claude API key
TELEGRAM_BOT_TOKEN=     # Optional — get from @BotFather on Telegram
TELEGRAM_CHAT_ID=       # Optional — your personal Telegram chat ID
```

See `.env.example` for the full list.

## Telegram Integration

The new `telegram_integration.py` module lets Jarvis:
- **Send notifications** to your Telegram chat from anywhere in the codebase
- **Receive messages** via long-polling and route them through Jarvis's brain
- **Send files/documents** back to Telegram

### Quick usage

```python
# Send a one-off notification
from telegram_integration import send_notification
send_notification("Task completed!")

# Full instance with message routing
from telegram_integration import TelegramIntegration

def handle(text: str) -> str:
    # plug into your Jarvis pipeline here
    return f"Jarvis received: {text}"

tg = TelegramIntegration(on_message=handle)
tg.start_polling()   # runs in background thread
```

### Setup steps
1. Message **@BotFather** on Telegram → `/newbot` → copy the token.
2. Message **@userinfobot** on Telegram → copy your numeric chat ID.
3. Add both to `.env`.
4. Run `python telegram_integration.py` to verify the connection.

## Development Guidelines

- **Python 3.10+** required.
- Run the server: `uvicorn server:app --reload --port 8000`
- Install dependencies: `pip install -r requirements.txt`
- All new integrations should follow the pattern in `telegram_integration.py`:
  - Module-level constants from `os.getenv()`
  - A class with a clear public API
  - A module-level convenience instance + helper functions
  - Guard against missing credentials with clear log warnings
- Write tests in `tests/` for any new module.
- Use `logger = logging.getLogger(__name__)` — do **not** use `print()` for runtime output.

## Adding New Features

1. Create a new `feature_name.py` module.
2. Register any new actions in `dispatch_registry.py`.
3. Import and wire up in `server.py`.
4. Update this `CLAUDE.md` table above.
5. Add any new env vars to `.env.example`.

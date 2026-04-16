"""
telegram_integration.py

Telegram Bot integration for Jarvis.
Allows Jarvis to send and receive messages via a Telegram Bot.

Setup:
  1. Create a bot via @BotFather on Telegram -> get TELEGRAM_BOT_TOKEN
  2. Get your chat ID by messaging @userinfobot -> set TELEGRAM_CHAT_ID
  3. Add both to your .env file

Features:
  - Send text messages to a Telegram chat
  - Send files/documents
  - Poll for incoming messages and route them to Jarvis
  - Supports reply keyboard for quick actions
"""

import os
import logging
import asyncio
import threading
from typing import Optional, Callable

try:
    import requests
except ImportError:
    requests = None

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_API_BASE = "https://api.telegram.org/bot"


class TelegramIntegration:
    """
    Handles all Telegram Bot API interactions for Jarvis.
    """

    def __init__(
        self,
        token: str = TELEGRAM_BOT_TOKEN,
        chat_id: str = TELEGRAM_CHAT_ID,
        on_message: Optional[Callable[[str], str]] = None,
    ):
        self.token = token
        self.chat_id = chat_id
        self.on_message = on_message  # callback: receives user text, returns reply text
        self.api_url = f"{TELEGRAM_API_BASE}{self.token}"
        self._last_update_id: int = 0
        self._polling = False
        self._poll_thread: Optional[threading.Thread] = None

        if not self.token:
            logger.warning(
                "TELEGRAM_BOT_TOKEN is not set. Telegram integration will be disabled."
            )
        if not self.chat_id:
            logger.warning(
                "TELEGRAM_CHAT_ID is not set. Messages will not be sent."
            )

    # ------------------------------------------------------------------ #
    #  Core API helpers
    # ------------------------------------------------------------------ #

    def _get(self, method: str, params: dict = None) -> Optional[dict]:
        """Make a GET request to the Telegram Bot API."""
        if not requests:
            logger.error("'requests' library not installed.")
            return None
        try:
            resp = requests.get(
                f"{self.api_url}/{method}", params=params or {}, timeout=10
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Telegram GET {method} error: {e}")
            return None

    def _post(self, method: str, data: dict = None, files=None) -> Optional[dict]:
        """Make a POST request to the Telegram Bot API."""
        if not requests:
            logger.error("'requests' library not installed.")
            return None
        try:
            if files:
                resp = requests.post(
                    f"{self.api_url}/{method}", data=data or {}, files=files, timeout=30
                )
            else:
                resp = requests.post(
                    f"{self.api_url}/{method}", json=data or {}, timeout=10
                )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Telegram POST {method} error: {e}")
            return None

    # ------------------------------------------------------------------ #
    #  Sending
    # ------------------------------------------------------------------ #

    def send_message(self, text: str, chat_id: str = None, parse_mode: str = "HTML") -> bool:
        """
        Send a text message to the configured Telegram chat.

        Args:
            text:       Message text (supports HTML or Markdown formatting).
            chat_id:    Override the default chat_id if needed.
            parse_mode: 'HTML' or 'Markdown'. Defaults to 'HTML'.

        Returns:
            True if sent successfully, False otherwise.
        """
        if not self.token:
            logger.error("Cannot send message: TELEGRAM_BOT_TOKEN not set.")
            return False
        target = chat_id or self.chat_id
        if not target:
            logger.error("Cannot send message: TELEGRAM_CHAT_ID not set.")
            return False

        payload = {"chat_id": target, "text": text, "parse_mode": parse_mode}
        result = self._post("sendMessage", payload)
        if result and result.get("ok"):
            logger.info(f"Telegram message sent to {target}.")
            return True
        logger.error(f"Failed to send Telegram message: {result}")
        return False

    def send_document(self, file_path: str, caption: str = "", chat_id: str = None) -> bool:
        """
        Send a file/document to the Telegram chat.

        Args:
            file_path: Local path to the file.
            caption:   Optional caption text.
            chat_id:   Override the default chat_id if needed.

        Returns:
            True if sent successfully, False otherwise.
        """
        if not self.token:
            logger.error("Cannot send document: TELEGRAM_BOT_TOKEN not set.")
            return False
        target = chat_id or self.chat_id
        if not target:
            logger.error("Cannot send document: TELEGRAM_CHAT_ID not set.")
            return False
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return False

        with open(file_path, "rb") as f:
            result = self._post(
                "sendDocument",
                data={"chat_id": target, "caption": caption},
                files={"document": f},
            )
        if result and result.get("ok"):
            logger.info(f"Telegram document sent: {file_path}")
            return True
        logger.error(f"Failed to send document: {result}")
        return False

    def send_typing(self, chat_id: str = None) -> None:
        """Send a 'typing...' action indicator to the chat."""
        target = chat_id or self.chat_id
        self._post("sendChatAction", {"chat_id": target, "action": "typing"})

    # ------------------------------------------------------------------ #
    #  Receiving / Polling
    # ------------------------------------------------------------------ #

    def get_updates(self, offset: int = 0, timeout: int = 20) -> list:
        """
        Long-poll the Telegram API for new updates.

        Args:
            offset:  Update ID to start from (avoids reprocessing old messages).
            timeout: Long-polling timeout in seconds.

        Returns:
            List of update dicts.
        """
        params = {"offset": offset, "timeout": timeout, "allowed_updates": ["message"]}
        result = self._get("getUpdates", params)
        if result and result.get("ok"):
            return result.get("result", [])
        return []

    def _poll_loop(self) -> None:
        """Internal polling loop — runs in a background thread."""
        logger.info("Telegram polling started.")
        while self._polling:
            try:
                updates = self.get_updates(offset=self._last_update_id + 1)
                for update in updates:
                    self._last_update_id = update["update_id"]
                    self._handle_update(update)
            except Exception as e:
                logger.error(f"Polling error: {e}")
                import time; time.sleep(2)
        logger.info("Telegram polling stopped.")

    def _handle_update(self, update: dict) -> None:
        """Process a single incoming Telegram update."""
        message = update.get("message", {})
        text = message.get("text", "").strip()
        sender_id = str(message.get("chat", {}).get("id", ""))
        username = message.get("chat", {}).get("username", "unknown")

        if not text:
            return

        logger.info(f"Telegram message from @{username} ({sender_id}): {text}")

        # Only respond to the authorised chat ID (security gate)
        if self.chat_id and sender_id != self.chat_id:
            logger.warning(f"Ignoring message from unauthorised chat: {sender_id}")
            return

        # Route through Jarvis if a callback is registered
        if self.on_message:
            try:
                self.send_typing(sender_id)
                reply = self.on_message(text)
                if reply:
                    self.send_message(reply, chat_id=sender_id)
            except Exception as e:
                logger.error(f"Error processing message via on_message callback: {e}")
                self.send_message(
                    "\u26a0\ufe0f Jarvis encountered an error processing your request.",
                    chat_id=sender_id,
                )

    def start_polling(self) -> None:
        """
        Start background polling for incoming Telegram messages.
        Runs in a daemon thread so it stops when the main process exits.
        """
        if not self.token:
            logger.error("Cannot start polling: TELEGRAM_BOT_TOKEN not set.")
            return
        if self._polling:
            logger.warning("Polling already running.")
            return
        self._polling = True
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

    def stop_polling(self) -> None:
        """Stop the background polling thread."""
        self._polling = False
        if self._poll_thread:
            self._poll_thread.join(timeout=5)
            self._poll_thread = None

    # ------------------------------------------------------------------ #
    #  Utility
    # ------------------------------------------------------------------ #

    def get_me(self) -> Optional[dict]:
        """Return basic info about the bot (useful for verifying the token)."""
        result = self._get("getMe")
        if result and result.get("ok"):
            return result["result"]
        return None

    def is_connected(self) -> bool:
        """Return True if the bot token is valid and the API is reachable."""
        return self.get_me() is not None


# ------------------------------------------------------------------ #
#  Module-level convenience instance
# ------------------------------------------------------------------ #

_default_instance: Optional[TelegramIntegration] = None


def get_telegram() -> TelegramIntegration:
    """Return (and lazily create) the default TelegramIntegration instance."""
    global _default_instance
    if _default_instance is None:
        _default_instance = TelegramIntegration()
    return _default_instance


def send_notification(text: str) -> bool:
    """
    Convenience function — send a quick notification from anywhere in Jarvis.

    Example:
        from telegram_integration import send_notification
        send_notification("Task completed: morning briefing sent.")
    """
    return get_telegram().send_message(text)


if __name__ == "__main__":
    # Quick smoke-test: python telegram_integration.py
    logging.basicConfig(level=logging.INFO)
    tg = TelegramIntegration()
    if tg.is_connected():
        info = tg.get_me()
        print(f"Connected! Bot: @{info.get('username')} ({info.get('first_name')})")
        tg.send_message("\U0001f916 Jarvis Telegram integration is live!")
    else:
        print("Could not connect. Check TELEGRAM_BOT_TOKEN in your .env file.")

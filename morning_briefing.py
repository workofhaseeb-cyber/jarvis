"""
Morning Briefing — Weather, news, tasks, and calendar summary.
Triggered by voice command: "Good morning", "morning briefing", "wake up"

Setup:
    pip install httpx
    NEWSAPI_KEY=your_key_here  (free at https://newsapi.org)
"""

import logging
import os
from datetime import datetime
from typing import Optional
import httpx

log = logging.getLogger("jarvis.morning_briefing")

NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")
NEWS_COUNTRY = os.getenv("NEWS_COUNTRY", "us")
NEWS_CATEGORY = os.getenv("NEWS_CATEGORY", "technology")


async def fetch_weather_briefing() -> str:
    """Fetch current weather from wttr.in for briefing."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as http:
            resp = await http.get(
                "https://wttr.in/?format=%l:+%C,+%t,+feels+like+%f",
                headers={"User-Agent": "curl"}
            )
            if resp.status_code == 200:
                return resp.text.strip()
    except Exception as e:
        log.warning(f"Weather fetch failed: {e}")
    return "Weather unavailable"


async def fetch_top_news(count: int = 5) -> list[dict]:
    """Fetch top headlines from NewsAPI."""
    if not NEWSAPI_KEY:
        log.warning("NEWSAPI_KEY not set. Add it to .env for news briefing.")
        return []
    try:
        async with httpx.AsyncClient(timeout=8.0) as http:
            resp = await http.get(
                "https://newsapi.org/v2/top-headlines",
                params={
                    "country": NEWS_COUNTRY,
                    "category": NEWS_CATEGORY,
                    "pageSize": count,
                    "apiKey": NEWSAPI_KEY,
                }
            )
            if resp.status_code == 200:
                data = resp.json()
                articles = data.get("articles", [])
                return [
                    {
                        "title": a.get("title", ""),
                        "source": a.get("source", {}).get("name", ""),
                        "description": a.get("description", ""),
                    }
                    for a in articles
                    if a.get("title") and "[Removed]" not in a.get("title", "")
                ]
    except Exception as e:
        log.error(f"News fetch failed: {e}")
    return []


async def generate_morning_briefing(
    calendar_events: list[dict] = None,
    open_tasks: list[dict] = None,
    unread_email_count: int = 0,
) -> str:
    """
    Generate a full morning briefing text for JARVIS to speak.
    Combines: time greeting + weather + news + calendar + tasks + email
    """
    now = datetime.now()
    hour = now.hour
    greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"
    date_str = now.strftime("%A, %B %d")

    parts = [f"{greeting}, sir. It's {date_str}."]

    # Weather
    weather = await fetch_weather_briefing()
    if weather and weather != "Weather unavailable":
        parts.append(f"Currently {weather}.")

    # Calendar
    if calendar_events:
        count = len(calendar_events)
        parts.append(f"You have {count} event{'s' if count != 1 else ''} on your calendar today.")
        for e in calendar_events[:3]:
            title = e.get("title", e.get("summary", "Meeting"))
            start = e.get("start", "")
            parts.append(f"{start} — {title}.")
        if count > 3:
            parts.append(f"And {count - 3} more event{'s' if count - 3 != 1 else ''}.")
    else:
        parts.append("Your calendar is clear today.")

    # Tasks
    if open_tasks:
        high = [t for t in open_tasks if t.get("priority") == "high"]
        parts.append(
            f"You have {len(open_tasks)} open task{'s' if len(open_tasks) != 1 else ''}"
            + (f", {len(high)} high priority" if high else "") + "."
        )
        for t in high[:2]:
            parts.append(f"Priority: {t['title']}.")

    # Email
    if unread_email_count > 0:
        parts.append(
            f"You have {unread_email_count} unread email{'s' if unread_email_count != 1 else ''} waiting."
        )

    # News
    news = await fetch_top_news(count=3)
    if news:
        parts.append("Here are your top headlines.")
        for i, article in enumerate(news, 1):
            parts.append(f"{i}. {article['title']}")

    parts.append("How shall we begin, sir?")
    return " ".join(parts)


BRIEFING_TRIGGERS = [
    "good morning",
    "morning briefing",
    "morning brief",
    "wake up",
    "start my day",
    "daily briefing",
    "what's happening today",
    "what do i have today",
    "run the briefing",
]


def is_briefing_request(text: str) -> bool:
    """Check if user's text is requesting a morning briefing."""
    text_lower = text.lower()
    return any(trigger in text_lower for trigger in BRIEFING_TRIGGERS)

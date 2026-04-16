"""
Google Calendar Sync — Cross-platform calendar integration via Google Calendar API.
Works on Windows, Linux, and macOS.

Setup:
    1. Go to https://console.cloud.google.com/
    2. Create a project → Enable Google Calendar API
    3. Create OAuth 2.0 credentials → Download as credentials.json
    4. Place credentials.json in the jarvis project root
    5. pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client

Required .env vars:
    GOOGLE_CALENDAR_CREDENTIALS=credentials.json  (path to OAuth credentials file)
    GOOGLE_CALENDAR_TOKEN=token.json              (auto-created on first auth)
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

log = logging.getLogger("jarvis.google_calendar")

CREDENTIALS_FILE = os.getenv("GOOGLE_CALENDAR_CREDENTIALS", "credentials.json")
TOKEN_FILE = os.getenv("GOOGLE_CALENDAR_TOKEN", "token.json")
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

_service = None


def _get_service():
    """Authenticate and return Google Calendar service. Caches the service."""
    global _service
    if _service:
        return _service

    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        log.error(
            "Google API packages not installed. Run: "
            "pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client"
        )
        return None

    creds = None
    token_path = Path(TOKEN_FILE)
    creds_path = Path(CREDENTIALS_FILE)

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                log.warning(f"Token refresh failed: {e}")
                creds = None

        if not creds:
            if not creds_path.exists():
                log.error(
                    f"Google Calendar credentials file not found: {CREDENTIALS_FILE}. "
                    "Download it from Google Cloud Console."
                )
                return None
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
            creds = flow.run_local_server(port=0)

        token_path.write_text(creds.to_json())

    _service = build("calendar", "v3", credentials=creds)
    log.info("Google Calendar service initialized")
    return _service


def get_todays_events_google() -> list[dict]:
    """Get today's events from Google Calendar."""
    service = _get_service()
    if not service:
        return []

    now = datetime.now(timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)

    try:
        result = service.events().list(
            calendarId="primary",
            timeMin=start_of_day.isoformat(),
            timeMax=end_of_day.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        return _parse_events(result.get("items", []))
    except Exception as e:
        log.error(f"Failed to fetch today's Google Calendar events: {e}")
        return []


def get_upcoming_events_google(days: int = 7) -> list[dict]:
    """Get upcoming events from Google Calendar for the next N days."""
    service = _get_service()
    if not service:
        return []

    now = datetime.now(timezone.utc)
    end = now + timedelta(days=days)

    try:
        result = service.events().list(
            calendarId="primary",
            timeMin=now.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=20,
        ).execute()

        return _parse_events(result.get("items", []))
    except Exception as e:
        log.error(f"Failed to fetch upcoming Google Calendar events: {e}")
        return []


def get_next_event_google() -> Optional[dict]:
    """Get the very next upcoming event."""
    events = get_upcoming_events_google(days=1)
    return events[0] if events else None


def _parse_events(raw_events: list) -> list[dict]:
    """Parse raw Google Calendar event objects into clean dicts."""
    events = []
    for e in raw_events:
        start = e.get("start", {})
        end = e.get("end", {})

        # Handle all-day events vs timed events
        start_str = start.get("dateTime", start.get("date", ""))
        end_str = end.get("dateTime", end.get("date", ""))

        # Format time for display
        display_time = ""
        if "dateTime" in start:
            try:
                dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                display_time = dt.strftime("%I:%M %p")
            except Exception:
                display_time = start_str
        else:
            display_time = "All day"

        events.append({
            "id": e.get("id", ""),
            "title": e.get("summary", "(No title)"),
            "start": display_time,
            "start_raw": start_str,
            "end_raw": end_str,
            "location": e.get("location", ""),
            "description": e.get("description", ""),
            "attendees": [
                a.get("email", "") for a in e.get("attendees", [])
            ],
            "meet_link": e.get("hangoutLink", ""),
            "all_day": "dateTime" not in start,
        })

    return events


def format_events_for_context_google(events: list[dict]) -> str:
    """Format Google Calendar events for injection into the JARVIS system prompt."""
    if not events:
        return "No events found in Google Calendar."

    lines = []
    for e in events:
        line = f"- {e['start']}: {e['title']}"
        if e.get("location"):
            line += f" @ {e['location']}"
        if e.get("meet_link"):
            line += f" [Google Meet: {e['meet_link']}]"
        lines.append(line)

    return "\n".join(lines)


def is_google_calendar_available() -> bool:
    """Check if Google Calendar is configured and reachable."""
    return _get_service() is not None


if __name__ == "__main__":
    print("Testing Google Calendar sync...")
    events = get_todays_events_google()
    if events:
        print(f"Found {len(events)} events today:")
        for e in events:
            print(f"  {e['start']}: {e['title']}")
    else:
        print("No events today (or not configured).")

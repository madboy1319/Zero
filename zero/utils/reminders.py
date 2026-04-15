"""Reminder storage and management."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

_REMINDERS_FILE = Path.home() / ".zero" / "reminders.json"


def _load() -> list[dict[str, Any]]:
    try:
        if _REMINDERS_FILE.exists():
            return json.loads(_REMINDERS_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Failed to load reminders.json: {}", e)
    return []


def _save(reminders: list[dict[str, Any]]) -> None:
    try:
        _REMINDERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _REMINDERS_FILE.write_text(
            json.dumps(reminders, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except Exception as e:
        logger.error("Failed to save reminders.json: {}", e)


def add_reminder(title: str, due_iso: str, note: str = "", channel: str = "", chat_id: str = "") -> dict[str, Any]:
    """Add a reminder and return it."""
    reminders = _load()
    reminder = {
        "id": str(uuid.uuid4())[:8],
        "title": title,
        "due_iso": due_iso,
        "note": note,
        "done": False,
        "created_at": datetime.now().isoformat(),
    }
    # Store delivery destination so the bridge knows where to send the notification
    if channel:
        reminder["channel"] = channel
    if chat_id:
        reminder["chat_id"] = chat_id
    reminders.append(reminder)
    _save(reminders)
    logger.info("Reminder added: '{}' due {} → {}:{}", title, due_iso, channel, chat_id)
    return reminder


def list_reminders(include_done: bool = False) -> list[dict[str, Any]]:
    """Return all (or only pending) reminders sorted by due date."""
    reminders = _load()
    if not include_done:
        reminders = [r for r in reminders if not r.get("done")]
    reminders.sort(key=lambda r: r.get("due_iso", ""))
    return reminders


def mark_done(reminder_id: str) -> bool:
    """Mark a reminder as done. Returns True if found."""
    reminders = _load()
    for r in reminders:
        if r["id"] == reminder_id:
            r["done"] = True
            _save(reminders)
            return True
    return False


def delete_reminder(reminder_id: str) -> bool:
    """Delete a reminder by id. Returns True if found."""
    reminders = _load()
    before = len(reminders)
    reminders = [r for r in reminders if r["id"] != reminder_id]
    if len(reminders) < before:
        _save(reminders)
        return True
    return False


def get_todays_reminders() -> list[dict[str, Any]]:
    """Return reminders due today (by date portion of due_iso)."""
    today = datetime.now().date().isoformat()
    return [
        r for r in list_reminders()
        if r.get("due_iso", "").startswith(today)
    ]

"""Notes storage and management."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

_NOTES_FILE = Path.home() / ".zero" / "notes.json"


def _load() -> list[dict[str, Any]]:
    try:
        if _NOTES_FILE.exists():
            return json.loads(_NOTES_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Failed to load notes.json: {}", e)
    return []


def _save(notes: list[dict[str, Any]]) -> None:
    try:
        _NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
        _NOTES_FILE.write_text(
            json.dumps(notes, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except Exception as e:
        logger.error("Failed to save notes.json: {}", e)


def save_note(content: str, tags: list[str] | None = None) -> dict[str, Any]:
    """Save a new note. Returns the saved note dict."""
    notes = _load()
    note = {
        "id": str(uuid.uuid4())[:8],
        "content": content,
        "tags": tags or [],
        "created_at": datetime.now().isoformat(),
    }
    notes.append(note)
    _save(notes)
    logger.info("Note saved: id={}", note["id"])
    return note


def list_notes(query: str = "") -> list[dict[str, Any]]:
    """Return all notes, optionally filtered by a search query (case-insensitive substring)."""
    notes = _load()
    if query:
        q = query.lower()
        notes = [
            n for n in notes
            if q in n.get("content", "").lower()
            or any(q in t.lower() for t in n.get("tags", []))
        ]
    return sorted(notes, key=lambda n: n.get("created_at", ""), reverse=True)


def delete_note(note_id: str) -> bool:
    """Delete a note by id. Returns True if found and deleted."""
    notes = _load()
    before = len(notes)
    notes = [n for n in notes if n["id"] != note_id]
    if len(notes) < before:
        _save(notes)
        return True
    return False


def clear_all_notes() -> int:
    """Delete all notes. Returns count of deleted notes."""
    notes = _load()
    count = len(notes)
    _save([])
    return count

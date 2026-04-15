"""Reminder tools for the agent."""

from __future__ import annotations

from typing import Any

from zero.agent.tools.base import Tool, tool_parameters
from zero.agent.tools.schema import StringSchema, BooleanSchema, tool_parameters_schema


@tool_parameters(
    tool_parameters_schema(
        title=StringSchema("Short description of what to be reminded about"),
        due_iso=StringSchema(
            "Due date/time in ISO 8601 format, e.g. '2026-04-15T17:00:00'. "
            "Derive this from the user's natural language — e.g. 'tomorrow at 5pm'."
        ),
        note=StringSchema("Optional extra details or context for the reminder"),
        required=["title", "due_iso"],
    )
)
class ReminderSetTool(Tool):
    """Save a reminder to ~/.zero/reminders.json."""

    def __init__(self) -> None:
        self._channel: str = ""
        self._chat_id: str = ""

    def set_context(self, channel: str, chat_id: str) -> None:
        """Capture the channel and chat_id of the requesting session."""
        self._channel = channel
        self._chat_id = chat_id

    @property
    def name(self) -> str:
        return "reminder_set"

    @property
    def description(self) -> str:
        return (
            "Save a reminder for the user. Call this when the user says things like "
            "'remind me to...', 'don't let me forget...', 'schedule a reminder for...'. "
            "Store the reminder in reminders.json AND use the cron tool to create a one-shot "
            "job at the due_iso time to deliver the reminder message via Telegram."
        )

    async def execute(self, title: str, due_iso: str, note: str = "", **kwargs: Any) -> str:
        from zero.utils.reminders import add_reminder
        reminder = add_reminder(
            title=title,
            due_iso=due_iso,
            note=note,
            channel=self._channel,
            chat_id=self._chat_id,
        )
        details = f" ({note})" if note else ""
        return (
            f"✅ Reminder saved (id: {reminder['id']}): '{title}'{details} — due at {due_iso}.\n"
            f"Now use the `cron` tool to schedule a one-shot delivery: "
            f"action='add', at='{due_iso}', message='🔔 Reminder: {title}{details}', deliver=True."
        )


@tool_parameters(
    tool_parameters_schema(
        include_done=BooleanSchema(
            description="Whether to include completed reminders (default: false)",
            default=False,
        ),
    )
)
class ReminderListTool(Tool):
    """List all upcoming (and optionally completed) reminders."""

    @property
    def name(self) -> str:
        return "reminder_list"

    @property
    def description(self) -> str:
        return (
            "Return the user's saved reminders from reminders.json. "
            "Call this when the user asks 'what are my reminders', 'show reminders', "
            "'what do I have coming up', etc."
        )

    async def execute(self, include_done: bool = False, **kwargs: Any) -> str:
        from zero.utils.reminders import list_reminders
        reminders = list_reminders(include_done=include_done)
        if not reminders:
            return "No upcoming reminders." if not include_done else "No reminders saved."
        lines = []
        for r in reminders:
            status = "✅" if r.get("done") else "🔔"
            note_part = f" — {r['note']}" if r.get("note") else ""
            lines.append(f"{status} [{r['id']}] {r['title']} — due {r['due_iso']}{note_part}")
        return "Your reminders:\n" + "\n".join(lines)

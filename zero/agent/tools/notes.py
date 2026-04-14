"""Notes tools for the agent."""

from __future__ import annotations

from typing import Any

from zero.agent.tools.base import Tool, tool_parameters
from zero.agent.tools.schema import StringSchema, ArraySchema, tool_parameters_schema


@tool_parameters(
    tool_parameters_schema(
        content=StringSchema("The note content to save"),
        tags=ArraySchema(
            items=StringSchema("A tag"),
            description="Optional list of tags to categorize the note (e.g. ['work', 'idea'])",
        ),
        required=["content"],
    )
)
class NoteSaveTool(Tool):
    """Save a note to ~/.zero/notes.json."""

    @property
    def name(self) -> str:
        return "note_save"

    @property
    def description(self) -> str:
        return (
            "Save a note for the user. Trigger this when the user says things like "
            "'note this down', 'save this', 'remember this', 'jot this down', 'keep a note of...'. "
            "Always confirm what was saved."
        )

    async def execute(self, content: str, tags: list[str] | None = None, **kwargs: Any) -> str:
        from zero.utils.notes import save_note
        note = save_note(content=content, tags=tags)
        tag_str = f" [tags: {', '.join(note['tags'])}]" if note.get("tags") else ""
        return f"📝 Note saved (id: {note['id']}){tag_str}: \"{content}\""


@tool_parameters(
    tool_parameters_schema(
        query=StringSchema(
            "Optional search query to filter notes (case-insensitive). "
            "Leave empty to list all notes."
        ),
    )
)
class NoteListTool(Tool):
    """List or search saved notes."""

    @property
    def name(self) -> str:
        return "note_list"

    @property
    def description(self) -> str:
        return (
            "List or search the user's saved notes from notes.json. "
            "Trigger when user says 'show my notes', 'what did I save', "
            "'find my note about X', 'search my notes for X'."
        )

    async def execute(self, query: str = "", **kwargs: Any) -> str:
        from zero.utils.notes import list_notes
        notes = list_notes(query=query)
        if not notes:
            msg = f"No notes found matching '{query}'." if query else "No notes saved yet."
            return msg
        lines = []
        for n in notes:
            tags = f" [{', '.join(n['tags'])}]" if n.get("tags") else ""
            created = n.get("created_at", "")[:16].replace("T", " ")
            lines.append(f"📝 [{n['id']}] {n['content']}{tags} — {created}")
        qualifier = f" matching '{query}'" if query else ""
        return f"Your notes{qualifier}:\n" + "\n".join(lines)


@tool_parameters(
    tool_parameters_schema(
        note_id=StringSchema("The id of the note to delete (from note_list output)"),
        clear_all=StringSchema(
            "Set to 'yes' to delete ALL notes. Requires explicit user confirmation."
        ),
        required=[],
    )
)
class NoteDeleteTool(Tool):
    """Delete a specific note or all notes."""

    @property
    def name(self) -> str:
        return "note_delete"

    @property
    def description(self) -> str:
        return (
            "Delete a note by id, or clear all notes if the user explicitly asks. "
            "Trigger on 'delete that note', 'remove note X', 'clear my notes', 'delete all notes'. "
            "For 'clear all', always confirm with the user before calling with clear_all='yes'."
        )

    async def execute(
        self, note_id: str = "", clear_all: str = "", **kwargs: Any
    ) -> str:
        if clear_all.strip().lower() == "yes":
            from zero.utils.notes import clear_all_notes
            count = clear_all_notes()
            return f"🗑️ Cleared all {count} note(s)."
        if not note_id:
            return "Error: provide a note_id to delete, or clear_all='yes' to delete everything."
        from zero.utils.notes import delete_note
        if delete_note(note_id):
            return f"🗑️ Note {note_id} deleted."
        return f"Note '{note_id}' not found."

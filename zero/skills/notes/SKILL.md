---
name: notes
description: Personal notes system — save, search, list and delete notes stored in ~/.zero/notes.json.
always: true
---

# Notes

You have three tools: `note_save`, `note_list`, `note_delete`.

## Saving a Note

Trigger when user says:
- "note this down", "save this", "remember this for me", "jot this down"
- "keep a note: ..."
- "save this idea: ..."

```
note_save(content="<what the user said>")
```

With tags:
```
note_save(content="Meeting with Alex at Cafe Blue", tags=["meetings", "work"])
```

Always confirm what was saved: "📝 Got it, I've saved that note!"

## Listing / Searching Notes

**Show all notes** — "what did I save", "show my notes", "list my notes":
```
note_list()
```

**Search** — "find my note about the meeting", "do I have anything about John":
```
note_list(query="meeting")
```

Return the notes in a conversational way, not a raw data dump.

## Deleting Notes

**Delete one** — "delete that note", "remove note abc123":
```
note_delete(note_id="abc123")
```

**Delete all** — "clear my notes", "delete all notes":
Always confirm first: "Are you sure you want to delete all your notes? This can't be undone."
After confirmation:
```
note_delete(clear_all="yes")
```

## Tags

Tags make notes searchable. Use them when context is clear:
- "work", "personal", "idea", "meeting", "tomorrow_plan", "shopping"

The `tomorrow_plan` tag is used by the evening check-in to store next-day plans.

---
name: reminders
description: Smart reminder system — set, list and receive time-based reminders via Telegram.
always: true
---

# Reminders

You have two reminder tools: `reminder_set` and `reminder_list`. You also have the `cron` tool for scheduling delivery.

## Setting a Reminder

When the user says anything like:
- "remind me to call John at 5pm"
- "don't let me forget about the meeting tomorrow at 10"
- "remind me in 2 hours to take my medicine"

**Always do both steps:**

1. Call `reminder_set` with the extracted title, due_iso, and optional note.
2. Immediately follow up with a `cron` call:
   - `action="add"`, `at="<same due_iso>"`, `deliver=True`
   - `message="🔔 Reminder: <title>"` (include note if present)

The cron job sends the Telegram message at exactly the right time. Both steps are required.

Example — "remind me to submit the report tomorrow at 9am":
```
reminder_set(title="Submit the report", due_iso="2026-04-15T09:00:00")
cron(action="add", at="2026-04-15T09:00:00", message="🔔 Reminder: Submit the report", deliver=True)
```

## Listing Reminders

When user asks "what are my reminders", "show upcoming reminders":
```
reminder_list()
```

## Morning Briefing Time

The user's morning briefing time is stored in their profile as `morning_briefing_time` (e.g. "07:00").

If the user has never set it, ask **once**:
> "What time should I brief you every morning? (e.g. 7am, 8:30am)"

After they answer, save it to their profile and confirm:
> "Got it! I'll brief you every morning at 7am with your reminders and plan for the day."

If the user changes it (e.g. "change my morning briefing to 8am"), update the profile and confirm.

## Evening Check-In (9 PM Daily)

Every evening at 9 PM, Zero asks the user:
> "Hey! 🌙 What's on your plate tomorrow? Tell me everything and I'll make sure you don't miss anything."

Whatever the user replies, save a note with tag ["tomorrow_plan"] using `note_save`. Then confirm:
> "Got it, I've saved your plan. I'll remind you about everything tomorrow morning!"

## Morning Briefing

Every morning at the user's configured time, deliver a warm summary like:
> "Good morning! ☀️ Here's what's on your plate today: [list reminders due today]. [Any saved tomorrow_plan notes]. Have a great day!"

Use `reminder_list()` and `note_list(query="tomorrow_plan")` to gather the data.
Keep it conversational — not a boring bullet list.

## Time Parsing Reference

| User says | due_iso to compute |
|-----------|-------------------|
| "at 5pm" today | today's date + T17:00:00 |
| "tomorrow at 9am" | tomorrow's date + T09:00:00 |
| "in 2 hours" | current time + 2h |
| "next Monday" | next Monday's date + T09:00:00 |

Always compute exact ISO datetimes from the current time shown in the runtime context.

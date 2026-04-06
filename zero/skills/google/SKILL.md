---
name: google
description: "Manage Google Calendar, Gmail, and Tasks. Use these tools to schedule meetings, read emails, and track tasks."
metadata: {"zero":{"emoji":"☁️","requires":{"env":["ZERO_GOOGLE__CLIENT_ID","ZERO_GOOGLE__CLIENT_SECRET"]}}}
---

# Google Skill

Use the Google Calendar, Gmail, and Tasks tools to help the user manage their personal and professional life.

## Calendar

- **Scheduling**: When a user asks to "schedule", "book", or "meeting", use `google_calendar_create_event`.
- **Viewing**: When a user asks "what's on my calendar" or "upcoming events", use `google_calendar_list_events`.
- **Modifying**: Use `google_calendar_update_event` to reschedule or change details.

## Gmail

- **Inbox Summary**: Use `gmail_list_messages` to give the user a quick overview of their latest emails.
- **Reading**: Use `gmail_read_message` ONLY when the user asks to see a specific email in full.
- **Sending/Replying**: Use `gmail_send_message` to send new emails or reply to existing threads.
- **Drafting**: If the user is unsure, use `gmail_create_draft`.

## Tasks

- **Listing**: Use `google_tasks_list` to show current task lists and individual tasks.
- **Adding**: Use `google_tasks_create` to add new todos.
- **Completing**: Use `google_tasks_complete` when the user says they've finished something.

## Conversational Guidelines

1. **Be Human**: Never say "The API returned...". Instead, say "You have a meeting with John at 3 PM tomorrow."
2. **Summarize**: When listing emails, provide a concise summary based on the subject and sender.
3. **Be Proactive**: If you see a task due today while checking the calendar, mention it!

## Examples

- "Schedule a meeting tomorrow at 3pm" or "Add a meeting to my calendar" → `google_calendar_create_event`
- "Do I have any emails from John?" → `gmail_list_messages`
- "Add 'buy groceries' to my tasks" or "Remind me to check the mail" → `google_tasks_create`
- "What's on my calendar?" or "Read my events" → `google_calendar_list_events`
- "List all tasks" or "What are my todos?" → `google_tasks_list`

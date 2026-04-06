from datetime import datetime, timedelta
from typing import Any

from loguru import logger

from zero.agent.tools.base import Tool, tool_parameters
from zero.utils.google_auth import get_calendar_service
from zero.utils.helpers import current_time_str

class GoogleCalendarTool(Tool):
    """Base class for Google Calendar tools."""
    
    def __init__(self):
        self._notify_callback = None

    def set_notify_callback(self, callback):
        self._notify_callback = callback

    async def _get_service(self):
        from zero.utils.google_auth import auth_manager
        auth_manager.set_notify_callback(self._notify_callback)
        return await get_calendar_service()

@tool_parameters({
    "type": "object",
    "properties": {
        "time_min": {"type": "string", "description": "ISO format start time. Defaults to now."},
        "time_max": {"type": "string", "description": "ISO format end time. Defaults to 7 days from now."},
        "max_results": {"type": "integer", "default": 10},
    }
})
class GoogleCalendarListEventsTool(GoogleCalendarTool):
    @property
    def name(self) -> str:
        return "google_calendar_list_events"

    @property
    def description(self) -> str:
        return "List upcoming events from Google Calendar."

    async def execute(self, time_min: str | None = None, time_max: str | None = None, max_results: int = 10) -> str:
        try:
            service = await self._get_service()
            now = datetime.utcnow().isoformat() + "Z"
            t_min = time_min or now
            
            events_result = service.events().list(
                calendarId="primary",
                timeMin=t_min,
                timeMax=time_max,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime"
            ).execute()
            
            events = events_result.get("items", [])
            if not events:
                return "No upcoming events found."
            
            lines = [f"Upcoming events (from {t_min}):"]
            for event in events:
                start = event["start"].get("dateTime", event["start"].get("date"))
                summary = event.get("summary", "(No title)")
                event_id = event.get("id")
                lines.append(f"- {start}: {summary} (ID: {event_id})")
            
            return "\n".join(lines)
        except Exception as e:
            return f"Error listing events: {str(e)}"

@tool_parameters({
    "type": "object",
    "properties": {
        "summary": {"type": "string", "description": "Title of the event"},
        "start_time": {"type": "string", "description": "ISO format start time (e.g. 2024-04-07T15:00:00Z)"},
        "end_time": {"type": "string", "description": "ISO format end time"},
        "description": {"type": "string"},
        "location": {"type": "string"},
        "reminders_minutes": {"type": "integer", "description": "Minutes before event for a popup reminder"},
    },
    "required": ["summary", "start_time", "end_time"]
})
class GoogleCalendarCreateEventTool(GoogleCalendarTool):
    @property
    def name(self) -> str:
        return "google_calendar_create_event"

    @property
    def description(self) -> str:
        return "Schedule a new event on Google Calendar."

    async def execute(self, summary: str, start_time: str, end_time: str, **kwargs) -> str:
        try:
            service = await self._get_service()
            event_body = {
                "summary": summary,
                "location": kwargs.get("location"),
                "description": kwargs.get("description"),
                "start": {"dateTime": start_time},
                "end": {"dateTime": end_time},
            }
            
            if "reminders_minutes" in kwargs:
                event_body["reminders"] = {
                    "useDefault": False,
                    "overrides": [{"method": "popup", "minutes": kwargs["reminders_minutes"]}]
                }

            event = service.events().insert(calendarId="primary", body=event_body).execute()
            return f"Event created: {event.get('htmlLink')}"
        except Exception as e:
            return f"Error creating event: {str(e)}"

@tool_parameters({
    "type": "object",
    "properties": {
        "event_id": {"type": "string", "description": "ID of the event to update"},
        "summary": {"type": "string"},
        "start_time": {"type": "string"},
        "end_time": {"type": "string"},
        "description": {"type": "string"},
        "reminders_minutes": {"type": "integer"},
    },
    "required": ["event_id"]
})
class GoogleCalendarUpdateEventTool(GoogleCalendarTool):
    @property
    def name(self) -> str:
        return "google_calendar_update_event"

    @property
    def description(self) -> str:
        return "Update or reschedule an existing Google Calendar event."

    async def execute(self, event_id: str, **kwargs) -> str:
        try:
            service = await self._get_service()
            event = service.events().get(calendarId="primary", eventId=event_id).execute()
            
            if "summary" in kwargs: event["summary"] = kwargs["summary"]
            if "description" in kwargs: event["description"] = kwargs["description"]
            if "start_time" in kwargs: event["start"] = {"dateTime": kwargs["start_time"]}
            if "end_time" in kwargs: event["end"] = {"dateTime": kwargs["end_time"]}
            
            if "reminders_minutes" in kwargs:
                event["reminders"] = {
                    "useDefault": False,
                    "overrides": [{"method": "popup", "minutes": kwargs["reminders_minutes"]}]
                }

            updated_event = service.events().update(calendarId="primary", eventId=event_id, body=event).execute()
            return f"Event updated: {updated_event.get('htmlLink')}"
        except Exception as e:
            return f"Error updating event: {str(e)}"

@tool_parameters({
    "type": "object",
    "properties": {
        "event_id": {"type": "string", "description": "ID of the event to delete"},
    },
    "required": ["event_id"]
})
class GoogleCalendarDeleteEventTool(GoogleCalendarTool):
    @property
    def name(self) -> str:
        return "google_calendar_delete_event"

    @property
    def description(self) -> str:
        return "Delete an event from Google Calendar."

    async def execute(self, event_id: str) -> str:
        try:
            service = await self._get_service()
            service.events().delete(calendarId="primary", eventId=event_id).execute()
            return "Event deleted successfully."
        except Exception as e:
            return f"Error deleting event: {str(e)}"

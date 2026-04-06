from typing import Any
from datetime import datetime

from loguru import logger

from zero.agent.tools.base import Tool, tool_parameters
from zero.utils.google_auth import get_tasks_service

class GoogleTasksTool(Tool):
    """Base class for Google Tasks tools."""
    
    def __init__(self):
        self._notify_callback = None

    def set_notify_callback(self, callback):
        self._notify_callback = callback

    async def _get_service(self):
        from zero.utils.google_auth import auth_manager
        auth_manager.set_notify_callback(self._notify_callback)
        return await get_tasks_service()

@tool_parameters({
    "type": "object",
    "properties": {
        "task_list_id": {"type": "string", "description": "Optional task list ID. Defaults to @default."},
    }
})
class GoogleTasksListTool(GoogleTasksTool):
    @property
    def name(self) -> str:
        return "google_tasks_list"

    @property
    def description(self) -> str:
        return "List all tasks and task lists from Google Tasks."

    async def execute(self, task_list_id: str | None = None) -> str:
        try:
            service = await self._get_service()
            
            # List task lists
            task_lists_result = service.tasklists().list().execute()
            task_lists = task_lists_result.get("items", [])
            
            lines = ["Task Lists:"]
            for tl in task_lists:
                lines.append(f"- {tl['title']} (ID: {tl['id']})")
                
            # If no list is specified, list tasks for the default list or iterate through all?
            # User says "Read all tasks". Let's iterate.
            target_lists = [l for l in task_lists if l['id'] == task_list_id] if task_list_id else task_lists
            
            for list_obj in target_lists:
                tasks_result = service.tasks().list(tasklist=list_obj["id"], showCompleted=True, showHidden=True).execute()
                tasks = tasks_result.get("items", [])
                lines.append(f"\nTasks in {list_obj['title']}:")
                if not tasks:
                    lines.append("No tasks found.")
                for task in tasks:
                    status = "✓" if task.get("status") == "completed" else " "
                    due = f" Due: {task['due']}" if task.get("due") else ""
                    lines.append(f"[{status}] {task['title']} (ID: {task['id']}){due}")
            
            return "\n".join(lines)
        except Exception as e:
            return f"Error listing tasks: {str(e)}"

@tool_parameters({
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Title of the task"},
        "notes": {"type": "string"},
        "due": {"type": "string", "description": "ISO format due date (e.g. 2024-04-10T12:00:00Z)"},
        "task_list_id": {"type": "string", "description": "Defaults to @default."},
    },
    "required": ["title"]
})
class GoogleTasksCreateTool(GoogleTasksTool):
    @property
    def name(self) -> str:
        return "google_tasks_create"

    @property
    def description(self) -> str:
        return "Add a new task to Google Tasks."

    async def execute(self, title: str, task_list_id: str = "@default", **kwargs) -> str:
        try:
            service = await self._get_service()
            task_body = {"title": title}
            if "notes" in kwargs: task_body["notes"] = kwargs["notes"]
            if "due" in kwargs: task_body["due"] = kwargs["due"]
            
            task = service.tasks().insert(tasklist=task_list_id, body=task_body).execute()
            return f"Task created successfully (ID: {task.get('id')})"
        except Exception as e:
            return f"Error creating task: {str(e)}"

@tool_parameters({
    "type": "object",
    "properties": {
        "task_id": {"type": "string", "description": "ID of the task to complete"},
        "task_list_id": {"type": "string", "description": "Defaults to @default."},
    },
    "required": ["task_id"]
})
class GoogleTasksCompleteTool(GoogleTasksTool):
    @property
    def name(self) -> str:
        return "google_tasks_complete"

    @property
    def description(self) -> str:
        return "Mark a task as complete in Google Tasks."

    async def execute(self, task_id: str, task_list_id: str = "@default") -> str:
        try:
            service = await self._get_service()
            task = service.tasks().get(tasklist=task_list_id, task=task_id).execute()
            task["status"] = "completed"
            service.tasks().update(tasklist=task_list_id, task=task_id, body=task).execute()
            return "Task marked as complete."
        except Exception as e:
            return f"Error completing task: {str(e)}"

@tool_parameters({
    "type": "object",
    "properties": {
        "task_id": {"type": "string", "description": "ID of the task to delete"},
        "task_list_id": {"type": "string", "description": "Defaults to @default."},
    },
    "required": ["task_id"]
})
class GoogleTasksDeleteTool(GoogleTasksTool):
    @property
    def name(self) -> str:
        return "google_tasks_delete"

    @property
    def description(self) -> str:
        return "Remove a task from Google Tasks."

    async def execute(self, task_id: str, task_list_id: str = "@default") -> str:
        try:
            service = await self._get_service()
            service.tasks().delete(tasklist=task_list_id, task=task_id).execute()
            return "Task deleted successfully."
        except Exception as e:
            return f"Error deleting task: {str(e)}"

import base64
from email.mime.text import MIMEText
from typing import Any

from loguru import logger

from zero.agent.tools.base import Tool, tool_parameters
from zero.utils.google_auth import get_gmail_service

class GmailTool(Tool):
    """Base class for Gmail tools."""
    
    def __init__(self):
        self._notify_callback = None

    def set_notify_callback(self, callback):
        self._notify_callback = callback

    async def _get_service(self):
        from zero.utils.google_auth import auth_manager
        auth_manager.set_notify_callback(self._notify_callback)
        return await get_gmail_service()

@tool_parameters({
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "Gmail search query (e.g. 'from:john' or 'is:unread')"},
        "max_results": {"type": "integer", "default": 10},
    }
})
class GmailListMessagesTool(GmailTool):
    @property
    def name(self) -> str:
        return "gmail_list_messages"

    @property
    def description(self) -> str:
        return "List and summarize messages from Gmail inbox."

    async def execute(self, query: str = "label:INBOX", max_results: int = 10) -> str:
        try:
            service = await self._get_service()
            results = service.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
            messages = results.get("messages", [])
            
            if not messages:
                return "No messages found."
            
            lines = ["Inbox Summary:"]
            for msg in messages:
                m = service.users().messages().get(userId="me", id=msg["id"], format="metadata", metadataHeaders=["From", "Subject"]).execute()
                headers = m.get("payload", {}).get("headers", [])
                sender = next((h["value"] for h in headers if h["name"] == "From"), "Unknown")
                subject = next((h["value"] for h in headers if h["name"] == "Subject"), "(No Subject)")
                snippet = m.get("snippet", "")
                lines.append(f"- ID: {msg['id']}\n  From: {sender}\n  Subject: {subject}\n  Summary: {snippet}")
            
            return "\n".join(lines)
        except Exception as e:
            return f"Error listing messages: {str(e)}"

@tool_parameters({
    "type": "object",
    "properties": {
        "message_id": {"type": "string", "description": "ID of the message to read"},
    },
    "required": ["message_id"]
})
class GmailReadMessageTool(GmailTool):
    @property
    def name(self) -> str:
        return "gmail_read_message"

    @property
    def description(self) -> str:
        return "Read the full body of a specific Gmail message."

    async def execute(self, message_id: str) -> str:
        try:
            service = await self._get_service()
            message = service.users().messages().get(userId="me", id=message_id, format="full").execute()
            payload = message.get("payload", {})
            parts = payload.get("parts", [])
            body = ""
            
            if not parts:
                body = base64.urlsafe_b64decode(payload.get("body", {}).get("data", "")).decode()
            else:
                for part in parts:
                    if part.get("mimeType") == "text/plain":
                        body = base64.urlsafe_b64decode(part.get("body", {}).get("data", "")).decode()
                        break
            
            headers = payload.get("headers", [])
            sender = next((h["value"] for h in headers if h["name"] == "From"), "Unknown")
            subject = next((h["value"] for h in headers if h["name"] == "Subject"), "(No Subject)")
            
            return f"From: {sender}\nSubject: {subject}\n\n{body}"
        except Exception as e:
            return f"Error reading message: {str(e)}"

@tool_parameters({
    "type": "object",
    "properties": {
        "to": {"type": "string", "description": "Recipient email address"},
        "subject": {"type": "string"},
        "body": {"type": "string"},
        "thread_id": {"type": "string", "description": "Optional thread ID to reply to"},
    },
    "required": ["to", "subject", "body"]
})
class GmailSendMessageTool(GmailTool):
    @property
    def name(self) -> str:
        return "gmail_send_message"

    @property
    def description(self) -> str:
        return "Send a new email or reply to an existing one."

    async def execute(self, to: str, subject: str, body: str, thread_id: str | None = None) -> str:
        try:
            service = await self._get_service()
            message = MIMEText(body)
            message["to"] = to
            message["subject"] = subject
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            body = {"raw": raw}
            if thread_id:
                body["threadId"] = thread_id
            
            sent_msg = service.users().messages().send(userId="me", body=body).execute()
            return f"Message sent successfully (ID: {sent_msg.get('id')})"
        except Exception as e:
            return f"Error sending message: {str(e)}"

@tool_parameters({
    "type": "object",
    "properties": {
        "to": {"type": "string"},
        "subject": {"type": "string"},
        "body": {"type": "string"},
    },
    "required": ["to", "subject", "body"]
})
class GmailDraftMessageTool(GmailTool):
    @property
    def name(self) -> str:
        return "gmail_create_draft"

    @property
    def description(self) -> str:
        return "Create and save a draft without sending."

    async def execute(self, to: str, subject: str, body: str) -> str:
        try:
            service = await self._get_service()
            message = MIMEText(body)
            message["to"] = to
            message["subject"] = subject
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            draft = service.users().drafts().create(userId="me", body={"message": {"raw": raw}}).execute()
            return f"Draft created successfully (ID: {draft.get('id')})"
        except Exception as e:
            return f"Error creating draft: {str(e)}"

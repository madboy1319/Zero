import os
import json
import asyncio
from pathlib import Path
from typing import Any, Awaitable, Callable

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build, Resource
from loguru import logger

from zero.config.loader import load_config

# If modifying these scopes, delete the file token.json.
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/tasks",
]

class GoogleAuthManager:
    """Manages Google OAuth 2.0 authentication and service instantiation."""

    def __init__(self, token_path: str | None = None):
        config = load_config()
        self.google_config = config.google
        self.token_path = token_path or self.google_config.token_path
        self._creds: Credentials | None = None
        self._notify_callback: Callable[[str], Awaitable[None]] | None = None

    def set_notify_callback(self, callback: Callable[[str], Awaitable[None]] | None):
        """Set a callback to notify the user (e.g., via Telegram)."""
        self._notify_callback = callback

    async def _get_credentials(self) -> Credentials:
        """Gets valid user credentials from storage or performs OAuth flow."""
        creds = None
        # The file token.json stores the user's access and refresh tokens.
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)

        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("Refreshing Google OAuth token...")
                try:
                    await asyncio.to_thread(creds.refresh, Request())
                except Exception as e:
                    logger.error(f"Failed to refresh Google token: {e}")
                    creds = await self._run_flow()
            else:
                creds = await self._run_flow()

            # Save the credentials for the next run
            with open(self.token_path, "w") as token:
                token.write(creds.to_json())

        self._creds = creds
        return creds

    async def _run_flow(self) -> Credentials:
        """Runs the manual OAuth flow."""
        print("\n" + "="*60)
        print("GOOGLE AUTHENTICATION REQUIRED")
        print("="*60)
        
        if self._notify_callback:
            await self._notify_callback(
                "Please check your terminal and open the authorization link to connect your Google account."
            )

        if not self.google_config.client_id or not self.google_config.client_secret:
            raise ValueError(
                "Google Client ID or Secret is missing in configuration. "
                "Please check your .env file."
            )

        client_config = {
            "installed": {
                "client_id": self.google_config.client_id,
                "client_secret": self.google_config.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [self.google_config.redirect_uri],
            }
        }

        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
        auth_url, _ = flow.authorization_url(prompt='consent')
        
        print(f"\nAuthorization URL:\n{auth_url}\n")
        print("="*60 + "\n")

        # Run the local server in a separate thread to avoid blocking the async loop
        try:
            # We use port 8080 as requested in redirect_uri
            # flow.run_local_server is blocking, so we use to_thread
            creds = await asyncio.to_thread(
                flow.run_local_server, 
                port=8080, 
                prompt="consent",
                authorization_prompt_message="Visit this URL to authorize: {url}"
            )
        except Exception as e:
            logger.error(f"OAuth flow failed: {e}")
            # Fallback to console flow if supported by the library version
            creds = await asyncio.to_thread(flow.run_console)
        
        if self._notify_callback:
            await self._notify_callback(
                "Google account connected successfully! Try your command again."
            )
        
        return creds

    async def get_service(self, service_name: str, version: str) -> Resource:
        """Returns an authenticated Google API service object."""
        creds = await self._get_credentials()
        return await asyncio.to_thread(build, service_name, version, credentials=creds)

# Singleton instance for easy access
auth_manager = GoogleAuthManager()

async def get_calendar_service() -> Resource:
    return await auth_manager.get_service("calendar", "v3")

async def get_gmail_service() -> Resource:
    return await auth_manager.get_service("gmail", "v1")

async def get_tasks_service() -> Resource:
    # Note: Using v1 as it is the stable release for Google Tasks API.
    return await auth_manager.get_service("tasks", "v1")

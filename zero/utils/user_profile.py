"""User profile management for persistent memory."""

import json
from pathlib import Path
from typing import Any
from loguru import logger

DEFAULT_PROFILE = {
    "name": "",
    "nickname": "",
    "communication_style": "",
    "interests": [],
    "hobbies": [],
    "likes": [],
    "dislikes": [],
    "mood_history": [],
    "current_mood": "neutral",
    "frequently_discussed": [],
    "personal_notes": [],
    "onboarding_complete": False
}

class UserProfileManager:
    """Manages reading, writing, and merging user profile data."""

    def __init__(self, workspace: Path):
        self.path = workspace / "user_profile.json"
        self._ensure_exists()

    def _ensure_exists(self):
        """Create the profile file with default values if it doesn't exist."""
        if not self.path.exists():
            self.save(DEFAULT_PROFILE)

    def load(self) -> dict[str, Any]:
        """Load the user profile from disk."""
        try:
            if not self.path.exists():
                return DEFAULT_PROFILE.copy()
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Ensure all default keys exist
                for k, v in DEFAULT_PROFILE.items():
                    if k not in data:
                        data[k] = v
                return data
        except Exception as e:
            logger.error("Failed to load user profile: {}", e)
            return DEFAULT_PROFILE.copy()

    def save(self, data: dict[str, Any]):
        """Save the user profile to disk."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error("Failed to save user profile: {}", e)

    def merge(self, new_data: dict[str, Any]):
        """Deep merge new data into the existing profile."""
        current = self.load()
        for key, value in new_data.items():
            if key not in DEFAULT_PROFILE:
                continue
            
            # Smart merge based on type
            if isinstance(value, list) and isinstance(current.get(key), list):
                # Append unique items for lists like interests, hobbies, etc.
                existing = set(map(str, current[key]))
                for item in value:
                    if str(item) not in existing:
                        current[key].append(item)
            elif isinstance(value, dict) and isinstance(current.get(key), dict):
                current[key].update(value)
            else:
                # Overwrite for strings, bools, etc.
                current[key] = value
        
        self.save(current)

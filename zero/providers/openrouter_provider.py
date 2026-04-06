"""OpenRouter provider with dynamic free model pool and failover."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any, Callable, Awaitable

import httpx
from loguru import logger

from zero.providers.openai_compat_provider import OpenAICompatProvider
from zero.providers.base import LLMResponse

if TYPE_CHECKING:
    from zero.providers.registry import ProviderSpec


class OpenRouterProvider(OpenAICompatProvider):
    """
    OpenRouter-specific provider that manages a dynamic pool of free models.

    Features:
    - Fetches live models from OpenRouter on startup and every 24 hours.
    - Filters for free models (pricing.prompt == "0" and pricing.completion == "0").
    - Maintains a session-based pool of healthy models.
    - Performs automatic failover across the pool on model failure.
    """

    MODELS_URL = "https://openrouter.ai/api/v1/models"
    REFRESH_INTERVAL = 24 * 60 * 60  # 24 hours in seconds

    # Initial seeded list of known free models (used if live fetch fails or as base)
    SEEDED_FREE_MODELS = [
        "google/gemini-2.0-flash-lite-preview-02-05:free",
        "google/gemini-2.0-pro-exp-02-05:free",
        "deepseek/deepseek-r1:free",
        "deepseek/deepseek-chat:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "qwen/qwen-2.5-72b-instruct:free",
        "openrouter/auto",  # OpenRouter-specific auto-router
    ]

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        default_model: str = "openrouter/free",
        extra_headers: dict[str, str] | None = None,
        spec: ProviderSpec | None = None,
    ):
        # OpenRouter-specific headers required by the user
        or_headers = {
            "HTTP-Referer": "zero",
            "X-Title": "Zero",
        }
        if extra_headers:
            or_headers.update(extra_headers)

        super().__init__(
            api_key=api_key,
            api_base=api_base or "https://openrouter.ai/api/v1",
            default_model=default_model,
            extra_headers=or_headers,
            spec=spec,
        )
        self._pool: list[str] = []
        self._failed_models: set[str] = set()
        self._last_refresh: float = 0
        self._refresh_lock = asyncio.Lock()

    async def _ensure_pool(self) -> None:
        """Ensure the model pool is initialized and fresh."""
        now = time.monotonic()
        if not self._pool or (now - self._last_refresh) > self.REFRESH_INTERVAL:
            async with self._refresh_lock:
                # Re-check inside lock
                if not self._pool or (now - self._last_refresh) > self.REFRESH_INTERVAL:
                    await self._refresh_pool()

    async def _refresh_pool(self) -> None:
        """Fetch live models from OpenRouter and filter for free ones."""
        logger.info("Refreshing OpenRouter free model pool...")
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.MODELS_URL, headers=headers)
                response.raise_for_status()
                data = response.json()
                
                live_models = []
                for m in data.get("data", []):
                    pricing = m.get("pricing", {})
                    # Filter for free models: prompt and completion pricing are both "0"
                    if str(pricing.get("prompt")) == "0" and str(pricing.get("completion")) == "0":
                        live_models.append(m["id"])

                # Merge with seeded list and deduplicate
                pool = list(dict.fromkeys(live_models + self.SEEDED_FREE_MODELS))
                self._pool = pool
                self._failed_models.clear()  # Reset failures on refresh
                self._last_refresh = time.monotonic()
                logger.info("OpenRouter pool refreshed: {} free models found.", len(live_models))
        except Exception as e:
            logger.error("Failed to refresh OpenRouter pool: {}. Using seeded models.", e)
            if not self._pool:
                self._pool = self.SEEDED_FREE_MODELS
            self._last_refresh = time.monotonic()

    def _get_healthy_pool(self) -> list[str]:
        """Return models from the pool that haven't failed in this session."""
        return [m for m in self._pool if m not in self._failed_models]

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.85,
        reasoning_effort: str | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> LLMResponse:
        await self._ensure_pool()
        
        # If a specific model is requested (not a generic free one), use it directly
        if model and model not in ("openrouter/free", "auto"):
            return await super().chat(
                messages=messages, tools=tools, model=model,
                max_tokens=max_tokens, temperature=temperature,
                reasoning_effort=reasoning_effort, tool_choice=tool_choice,
            )

        # Failover loop across the healthy pool
        pool = self._get_healthy_pool()
        if not pool:
            return LLMResponse(
                content="I'm having trouble connecting right now. Try again in a moment.",
                finish_reason="error"
            )

        for current_model in pool:
            logger.debug("Trying OpenRouter model: {}", current_model)
            response = await super().chat(
                messages=messages, tools=tools, model=current_model,
                max_tokens=max_tokens, temperature=temperature,
                reasoning_effort=reasoning_effort, tool_choice=tool_choice,
            )

            if response.finish_reason != "error":
                return response

            # If failed, mark as failed and try next
            logger.warning("OpenRouter model {} failed, switching...", current_model)
            self._failed_models.add(current_model)

        return LLMResponse(
            content="I'm having trouble connecting right now. Try again in a moment.",
            finish_reason="error"
        )

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.85,
        reasoning_effort: str | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        on_content_delta: Callable[[str], Awaitable[None]] | None = None,
    ) -> LLMResponse:
        await self._ensure_pool()

        if model and model not in ("openrouter/free", "auto"):
            return await super().chat_stream(
                messages=messages, tools=tools, model=model,
                max_tokens=max_tokens, temperature=temperature,
                reasoning_effort=reasoning_effort, tool_choice=tool_choice,
                on_content_delta=on_content_delta,
            )

        pool = self._get_healthy_pool()
        if not pool:
            return LLMResponse(
                content="I'm having trouble connecting right now. Try again in a moment.",
                finish_reason="error"
            )

        for current_model in pool:
            logger.debug("Trying OpenRouter model (stream): {}", current_model)
            response = await super().chat_stream(
                messages=messages, tools=tools, model=current_model,
                max_tokens=max_tokens, temperature=temperature,
                reasoning_effort=reasoning_effort, tool_choice=tool_choice,
                on_content_delta=on_content_delta,
            )

            if response.finish_reason != "error":
                return response

            logger.warning("OpenRouter model {} (stream) failed, switching...", current_model)
            self._failed_models.add(current_model)

        return LLMResponse(
            content="I'm having trouble connecting right now. Try again in a moment.",
            finish_reason="error"
        )

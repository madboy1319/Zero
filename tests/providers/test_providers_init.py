"""Tests for lazy provider exports from zero.providers."""

from __future__ import annotations

import importlib
import sys


def test_importing_providers_package_is_lazy(monkeypatch) -> None:
    monkeypatch.delitem(sys.modules, "zero.providers", raising=False)
    monkeypatch.delitem(sys.modules, "zero.providers.anthropic_provider", raising=False)
    monkeypatch.delitem(sys.modules, "zero.providers.openai_compat_provider", raising=False)
    monkeypatch.delitem(sys.modules, "zero.providers.openai_codex_provider", raising=False)
    monkeypatch.delitem(sys.modules, "zero.providers.github_copilot_provider", raising=False)
    monkeypatch.delitem(sys.modules, "zero.providers.azure_openai_provider", raising=False)

    providers = importlib.import_module("zero.providers")

    assert "zero.providers.anthropic_provider" not in sys.modules
    assert "zero.providers.openai_compat_provider" not in sys.modules
    assert "zero.providers.openai_codex_provider" not in sys.modules
    assert "zero.providers.github_copilot_provider" not in sys.modules
    assert "zero.providers.azure_openai_provider" not in sys.modules
    assert providers.__all__ == [
        "LLMProvider",
        "LLMResponse",
        "AnthropicProvider",
        "OpenAICompatProvider",
        "OpenAICodexProvider",
        "GitHubCopilotProvider",
        "AzureOpenAIProvider",
    ]


def test_explicit_provider_import_still_works(monkeypatch) -> None:
    monkeypatch.delitem(sys.modules, "zero.providers", raising=False)
    monkeypatch.delitem(sys.modules, "zero.providers.anthropic_provider", raising=False)

    namespace: dict[str, object] = {}
    exec("from zero.providers import AnthropicProvider", namespace)

    assert namespace["AnthropicProvider"].__name__ == "AnthropicProvider"
    assert "zero.providers.anthropic_provider" in sys.modules

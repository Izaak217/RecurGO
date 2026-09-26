"""Optional local language-model explanations (v0.1.2)."""

from .ollama import OllamaClient
from .settings import OllamaSettings

__all__ = ["OllamaClient", "OllamaSettings"]

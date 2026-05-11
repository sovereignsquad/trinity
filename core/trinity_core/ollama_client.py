"""Backward-compatible shim for the Ollama provider implementation."""

from trinity_core.adapters.model.ollama import OllamaClientError, OllamaModelProvider

OllamaChatClient = OllamaModelProvider

__all__ = ["OllamaChatClient", "OllamaClientError", "OllamaModelProvider"]

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from typing import Any

import litellm

litellm.drop_params = True
litellm.set_verbose = False


class ModelClient:
    """Thin wrapper around LiteLLM with async streaming."""

    def __init__(self, model: str) -> None:
        self.model = model
        self.extra: dict[str, Any] = {}
        if model.startswith("ollama/"):
            self.extra["api_base"] = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")

    async def stream(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        """Yield response chunks token by token."""

        def _call() -> Any:
            return litellm.completion(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                **self.extra,
            )

        try:
            response = await asyncio.to_thread(_call)
        except Exception as exc:  # noqa: BLE001
            yield f"\n[error] {type(exc).__name__}: {exc}\n"
            return

        loop = asyncio.get_running_loop()
        iterator = iter(response)

        def _next() -> Any:
            try:
                return next(iterator)
            except StopIteration:
                return None

        while True:
            chunk = await loop.run_in_executor(None, _next)
            if chunk is None:
                break
            try:
                delta = chunk.choices[0].delta.content
            except (AttributeError, IndexError):
                delta = None
            if delta:
                yield delta

    async def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """Non-streaming completion."""

        def _call() -> Any:
            return litellm.completion(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
                **self.extra,
            )

        try:
            response = await asyncio.to_thread(_call)
            return response.choices[0].message.content or ""
        except Exception as exc:  # noqa: BLE001
            return f"[error] {type(exc).__name__}: {exc}"

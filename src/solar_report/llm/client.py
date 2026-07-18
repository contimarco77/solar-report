"""Async client wrapping the official anthropic SDK.

This is the only module that talks to the Anthropic API directly, so tests
can mock the LLM boundary here instead of patching SDK internals.
"""

from __future__ import annotations

import anthropic


class EmptyResponseError(RuntimeError):
    """Raised when the API response contains no usable text content."""


class AnthropicClient:
    """Minimal async wrapper around ``anthropic.AsyncAnthropic``.

    Retry/backoff beyond the SDK defaults and streaming are intentionally
    out of scope for v0.1.
    """

    def __init__(self, api_key: str, model: str, max_tokens: int) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Send one message to the API and return the response text."""
        response = await self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text_parts = [block.text for block in response.content if block.type == "text"]
        if not text_parts:
            raise EmptyResponseError(
                f"API response contains no text content "
                f"(stop_reason={response.stop_reason!r}, "
                f"content blocks: {[block.type for block in response.content]!r})"
            )
        return "".join(text_parts)

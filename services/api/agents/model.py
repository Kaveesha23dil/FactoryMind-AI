"""Deterministic ADK model used to mock Gemini in automated tests.

This is a genuine ``google.adk.models.BaseLlm`` implementation: it plugs into
the real ADK Runner, session service, and structured-output validation path,
but returns a pre-scripted JSON response instead of calling the network.
"""

from __future__ import annotations

from typing import AsyncGenerator

from google.adk.models import BaseLlm, LlmResponse
from google.genai import types


class ScriptedLlm(BaseLlm):
    """Returns one pre-scripted JSON response per model turn."""

    model: str = "scripted"
    response_text: str = "{}"

    async def generate_content_async(
        self, llm_request, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        yield LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part(text=self.response_text)],
            ),
            turn_complete=True,
        )

"""ADK runtime: builds and executes the logical agents.

Production uses the real ``google.adk.models.Gemini`` model. Automated tests use
:class:`~services.api.agents.model.ScriptedLlm`, which runs through the exact
same ADK Runner / session / structured-output path without touching the network.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.models import Gemini
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from services.api.agents.base import AgentSpec
from services.api.agents.model import ScriptedLlm
from services.api.core import config

logger = logging.getLogger(__name__)

#: Test-only registry of scripted per-agent JSON responses.
_scripted_responses: dict[str, str] = {}


class InvestigationProviderError(Exception):
    """Raised when the model provider fails or returns unusable output."""


def set_scripted_response(agent_name: str, response_text: str) -> None:
    _scripted_responses[agent_name] = response_text


def clear_scripted_responses() -> None:
    _scripted_responses.clear()


def build_runtime() -> "AdkRuntime":
    """Build the runtime based on the configured AI provider."""
    provider = config.settings.ai_provider
    if provider not in config.AI_PROVIDERS:
        raise InvestigationProviderError(
            f"Unsupported AI_PROVIDER '{provider}' (expected one of {config.AI_PROVIDERS})"
        )
    return AdkRuntime(
        provider=provider,
        model_name=config.settings.gemini_model,
        scripted_responses=dict(_scripted_responses),
    )


class AdkRuntime:
    def __init__(
        self,
        provider: str,
        model_name: str,
        scripted_responses: dict[str, str] | None = None,
    ) -> None:
        self.provider = provider
        self.model_name = model_name
        self.scripted_responses = dict(scripted_responses or {})

    # -- construction ----------------------------------------------------

    def _model_for(self, spec: AgentSpec):
        if self.provider == "scripted":
            if spec.name not in self.scripted_responses:
                raise InvestigationProviderError(
                    f"No scripted response registered for agent '{spec.name}'"
                )
            return ScriptedLlm(
                model="scripted",
                response_text=self.scripted_responses[spec.name],
            )
        return Gemini(model=self.model_name)

    def build_agent(self, spec: AgentSpec) -> LlmAgent:
        return LlmAgent(
            name=spec.name,
            description=spec.label,
            model=self._model_for(spec),
            instruction=spec.instruction,
            output_schema=spec.output_schema,
            output_key=f"{spec.name}_output",
        )

    # -- execution -------------------------------------------------------

    async def run(self, spec: AgentSpec, prompt: str) -> dict[str, Any]:
        agent = self.build_agent(spec)
        app_name = f"factorymind-{spec.name}"
        user_id = "investigation"
        session_id = f"{spec.name}-{uuid.uuid4().hex}"
        session_service = InMemorySessionService()
        runner = Runner(app_name=app_name, agent=agent, session_service=session_service)
        await session_service.create_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        )

        try:
            async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=types.Content(
                    role="user", parts=[types.Part(text=prompt)]
                ),
            ):
                if event.error_message:
                    raise InvestigationProviderError(
                        f"{spec.name}: {event.error_message}"
                    )
                usage = getattr(event, "usage_metadata", None)
                if usage is not None:
                    self._log_usage(spec.name, usage)
        except InvestigationProviderError:
            raise
        except Exception as exc:  # provider/network/validation errors
            raise InvestigationProviderError(
                f"{spec.name} failed: {type(exc).__name__}: {exc}"
            ) from exc

        session = await session_service.get_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        )
        if session is None:
            raise InvestigationProviderError(f"{spec.name}: session was lost")
        output = session.state.get(f"{spec.name}_output")
        if output is None:
            raise InvestigationProviderError(
                f"{spec.name} produced no structured output"
            )
        return output

    @staticmethod
    def _log_usage(agent_name: str, usage: Any) -> None:
        prompt_tokens = getattr(usage, "prompt_token_count", None)
        output_tokens = getattr(usage, "candidates_token_count", None)
        total_tokens = getattr(usage, "total_token_count", None)
        if total_tokens is None:
            return
        logger.info(
            "Agent %s token usage: prompt=%s output=%s total=%s",
            agent_name,
            prompt_tokens,
            output_tokens,
            total_tokens,
        )


__all__ = [
    "AdkRuntime",
    "InvestigationProviderError",
    "build_runtime",
    "set_scripted_response",
    "clear_scripted_responses",
]

"""ADK runtime: builds and executes the logical agents.

Production uses the real ``google.adk.models.Gemini`` model. Automated tests use
:class:`~services.api.agents.model.ScriptedLlm`, which runs through the exact
same ADK Runner / session / structured-output path without touching the network.
"""

from __future__ import annotations

import logging
import re
import uuid
import time
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from contextlib import aclosing
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.agents.run_config import RunConfig
from google.adk.models import Gemini
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from services.api.agents.base import AgentSpec
from services.api.agents.model import ScriptedLlm
from services.api.core import config
from services.api.agents.request_control import request_slot, provider_cooldown, save_cooldown

logger = logging.getLogger(__name__)

#: Test-only registry of scripted per-agent JSON responses.
_scripted_responses: dict[str, str] = {}


class InvestigationProviderError(Exception):
    """Raised when the model provider fails or returns unusable output."""

    def __init__(self, message, *, retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after

    @property
    def category(self) -> str:
        message = str(self).lower()
        for marker, category in (('model_allocation', 'model_allocation'), ('spending_limit', 'spending_limit'), ('rpd', 'RPD'), ('tpm', 'TPM'), ('rpm', 'RPM')):
            if re.search(r'\b' + marker + r'\b', message):
                return category
        if re.search(r'quota(?:value)?[\s\x27\x22:]+0\b|limit:\s*0\b|no model allocation|not_found', message):
            return 'model_allocation'
        if re.search(r'spend(?:ing)?[_ -]?(?:limit|cap)|(?:insufficient|exhausted) credits|credits? (?:exhausted|depleted)|billing.*(?:disabled|not enabled)|budget.*(?:exceeded|exhausted)', message):
            return 'spending_limit'
        if self.daily_quota_exhausted:
            return 'RPD'
        if re.search(r'tokens(?:permodel)?perminute|tokens_per_minute|tokens per minute', message):
            return 'TPM'
        if re.search(r'requestsperminute|requests_per_minute|requests per minute', message):
            return 'RPM'
        if '429' in message or 'resource_exhausted' in message:
            return 'quota_unknown'
        if '503' in message or 'unavailable' in message:
            return 'unavailable'
        if 'timed out' in message or 'timeout' in message:
            return 'timeout'
        return 'provider_error'

    @classmethod
    def from_exception(cls, exc):
        response = getattr(exc, 'response', None)
        headers = getattr(response, 'headers', {}) or {}
        value = headers.get('Retry-After') or headers.get('retry-after')
        delay = None
        if value:
            try:
                delay = max(0, float(value))
            except (ValueError, TypeError):
                try:
                    delay = max(0, (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds())
                except (ValueError, TypeError):
                    pass
        message = str(exc)
        if delay is not None:
            message += f" retryDelay: '{delay:g}s'"
        return cls(message, retry_after=delay)

    @property
    def retry_after_seconds(self) -> float | None:
        if self.retry_after is not None:
            return self.retry_after
        match = re.search(r"retryDelay['\"]?\s*:\s*['\"]?(\d+(?:\.\d+)?)s", str(self))
        return float(match[1]) if match else None

    @property
    def daily_quota_exhausted(self) -> bool:
        return bool(re.search(r'requestsperday|requests_per_day|perdayperproject', str(self), re.IGNORECASE))

    @property
    def retryable(self) -> bool:
        # ADK can report SDK failures as events rather than exceptions.
        if self.category in ('RPD', 'spending_limit', 'model_allocation') or (self.retry_after_seconds or 0) > 60:
            return False
        return bool(re.search(r'\b(?:429|500|502|503|504|UNAVAILABLE|RESOURCE_EXHAUSTED|DEADLINE_EXCEEDED)\b', str(self)))


class MeteredGemini(Gemini):
    """One SDK attempt per model request; orchestrator owns bounded retries."""
    agent_name: str = ''
    metrics: Any = None

    async def generate_content_async(self, llm_request, stream=False):
        async with request_slot():
            cooldown = provider_cooldown(self.model) if config.settings.provider_cooldown_enabled else None
            if cooldown:
                category, delay = cooldown
                raise InvestigationProviderError(f'{category} quota cooldown active; retryDelay: {delay:g}s')
            started = time.perf_counter()
            entry = {'event': 'gemini_request', 'agent': self.agent_name, 'model': self.model,
                     'request_count': 1, 'input_tokens': None, 'output_tokens': None, 'error_category': None}
            try:
                async with aclosing(super().generate_content_async(llm_request, stream)) as responses:
                    async for response in responses:
                        usage = getattr(response, 'usage_metadata', None)
                        if usage:
                            entry['input_tokens'] = getattr(usage, 'prompt_token_count', None)
                            entry['output_tokens'] = getattr(usage, 'candidates_token_count', None)
                        if getattr(response, 'error_message', None):
                            failure = InvestigationProviderError(response.error_message)
                            entry['error_category'] = failure.category
                            save_cooldown(self.model, failure)
                        yield response
            except Exception as exc:
                failure = InvestigationProviderError.from_exception(exc)
                entry['error_category'] = failure.category
                save_cooldown(self.model, failure)
                raise failure from exc
            except BaseException:
                entry['error_category'] = 'cancelled'
                raise
            finally:
                entry['latency_ms'] = round((time.perf_counter() - started) * 1000, 2)
                if self.metrics is not None:
                    self.metrics.append(entry)
                logger.info('gemini_request', extra={'usage': entry})


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
        self.request_metrics = []

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
        return MeteredGemini(model=self.model_name, agent_name=spec.name,
                            metrics=self.request_metrics, retry_options=types.HttpRetryOptions(attempts=1))

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

    async def run(
        self,
        spec: AgentSpec,
        prompt: str,
        image_parts: list["types.Part"] | None = None,
    ) -> dict[str, Any]:
        agent = self.build_agent(spec)
        app_name = f"factorymind-{spec.name}"
        user_id = "investigation"
        session_id = f"{spec.name}-{uuid.uuid4().hex}"
        session_service = InMemorySessionService()
        runner = Runner(app_name=app_name, agent=agent, session_service=session_service)
        await session_service.create_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        )

        parts = [types.Part(text=prompt)]
        if image_parts:
            parts.extend(image_parts)
        try:
            events = runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=types.Content(role="user", parts=parts),
                run_config=RunConfig(max_llm_calls=config.settings.gemini_max_model_calls),
            )
            # Close the stream in the same task on provider errors/timeouts;
            # deferred async-generator finalization can detach tracing context
            # in another task and produce misleading secondary exceptions.
            async with aclosing(events):
                async for event in events:
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
            raise InvestigationProviderError.from_exception(exc) from exc

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

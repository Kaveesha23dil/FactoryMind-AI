"""Shared agent specification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel


@dataclass(frozen=True)
class AgentSpec:
    """Everything the runtime needs to execute one logical agent."""

    name: str
    label: str
    instruction: str
    output_schema: type[BaseModel]
    build_prompt: Callable[[dict[str, Any]], str]

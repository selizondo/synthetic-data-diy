"""
P1-diy LLM client — thin adapter that wires Logfire+Langfuse observability
into llm_utils calls via the obs_fn hook.

All retry logic, backoff, and client caching live in llm_utils.client.
"""

from typing import Type, TypeVar

from llm_utils.client import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    chat_complete,  # noqa: F401 — re-exported for phase3_benchmark.py
)
from llm_utils.client import (
    instructor_complete as _instructor_complete,
)
from llm_utils.client import (
    judge_batch as _judge_batch,
)
from llm_utils.client import (
    judge_binary as _judge_binary,
)
from pydantic import BaseModel

from observability import record_llm_generation

T = TypeVar("T", bound=BaseModel)


def _make_obs_fn(obs_context: dict | None, name: str):
    """Return an obs_fn that routes into record_llm_generation."""
    if obs_context is None:
        return None

    def obs_fn(*, model, input_messages, output, duration_ms, error=None, extra_attributes=None):
        output_serialized = output.model_dump() if hasattr(output, "model_dump") else str(output) if output is not None else None
        record_llm_generation(
            obs_context=obs_context,
            name=name,
            model=model,
            input_messages=input_messages,
            output=output_serialized,
            duration_ms=duration_ms,
            error=error,
            extra_attributes=extra_attributes or {},
        )

    return obs_fn


def instructor_complete(
    messages: list[dict],
    response_model: Type[T],
    model: str,
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    max_retries: int = DEFAULT_MAX_RETRIES,
    obs_context: dict | None = None,
    name: str = "instructor_complete",
) -> T:
    return _instructor_complete(
        messages,
        response_model,
        model,
        temperature=temperature,
        max_tokens=max_tokens,
        max_retries=max_retries,
        obs_fn=_make_obs_fn(obs_context, name),
    )


def judge_binary(
    prompt: str,
    model: str,
    default_on_error: int = 0,
    obs_context: dict | None = None,
    name: str = "judge_binary",
) -> int:
    return _judge_binary(
        prompt,
        model,
        default_on_error=default_on_error,
        obs_fn=_make_obs_fn(obs_context, name),
    )


def judge_batch(
    prompt: str,
    response_model: Type[T],
    model: str,
    max_retries: int = DEFAULT_MAX_RETRIES,
    obs_context: dict | None = None,
) -> T:
    name = f"phase{obs_context.get('phase', '?')}.judge_batch" if obs_context else "judge_batch"
    return _judge_batch(
        prompt,
        response_model,
        model,
        max_retries=max_retries,
        obs_fn=_make_obs_fn(obs_context, name),
    )

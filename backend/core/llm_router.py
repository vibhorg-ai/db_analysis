"""
LLM router v5: AMAIZ-only. Session init and payload via AmaizService.

- Creates session on first use.
- Supports flow_name override: chat uses AMAIZ_CHAT_FLOW_NAME, pipeline uses AMAIZ_FLOW_NAME.
- Streaming with automatic fallback to non-streaming on transient errors.
- Session reset and retry on 409 (session-in-use), 504, and timeout errors.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from amaiz_framework_sdk.apis.services.runtime.modules.genaiapp_runtime_sessions.v1.models.models import (
    GenaiAppRuntimeSessionRunInput,
)

from backend.core.config import get_settings
from backend.core.amaiz_service import AmaizService
from backend.core.circuit_breaker import CircuitOpenError, get_amaiz_circuit

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BACKOFF = [5, 10, 15]


def _is_session_contention(exc: Exception) -> bool:
    """Return True if the error is 409 'session is in use' from AMAIZ."""
    msg = str(exc).lower()
    return "409" in msg and "session" in msg


def _is_gateway_timeout(exc: Exception) -> bool:
    """Return True if the error is 504 Gateway Timeout / upstream timeout from AMAIZ."""
    msg = str(exc).lower()
    return "504" in msg or "gateway timeout" in msg or ("upstream" in msg and "timeout" in msg)


def _normalize_messages(messages: list[dict[str, str]] | str) -> list[dict[str, str]]:
    """Normalize input to a list of message dicts with role and content."""
    if isinstance(messages, str):
        return [{"role": "user", "content": messages}]
    return list(messages)


def _messages_to_single_content(msg_list: list[dict[str, str]]) -> str:
    """Convert message list to a single content string for the LLM prompt."""
    parts = []
    for m in msg_list:
        role = (m.get("role") or "user").strip()
        content = (m.get("content") or "").strip()
        if not content:
            continue
        if role == "system":
            parts.append(f"=== SYSTEM INSTRUCTIONS ===\n{content}\n=== END SYSTEM INSTRUCTIONS ===")
        elif role == "assistant":
            parts.append(f"ASSISTANT: {content}")
        else:
            parts.append(f"USER: {content}")
    return "\n\n".join(parts)


def _prepare_instruction_and_context(
    msg_list: list[dict[str, str]], flow_name: str | None = None
) -> tuple[str, str]:
    """Return (instruction, context_str) for the AMAIZ payload.

    For chat flow:
      - context_str = system prompt (schema, health, reports) → sent as context_data
      - instruction  = FULL message blob (system + conversation) → sent as user_input

    This ensures the model always receives context in user_input (works with any
    template), and ALSO receives it in context_data (for templates that use it).

    For non-chat flows: everything in instruction, context_str empty.
    """
    chat_flow = get_settings().AMAIZ_CHAT_FLOW_NAME
    use_chat_split = flow_name and flow_name.strip().lower() == chat_flow.strip().lower()

    if use_chat_split and len(msg_list) > 1:
        first = msg_list[0]
        if (first.get("role") or "").strip().lower() == "system":
            context_str = (first.get("content") or "").strip()
            # instruction = full blob so user_input always has context
            instruction = _messages_to_single_content(msg_list)
            return (instruction.strip(), context_str)

    if len(msg_list) == 1:
        return (msg_list[0].get("content", "").strip(), "")
    content = _messages_to_single_content(msg_list)
    return (content.strip(), "")


class LLMRouter:
    """
    AMAIZ-only LLM interface.

    flow_name can be overridden per call:
      - Chat endpoint uses settings.AMAIZ_CHAT_FLOW_NAME
      - Pipeline agents use settings.AMAIZ_FLOW_NAME
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._amaiz = AmaizService()
        self._session_id: str | None = None

    async def _ensure_session(self) -> str:
        """Check circuit breaker, init session if needed, retry up to 3 times with backoff."""
        get_amaiz_circuit().check()
        if not self._settings.amaiz_configured:
            raise RuntimeError(
                "AMAIZ is not configured. Set AMAIZ_TENANT_ID, AMAIZ_BASE_URL, "
                "AMAIZ_API_KEY, AMAIZ_GENAIAPP_RUNTIME_ID in .env"
            )
        if self._session_id is None:
            last_err: Exception | None = None
            for attempt in range(MAX_RETRIES):
                try:
                    self._session_id = await self._amaiz.session_init()
                    get_amaiz_circuit().record_success()
                    return self._session_id
                except Exception as e:
                    get_amaiz_circuit().record_failure()
                    last_err = e
                    wait = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)]
                    logger.warning(
                        "AMAIZ session init failed (attempt %d/%d): %s. Retrying in %ds...",
                        attempt + 1,
                        MAX_RETRIES,
                        e,
                        wait,
                    )
                    await asyncio.sleep(wait)
            raise RuntimeError(
                f"AMAIZ session init failed after {MAX_RETRIES} attempts: {last_err}"
            ) from last_err
        return self._session_id

    def _build_payload(
        self, instruction: str, context_str: str, flow_name: str | None = None
    ) -> GenaiAppRuntimeSessionRunInput:
        resolved_flow = flow_name or self._settings.AMAIZ_FLOW_NAME
        context_key = self._settings.AMAIZ_CONTEXT_KEY
        logger.info(
            "AMAIZ payload: flow=%s, instruction_len=%d, context_len=%d",
            resolved_flow,
            len(instruction),
            len(context_str),
        )
        return self._amaiz.prepare_str_context_payload(
            resolved_flow,
            context_key,
            context_str,
            instruction or "Please analyze.",
        )

    async def _generate_with_flow(
        self,
        instruction: str,
        context_str: str,
        flow_name: str | None,
    ) -> str:
        """Run generate against a specific flow with retry logic. Raises on failure."""
        last_err: Exception | None = None
        for attempt in range(MAX_RETRIES):
            session_id = await self._ensure_session()
            payload = self._build_payload(instruction, context_str, flow_name)
            try:
                out = await self._amaiz.get_answer(payload, session_id)
                get_amaiz_circuit().record_success()
                return out
            except CircuitOpenError:
                raise
            except Exception as e:
                last_err = e
                is_contention = _is_session_contention(e)
                is_504 = _is_gateway_timeout(e)
                is_timeout = isinstance(
                    e, (httpx.ReadTimeout, httpx.ConnectTimeout, asyncio.TimeoutError)
                )

                if is_contention:
                    logger.warning(
                        "AMAIZ 409 session-in-use (attempt %d/%d) — creating new session after backoff",
                        attempt + 1,
                        MAX_RETRIES,
                    )
                elif is_504:
                    get_amaiz_circuit().record_failure()
                    logger.warning(
                        "AMAIZ 504 upstream timeout (attempt %d/%d) — creating new session after backoff",
                        attempt + 1,
                        MAX_RETRIES,
                    )
                elif is_timeout:
                    logger.warning(
                        "AMAIZ timeout (attempt %d/%d) — creating new session after backoff",
                        attempt + 1,
                        MAX_RETRIES,
                    )
                    get_amaiz_circuit().record_failure()
                else:
                    get_amaiz_circuit().record_failure()
                    self._session_id = None
                    raise

                self._session_id = None
                if attempt < MAX_RETRIES - 1:
                    wait = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)]
                    logger.info("Waiting %ds before retry...", wait)
                    await asyncio.sleep(wait)

        self._session_id = None
        raise last_err  # type: ignore[misc]

    async def generate(
        self,
        messages: list[dict[str, str]] | str,
        flow_name: str | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Generate a completion via AMAIZ (non-streaming).

        Retries on 409 (session-in-use), 504, and timeout by creating a fresh
        session with exponential backoff. Circuit breaker integration.

        If the configured pipeline flow fails and is NOT the chat flow, falls
        back to the chat flow automatically (handles AMAIZ flow misconfiguration).
        """
        msg_list = _normalize_messages(messages)
        if not msg_list:
            return ""
        instruction, context_str = _prepare_instruction_and_context(msg_list, flow_name)
        if not instruction and not context_str:
            return ""

        resolved_flow = flow_name or self._settings.AMAIZ_FLOW_NAME
        chat_flow = self._settings.AMAIZ_CHAT_FLOW_NAME
        is_chat = resolved_flow.strip().lower() == chat_flow.strip().lower()

        try:
            return await self._generate_with_flow(instruction, context_str, flow_name)
        except CircuitOpenError:
            raise
        except Exception as primary_err:
            if is_chat:
                raise

            logger.warning(
                "Pipeline flow '%s' failed (%s). Falling back to chat flow '%s'.",
                resolved_flow,
                primary_err,
                chat_flow,
            )
            self._session_id = None
            try:
                result = await self._generate_with_flow(
                    instruction, context_str, chat_flow
                )
                logger.info(
                    "Fallback to chat flow '%s' succeeded.", chat_flow
                )
                return result
            except Exception as fallback_err:
                logger.error(
                    "Fallback to chat flow also failed: %s", fallback_err
                )
                raise primary_err from fallback_err

    async def generate_stream(
        self,
        messages: list[dict[str, str]] | str,
        flow_name: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """
        Stream completion chunks via AMAIZ.
        Falls back to non-streaming on transient errors.
        """
        msg_list = _normalize_messages(messages)
        if not msg_list:
            return
        instruction, context_str = _prepare_instruction_and_context(msg_list, flow_name)
        if not instruction and not context_str:
            return

        session_id = await self._ensure_session()
        payload = self._build_payload(instruction, context_str, flow_name)

        try:
            chunk_count = 0
            async for chunk in self._amaiz.stream_answer(payload, session_id):
                chunk_count += 1
                yield chunk
            get_amaiz_circuit().record_success()
            logger.info("AMAIZ stream completed: %d chunks", chunk_count)
        except CircuitOpenError:
            raise
        except (httpx.ReadTimeout, httpx.RemoteProtocolError) as stream_err:
            get_amaiz_circuit().record_failure()
            logger.warning(
                "AMAIZ stream failed (%s), falling back to non-streaming",
                type(stream_err).__name__,
            )
            self._session_id = None
            session_id = await self._ensure_session()
            payload = self._build_payload(instruction, context_str, flow_name)
            result = await self._amaiz.get_answer(payload, session_id)
            get_amaiz_circuit().record_success()
            yield result
        except Exception as e:
            get_amaiz_circuit().record_failure()
            raise

"""
AMAIZ service: session init, payload preparation, and LLM run/stream.

Uses backend.core.config.get_settings() for AMAIZ credentials and timeout.
Requires amaiz_sdk and amaiz_framework_sdk.

IMPORTANT: The AMAIZ SDK reads HTTPX_REQUEST_TIMEOUT from os.environ (default 5s).
We set it from our config before constructing any SDK objects.
"""

from __future__ import annotations

import contextlib
import io
import logging
import os
import sys
from typing import Any, AsyncGenerator

from pydantic import ValidationError

from amaiz_sdk.apis.models import ServiceConfiguration
from amaiz_sdk.apis.runtime.modules.genaiapps import get_genaiapp_runtimes_service
from amaiz_sdk.apis.runtime.modules.genaiapp_runtimes_sessions import get_genaiappruntime_session_service
from amaiz_framework_sdk.infra.apiclient.configuration import (
    APiKeySecurityConfiguration,
    SecurityConfigurationType,
)
from amaiz_framework_sdk.apis.services.runtime.modules.genaiapps.v1.models.models import GenaiAppRuntimeFindById
from amaiz_framework_sdk.apis.services.runtime.modules.genaiapp_runtime_sessions.v1.models.models import (
    Execution,
    ExecutionInputParams,
    ExecutionMessage,
    FlowRef,
    GenaiAppRuntimeInitialExecutionLevel,
    GenaiAppRuntimePartialRef,
    GenaiAppRuntimeSessionCreate,
    GenaiAppRuntimeSessionInit,
    GenaiAppRuntimeSessionRunInput,
    GenaiAppRuntimeSessionRun,
)

from backend.core.config import get_settings

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def _suppress_sdk_trace_noise():
    """Suppress AMAIZ SDK trace validation errors printed to stderr.

    The SDK's response model includes trace_info with discriminated-union event types.
    When the server sends newer trace types the SDK doesn't know about, Pydantic prints
    validation-error lines to stderr. These are harmless (the actual LLM response.message
    is unaffected) but flood the console. Capture stderr during SDK calls.
    """
    buf = io.StringIO()
    old_stderr = sys.stderr
    sys.stderr = buf
    try:
        yield
    finally:
        sys.stderr = old_stderr
        captured = buf.getvalue()
        if captured:
            lines = captured.strip().splitlines()
            logger.debug(
                "Suppressed %d lines of SDK trace-validation noise (harmless)",
                len(lines),
            )


def _ensure_timeout_env() -> None:
    """Set HTTPX_REQUEST_TIMEOUT from config before SDK constructs ApiClient."""
    settings = get_settings()
    timeout_str = str(settings.HTTPX_REQUEST_TIMEOUT)
    os.environ["HTTPX_REQUEST_TIMEOUT"] = timeout_str
    logger.info("HTTPX_REQUEST_TIMEOUT env var set to %s", timeout_str)


class AmaizService:
    """AMAIZ session and LLM invocation via GenAI app runtime."""

    def __init__(self) -> None:
        _ensure_timeout_env()
        settings = get_settings()
        self._settings = settings
        self._service_config = ServiceConfiguration(
            base_url=settings.AMAIZ_BASE_URL,
            security=APiKeySecurityConfiguration(
                type=SecurityConfigurationType.API_KEY,
                key=settings.AMAIZ_API_KEY,
            ),
        )
        self._runtime_service = get_genaiapp_runtimes_service(self._service_config)
        self._session_service = get_genaiappruntime_session_service(self._service_config)

    async def session_init(self) -> str:
        """Create a new AMAIZ session and return session_id."""
        settings = self._settings
        tenant_masked = (settings.AMAIZ_TENANT_ID[:8] + "...") if len(settings.AMAIZ_TENANT_ID) > 8 else "***"
        runtime_masked = (
            (settings.AMAIZ_GENAIAPP_RUNTIME_ID[:12] + "...")
            if len(settings.AMAIZ_GENAIAPP_RUNTIME_ID) > 12
            else "***"
        )
        logger.info(
            "Initializing AMAIZ session (tenant=%s, runtime=%s, base_url=%s)",
            tenant_masked,
            runtime_masked,
            settings.AMAIZ_BASE_URL,
        )
        genaiapp_response: GenaiAppRuntimeFindById = await self._runtime_service.genai_app_runtime_find_by_id(
            settings.AMAIZ_TENANT_ID,
            settings.AMAIZ_GENAIAPP_RUNTIME_ID,
        )
        if not genaiapp_response or not getattr(genaiapp_response, "response", None):
            raise RuntimeError("GenAI runtime not found")
        response = genaiapp_response.response
        runtime_id = getattr(response, "id", None) or settings.AMAIZ_GENAIAPP_RUNTIME_ID
        logger.info("GenAI runtime app found")
        session_payload = GenaiAppRuntimeSessionInit(
            genaiapp_runtime=GenaiAppRuntimePartialRef(id=runtime_id),
            execution_state=GenaiAppRuntimeInitialExecutionLevel(
                execution_level="GENAIAPP",
                validate_language=False,
            ),
        )
        session_response: GenaiAppRuntimeSessionCreate = await self._session_service.genai_app_runtime_session_create(
            settings.AMAIZ_TENANT_ID,
            False,
            False,
            session_payload,
        )
        session_id = session_response.response.id
        logger.info("AMAIZ session created: %s", session_id)
        return session_id

    def prepare_str_context_payload(
        self,
        flow_name: str,
        context_key: str,
        context_value: str,
        prompt: str,
    ) -> GenaiAppRuntimeSessionRunInput:
        """Build payload for LLM run: flow name, context key/value, and user prompt."""
        return GenaiAppRuntimeSessionRunInput(
            execution=Execution(flow=FlowRef(name=flow_name)),
            user_input=ExecutionMessage(message_type="STRING", message=prompt),
            input_params=ExecutionInputParams(root={context_key: context_value}),
        )

    def prepare_dict_context_payload(
        self,
        flow_name: str,
        context: dict[str, Any],
        prompt: str,
    ) -> GenaiAppRuntimeSessionRunInput:
        """Build payload with dict context (input_params.root = context)."""
        return GenaiAppRuntimeSessionRunInput(
            execution=Execution(flow=FlowRef(name=flow_name)),
            user_input=ExecutionMessage(message_type="STRING", message=prompt),
            input_params=ExecutionInputParams(root=context),
        )

    async def get_answer(self, payload: GenaiAppRuntimeSessionRunInput, session_id: str) -> str:
        """Run session with payload and return final message text (non-streaming)."""
        logger.debug(
            "AMAIZ get_answer: session=%s, flow=%s, prompt_len=%d",
            session_id,
            payload.execution.flow.name if payload.execution and payload.execution.flow else "?",
            len(payload.user_input.message) if payload.user_input else 0,
        )
        try:
            with _suppress_sdk_trace_noise():
                llm_answer: GenaiAppRuntimeSessionRun = await self._session_service.genai_app_runtime_session_run(
                    self._settings.AMAIZ_TENANT_ID,
                    session_id,
                    False,
                    payload,
                )
        except ValidationError as ve:
            logger.warning(
                "SDK ValidationError (%d errors) — attempting raw response extraction",
                ve.error_count(),
            )
            return self._extract_message_from_validation_error(ve)

        if llm_answer.response.message is None:
            execution_info = llm_answer.response.execution_info
            if execution_info is not None:
                error_details = getattr(execution_info, "error_details", None)
                error_message = getattr(error_details, "error_message", str(execution_info))
                logger.error("AMAIZ error: %s", error_message)
                raise RuntimeError(f"AMAIZ execution error: {error_message}")
            raise RuntimeError("AMAIZ returned no message and no error details")
        return llm_answer.response.message.message or ""

    @staticmethod
    def _extract_message_from_validation_error(ve: ValidationError) -> str:
        """Extract LLM message from raw input when SDK model validation fails."""
        try:
            raw = ve.errors()[0].get("input") if ve.errors() else None
            if isinstance(raw, dict):
                msg = raw.get("response", {}).get("message", {}).get("message", "")
                if msg:
                    logger.info("Recovered LLM message (%d chars) from raw response", len(msg))
                    return str(msg)
        except Exception:
            pass

        try:
            ctx = ve.errors()[0].get("ctx", {}) if ve.errors() else {}
            raw_input = ctx.get("input")
            if isinstance(raw_input, dict):
                msg = raw_input.get("response", {}).get("message", {}).get("message", "")
                if msg:
                    return str(msg)
        except Exception:
            pass

        logger.error("Could not extract message from SDK ValidationError")
        raise RuntimeError(
            "AMAIZ SDK validation error — could not parse response. "
            "Version mismatch between SDK and server."
        )

    async def stream_answer(
        self,
        payload: GenaiAppRuntimeSessionRunInput,
        session_id: str,
    ) -> AsyncGenerator[str, None]:
        """Stream LLM response chunks as strings."""
        logger.debug(
            "AMAIZ stream_answer: session=%s, flow=%s",
            session_id,
            payload.execution.flow.name if payload.execution and payload.execution.flow else "?",
        )
        with _suppress_sdk_trace_noise():
            async for chunk in self._session_service.genai_app_runtime_session_run_stream(
                self._settings.AMAIZ_TENANT_ID,
                session_id,
                False,
                payload,
            ):
                msg = getattr(chunk, "response", None)
                if msg is None:
                    continue
                exec_msg = getattr(msg, "message", None)
                if exec_msg is None:
                    continue
                text = getattr(exec_msg, "message", None)
                if text:
                    yield str(text)

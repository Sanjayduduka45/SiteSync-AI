"""
Gemini + LangChain AI Provider Service — SiteSync AI Phase 5.
Handles prompt formatting, Gemini LLM invocation via LangChain, structured JSON parsing,
and Pydantic v2 schema validation.

Invariants:
  - Isolated provider service: no database access, no Supabase queries, no persistent writes.
  - Zero trust of LLM for raw_input_id: trusted parent ID is strictly injected by the service.
  - Fail-safe & clean error boundaries: distinguishes configuration, provider, timeout, and parsing errors.
  - Production never silently returns fake mock data on provider failure.
  - API keys and provider credentials are strictly guarded and never exposed in logs or error messages.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import date, datetime, timezone
from typing import Any, Callable
from uuid import UUID

from app.ai.prompts.extraction_v1 import (
    EXTRACTION_PROMPT_VERSION,
    SYSTEM_INSTRUCTION,
    build_extraction_prompt,
)
from app.core.config import get_settings
from app.schemas.extractions import ExtractedActivity, ExtractionResult

logger = logging.getLogger(__name__)


# Controlled Provider Exceptions
class GeminiConfigurationError(Exception):
    """Raised when GEMINI_API_KEY or model configuration is missing."""


class GeminiProviderError(Exception):
    """Raised when the upstream Gemini LLM provider fails."""


class GeminiTimeoutError(GeminiProviderError):
    """Raised when LLM invocation exceeds the timeout threshold."""


class GeminiExtractionParseError(Exception):
    """Raised when LLM response is malformed JSON or fails Pydantic schema validation."""


class GeminiService:
    """Isolated LLM provider service using LangChain and Google Gemini."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        temperature: float = 0.1,
        timeout: float = 15.0,
        max_retries: int = 2,
        mock_provider: Callable[..., Any] | None = None,
    ) -> None:
        settings = get_settings()
        self._api_key = api_key if api_key is not None else settings.gemini_api_key
        self.model = model or settings.gemini_model or "gemini-3.6-flash"
        self.temperature = temperature
        self.timeout = timeout
        self.max_retries = max_retries
        self.prompt_version = EXTRACTION_PROMPT_VERSION
        self._mock_provider = mock_provider

    @property
    def model_version_string(self) -> str:
        return f"{self.model}:{self.prompt_version}"

    async def extract_structured_data(
        self,
        raw_input_id: UUID,
        raw_text: str,
        field_date: date | str | None = None,
        input_type: str = "text",
        title: str | None = None,
        fake_response: dict[str, Any] | str | None = None,
    ) -> ExtractionResult:
        """
        Renders versioned prompt, calls Gemini via LangChain, parses JSON, and validates into ExtractionResult.
        """
        if not raw_text or not raw_text.strip():
            raise ValueError("Cannot extract structured data from empty raw text")

        prompt = build_extraction_prompt(
            raw_text=raw_text,
            field_date=field_date,
            input_type=input_type,
            title=title,
        )

        raw_json_str: str

        # 1. Check for explicit test fake_response or injected mock_provider
        if fake_response is not None:
            if isinstance(fake_response, dict):
                raw_json_str = json.dumps(fake_response)
            else:
                raw_json_str = str(fake_response)
        elif self._mock_provider is not None:
            raw_json_str = await self._invoke_mock(prompt, raw_text)
        else:
            # 2. Production path: Requires valid API Key and calls real Gemini via LangChain
            if not self._api_key or not self._api_key.strip():
                raise GeminiConfigurationError("GEMINI_API_KEY is not configured on the backend server")

            raw_json_str = await self._invoke_gemini_with_retry(prompt)

        # 3. Parse JSON and validate against Pydantic schema
        return self._parse_and_validate(raw_json_str, raw_input_id)

    async def _invoke_mock(self, prompt: str, raw_text: str) -> str:
        """Executes test mock provider."""
        if asyncio.iscoroutinefunction(self._mock_provider):
            res = await self._mock_provider(prompt, raw_text)
        else:
            res = self._mock_provider(prompt, raw_text)
        if isinstance(res, dict):
            return json.dumps(res)
        return str(res)

    async def _invoke_gemini_with_retry(self, prompt: str) -> str:
        """
        Invokes Gemini with exponential backoff on transient errors (429, 503, timeout).
        """
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_google_genai import ChatGoogleGenerativeAI

        llm = ChatGoogleGenerativeAI(
            model=self.model,
            google_api_key=self._api_key,
            temperature=self.temperature,
            timeout=self.timeout,
            max_retries=0,  # Controlled manually below for deterministic backoff
        )

        messages = [
            SystemMessage(content=SYSTEM_INSTRUCTION),
            HumanMessage(content=prompt),
        ]

        attempt = 0
        backoff_delay = 1.0

        while True:
            attempt += 1
            try:
                coro = llm.ainvoke(messages)
                response = await asyncio.wait_for(coro, timeout=self.timeout)
                content = response.content
                if isinstance(content, list):
                    text_parts: list[str] = []
                    for part in content:
                        if isinstance(part, str):
                            text_parts.append(part)
                        elif isinstance(part, dict) and "text" in part:
                            text_parts.append(str(part["text"]))
                    return "".join(text_parts)
                return str(content)

            except asyncio.TimeoutError as err:
                logger.warning(f"Gemini request timed out after {self.timeout}s (attempt {attempt}/{self.max_retries + 1})")
                if attempt > self.max_retries:
                    raise GeminiTimeoutError(f"Gemini LLM request timed out after {self.timeout}s") from err
                await asyncio.sleep(backoff_delay)
                backoff_delay *= 2

            except Exception as err:
                err_msg = str(err)
                # Check for transient rate limit (429) or service overload (503)
                is_transient = "429" in err_msg or "ResourceExhausted" in err_msg or "503" in err_msg or "Unavailable" in err_msg
                if is_transient and attempt <= self.max_retries:
                    logger.warning(f"Transient Gemini failure (attempt {attempt}/{self.max_retries + 1}): {err_msg[:100]}")
                    await asyncio.sleep(backoff_delay)
                    backoff_delay *= 2
                    continue

                # Sanitize error message to prevent accidental key exposure
                safe_msg = re.sub(r"key=[^&\s]+", "key=[REDACTED]", err_msg)
                logger.error(f"Gemini LLM invocation failed: {safe_msg}")
                raise GeminiProviderError(f"Gemini LLM invocation failed: {safe_msg}") from err

    def _parse_and_validate(self, json_str: str, raw_input_id: UUID) -> ExtractionResult:
        """
        Strips markdown wrappers, parses JSON, injects authoritative metadata,
        and runs strict Pydantic v2 validation.
        """
        cleaned = json_str.strip()
        # Robustly strip markdown code fences (including indented fences)
        lines = [line.strip() for line in cleaned.splitlines()]
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as err:
            raise GeminiExtractionParseError(f"Failed to parse LLM response as valid JSON: {str(err)}") from err

        if not isinstance(data, dict):
            raise GeminiExtractionParseError(f"Expected JSON object from LLM extraction, received {type(data).__name__}")

        # Inject server-authoritative fields (never trusted from LLM)
        payload = {
            "raw_input_id": str(raw_input_id),
            "extracted_activities": data.get("extracted_activities", []),
            "extraction_confidence": data.get("extraction_confidence", 0.0),
            "model_version": self.model_version_string,
            "processing_timestamp": datetime.now(timezone.utc).isoformat(),
        }

        try:
            return ExtractionResult.model_validate(payload)
        except Exception as val_err:
            raise GeminiExtractionParseError(f"LLM extraction output failed Pydantic validation: {str(val_err)}") from val_err


# Singleton instance configured with environment defaults
gemini_service = GeminiService()

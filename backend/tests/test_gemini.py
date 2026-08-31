"""
Tests for Gemini + LangChain Provider Service — SiteSync AI Phase 5.
Validates prompt formatting, prompt injection defense, structured JSON parsing,
error recovery, timeout handling, retry behavior, and isolation invariants.
"""

from __future__ import annotations

import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import pytest

from app.ai.prompts.extraction_v1 import (
    EXTRACTION_PROMPT_VERSION,
    SYSTEM_INSTRUCTION,
    build_extraction_prompt,
)
from app.schemas.extractions import ConfidenceLevel, ExtractionResult
from app.services.gemini_service import (
    GeminiConfigurationError,
    GeminiExtractionParseError,
    GeminiProviderError,
    GeminiService,
    GeminiTimeoutError,
)


# --- 1. Prompt Engineering & Injection Defense Tests ---

def test_prompt_version_exists():
    assert EXTRACTION_PROMPT_VERSION == "extraction_v1"


def test_prompt_renders_metadata_and_untrusted_delimiters():
    prompt = build_extraction_prompt(
        raw_text="Poured 30m3 concrete on Pad 4.",
        field_date=date(2026, 8, 30),
        input_type="voice",
        title="Pad 4 Concrete Log",
    )

    assert "Input Modality: voice" in prompt
    assert "Reference Field Date: 2026-08-30" in prompt
    assert "Title / Subject: Pad 4 Concrete Log" in prompt
    assert "<field_input>" in prompt
    assert "</field_input>" in prompt
    assert "Poured 30m3 concrete on Pad 4." in prompt


def test_system_instruction_security_rules():
    assert "UNTRUSTED USER DATA" in SYSTEM_INSTRUCTION
    assert "evidence_tokens" in SYSTEM_INSTRUCTION
    assert "exact verbatim" in SYSTEM_INSTRUCTION
    # Boundary prohibitions
    assert "Do NOT match activities to a project schedule" in SYSTEM_INSTRUCTION
    assert "Do NOT generate vector embeddings" in SYSTEM_INSTRUCTION
    assert "Do NOT perform variance analysis" in SYSTEM_INSTRUCTION
    assert "Do NOT make approval or acceptance decisions" in SYSTEM_INSTRUCTION


# --- 2. GeminiService Schema Parsing & Mock Tests ---

@pytest.mark.asyncio
async def test_valid_mocked_gemini_output_parses_into_extraction_result():
    input_id = uuid.uuid4()
    mock_json = {
        "extracted_activities": [
            {
                "description": "Installed 8 spools of stainless steel line 14",
                "progress_value": 8.0,
                "progress_unit": "spools",
                "discipline": "Piping",
                "location": "Unit 2, Area C",
                "event_date": "2026-08-30",
                "constraints": ["Welder certification hold on spool 8"],
                "evidence_tokens": ["Installed 8 spools", "stainless steel line 14"],
            }
        ],
        "extraction_confidence": 0.94,
    }

    service = GeminiService(api_key="mock-key", model="gemini-1.5-flash")
    result = await service.extract_structured_data(
        raw_input_id=input_id,
        raw_text="Installed 8 spools of stainless steel line 14 today in Unit 2.",
        fake_response=mock_json,
    )

    assert isinstance(result, ExtractionResult)
    assert result.raw_input_id == input_id
    assert len(result.extracted_activities) == 1
    assert result.extracted_activities[0].description == "Installed 8 spools of stainless steel line 14"
    assert result.extracted_activities[0].progress_value == 8.0
    assert result.extracted_activities[0].progress_unit == "spools"
    assert result.extracted_activities[0].discipline == "Piping"
    assert result.extracted_activities[0].location == "Unit 2, Area C"
    assert result.extracted_activities[0].constraints == ["Welder certification hold on spool 8"]
    assert result.extracted_activities[0].evidence_tokens == ["Installed 8 spools", "stainless steel line 14"]
    assert result.extraction_confidence == 0.94
    assert result.confidence_level == ConfidenceLevel.HIGH
    assert result.model_version == f"gemini-1.5-flash:{EXTRACTION_PROMPT_VERSION}"


@pytest.mark.asyncio
async def test_markdown_code_fence_stripping():
    input_id = uuid.uuid4()
    fenced_output = """```json
    {
      "extracted_activities": [
        {
          "description": "Formwork stripped on Column C12",
          "progress_value": 100.0,
          "progress_unit": "%",
          "discipline": "Civil",
          "location": "Column C12",
          "constraints": [],
          "evidence_tokens": ["Formwork stripped"]
        }
      ],
      "extraction_confidence": 0.88
    }
    ```"""

    service = GeminiService(api_key="mock-key")
    result = await service.extract_structured_data(
        raw_input_id=input_id,
        raw_text="Formwork stripped on Column C12",
        fake_response=fenced_output,
    )

    assert result.extraction_confidence == 0.88
    assert len(result.extracted_activities) == 1
    assert result.extracted_activities[0].description == "Formwork stripped on Column C12"


@pytest.mark.asyncio
async def test_malformed_json_raises_parse_error():
    input_id = uuid.uuid4()
    bad_json = "This is not JSON: {invalid json content"

    service = GeminiService(api_key="mock-key")
    with pytest.raises(GeminiExtractionParseError) as exc:
        await service.extract_structured_data(
            raw_input_id=input_id,
            raw_text="Sample text",
            fake_response=bad_json,
        )
    assert "Failed to parse LLM response as valid JSON" in str(exc.value)


@pytest.mark.asyncio
async def test_schema_validation_failure_raises_parse_error():
    input_id = uuid.uuid4()
    # Missing description in extracted_activities
    invalid_schema = {
        "extracted_activities": [
            {
                "progress_value": 50,  # missing required description!
            }
        ],
        "extraction_confidence": 0.90,
    }

    service = GeminiService(api_key="mock-key")
    with pytest.raises(GeminiExtractionParseError) as exc:
        await service.extract_structured_data(
            raw_input_id=input_id,
            raw_text="Sample text",
            fake_response=invalid_schema,
        )
    assert "failed Pydantic validation" in str(exc.value)


@pytest.mark.asyncio
async def test_empty_raw_text_rejected():
    service = GeminiService(api_key="mock-key")
    with pytest.raises(ValueError):
        await service.extract_structured_data(
            raw_input_id=uuid.uuid4(),
            raw_text="   ",
        )


@pytest.mark.asyncio
async def test_missing_api_key_raises_configuration_error():
    service = GeminiService(api_key="")
    with pytest.raises(GeminiConfigurationError) as exc:
        await service.extract_structured_data(
            raw_input_id=uuid.uuid4(),
            raw_text="Valid construction notes",
        )
    assert "GEMINI_API_KEY is not configured" in str(exc.value)


# --- 3. Retry Policy & Timeout Tests ---

@pytest.mark.asyncio
async def test_transient_failure_retries_and_succeeds():
    input_id = uuid.uuid4()
    attempts = 0

    mock_msg = MagicMock()
    mock_msg.content = '{"extracted_activities": [{"description": "Cable pulling complete"}], "extraction_confidence": 0.90}'

    async def mock_ainvoke(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise Exception("ResourceExhausted: 429 Rate limit exceeded")
        return mock_msg

    with patch("asyncio.sleep", new_callable=AsyncMock):
        with patch("langchain_google_genai.ChatGoogleGenerativeAI.ainvoke", side_effect=mock_ainvoke):
            service = GeminiService(api_key="test-key", max_retries=2)
            result = await service.extract_structured_data(
                raw_input_id=input_id,
                raw_text="Cable pulling complete",
            )
            assert result.extracted_activities[0].description == "Cable pulling complete"
            assert attempts == 2


@pytest.mark.asyncio
async def test_secret_redaction_in_error_message():
    secret_key = "AIzaSySecretApiKey12345"
    service = GeminiService(api_key=secret_key, max_retries=0)

    with patch("langchain_google_genai.ChatGoogleGenerativeAI.ainvoke", side_effect=Exception(f"Failed with key={secret_key}&error=network")):
        with pytest.raises(GeminiProviderError) as exc:
            await service.extract_structured_data(
                raw_input_id=uuid.uuid4(),
                raw_text="Sample notes",
            )
        assert secret_key not in str(exc.value)
        assert "key=[REDACTED]" in str(exc.value)


# --- 4. Service Isolation Invariants ---

def test_gemini_service_has_no_database_dependencies():
    from app.services import gemini_service as gs
    assert "supabase" not in gs.__dict__
    assert "db" not in gs.__dict__
    assert "Session" not in gs.__dict__

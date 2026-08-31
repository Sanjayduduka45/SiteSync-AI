"""
Tests for Domain Extraction Service & Database Persistence — SiteSync AI Phase 5.
Validates input eligibility, project isolation, Gemini invocation, server-authoritative fields,
deterministic normalization, exact evidence verification, real public.ai_extractions repository persistence,
concurrency-safe idempotent re-runs, and boundary rules.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, patch
import uuid
from uuid import UUID
import pytest
import httpx

from app.schemas.extractions import (
    ConfidenceLevel,
    ExtractedActivity,
    ExtractionResponse,
    ExtractionResult,
    ExtractionStatus,
)
from app.schemas.inputs import FieldInputType, TextInputCreate, TranscriptionStatus
from app.services.extraction_service import (
    AIExtractionRepository,
    CrossProjectInputError,
    EvidenceVerificationError,
    ExtractionInputError,
    ExtractionNotFoundError,
    ExtractionService,
    extraction_service,
)
from app.services.gemini_service import GeminiProviderError, GeminiService
from app.services.input_service import input_service


@pytest.fixture(autouse=True)
def clean_services():
    """Ensure clean isolated state before every test."""
    input_service.clear()
    extraction_service.clear()
    yield
    input_service.clear()
    extraction_service.clear()


# --- 1. Input Eligibility & Validation Tests ---

@pytest.mark.asyncio
async def test_text_input_with_valid_raw_text_succeeds():
    project_id = "proj-test-01"
    user_id = str(uuid.uuid4())

    text_input = input_service.create_text_input(
        project_id=project_id,
        data=TextInputCreate(
            title="Piping Rack 3",
            raw_text="Piping crew erected 4 spools in Rack 3 today.",
            field_date=date(2026, 8, 30),
        ),
        submitted_by_id=user_id,
    )

    mock_llm_json = {
        "extracted_activities": [
            {
                "description": "Erected 4 spools in Rack 3",
                "progress_value": 4.0,
                "progress_unit": "spools",
                "discipline": "piping",
                "location": "Rack 3",
                "event_date": "2026-08-30",
                "constraints": [],
                "evidence_tokens": ["erected 4 spools in Rack 3"],
            }
        ],
        "extraction_confidence": 0.95,
    }

    result = await extraction_service.extract_and_persist(
        project_id=project_id,
        field_input_id=text_input.id,
        fake_response=mock_llm_json,
    )

    assert result.status == ExtractionStatus.COMPLETED
    assert result.project_id == project_id
    assert result.field_input_id == text_input.id
    assert result.confidence_score == 0.95
    assert len(result.extracted_data.get("extracted_activities", [])) == 1
    assert result.extracted_data["extracted_activities"][0]["discipline"] == "Piping"


@pytest.mark.asyncio
async def test_blank_raw_text_rejected():
    project_id = "proj-test-01"
    input_id = str(uuid.uuid4())
    input_service._inputs[input_id] = {
        "id": input_id,
        "project_id": project_id,
        "submitted_by": str(uuid.uuid4()),
        "input_type": FieldInputType.TEXT,
        "title": "Empty note",
        "raw_text": "   ",
        "media_path": None,
        "media_filename": None,
        "media_mime_type": None,
        "media_size_bytes": 0,
        "audio_duration_seconds": None,
        "transcription_status": TranscriptionStatus.NONE,
        "transcription_error": None,
        "field_date": date(2026, 8, 30),
        "metadata": {},
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    with pytest.raises(ExtractionInputError) as exc:
        await extraction_service.extract_and_persist(
            project_id=project_id,
            field_input_id=input_id,
        )
    assert "contains no text content" in str(exc.value)


@pytest.mark.asyncio
async def test_voice_with_completed_transcript_succeeds():
    project_id = "proj-test-01"
    user_id = str(uuid.uuid4())

    voice_input = await input_service.create_media_input(
        project_id=project_id,
        input_type=FieldInputType.VOICE,
        filename="site_memo.wav",
        file_bytes=b"RIFFdummywavbytesdata",
        content_type="audio/wav",
        submitted_by_id=user_id,
        title="Voice update",
    )

    mock_llm_json = {
        "extracted_activities": [
            {
                "description": "Completed pipe spool erection on Line 24",
                "progress_value": 100.0,
                "progress_unit": "%",
                "discipline": "piping",
                "location": "Rack 3 area",
                "evidence_tokens": ["Completed pipe spool erection on Line 24"],
            }
        ],
        "extraction_confidence": 0.90,
    }

    result = await extraction_service.extract_and_persist(
        project_id=project_id,
        field_input_id=voice_input.id,
        fake_response=mock_llm_json,
    )

    assert result.status == ExtractionStatus.COMPLETED
    assert result.field_input_id == voice_input.id


@pytest.mark.asyncio
async def test_voice_without_completed_transcript_rejected():
    project_id = "proj-test-01"
    input_id = str(uuid.uuid4())
    input_service._inputs[input_id] = {
        "id": input_id,
        "project_id": project_id,
        "submitted_by": str(uuid.uuid4()),
        "input_type": FieldInputType.VOICE,
        "title": "Voice note",
        "raw_text": None,
        "media_path": "projects/proj-test-01/inputs/1/audio.wav",
        "media_filename": "audio.wav",
        "media_mime_type": "audio/wav",
        "media_size_bytes": 1024,
        "audio_duration_seconds": 12.0,
        "transcription_status": TranscriptionStatus.PENDING,
        "transcription_error": None,
        "field_date": date(2026, 8, 30),
        "metadata": {},
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    with pytest.raises(ExtractionInputError) as exc:
        await extraction_service.extract_and_persist(
            project_id=project_id,
            field_input_id=input_id,
        )
    assert "transcription is not completed" in str(exc.value)


@pytest.mark.asyncio
async def test_photo_and_document_without_caption_rejected():
    project_id = "proj-test-01"
    user_id = str(uuid.uuid4())

    photo_input = await input_service.create_media_input(
        project_id=project_id,
        input_type=FieldInputType.PHOTO,
        filename="site_photo.jpg",
        file_bytes=b"\xff\xd8\xff\xe0dummyjpgbytes",
        content_type="image/jpeg",
        submitted_by_id=user_id,
        raw_text=None,
    )

    with pytest.raises(ExtractionInputError) as exc:
        await extraction_service.extract_and_persist(
            project_id=project_id,
            field_input_id=photo_input.id,
        )
    assert "no accompanying text notes" in str(exc.value)


# --- 2. Project Isolation & Boundary Tests ---

@pytest.mark.asyncio
async def test_cross_project_field_input_rejected():
    project_a = "proj-alpha"
    project_b = "proj-beta"
    user_id = str(uuid.uuid4())

    input_in_a = input_service.create_text_input(
        project_id=project_a,
        data=TextInputCreate(raw_text="Alpha project work"),
        submitted_by_id=user_id,
    )

    # Attempt to extract input from Project A under Project B context
    with pytest.raises(CrossProjectInputError) as exc:
        await extraction_service.extract_and_persist(
            project_id=project_b,
            field_input_id=input_in_a.id,
        )
    assert "does not belong to project" in str(exc.value)


@pytest.mark.asyncio
async def test_nonexistent_field_input_raises_not_found():
    with pytest.raises(ExtractionNotFoundError):
        await extraction_service.extract_and_persist(
            project_id="proj-alpha",
            field_input_id=str(uuid.uuid4()),
        )


# --- 3. Server-Authoritative Metadata Enforcement Tests ---

@pytest.mark.asyncio
async def test_gemini_hallucinated_raw_input_id_is_overwritten():
    project_id = "proj-test-01"
    user_id = str(uuid.uuid4())
    correct_input = input_service.create_text_input(
        project_id=project_id,
        data=TextInputCreate(raw_text="Poured 50 cubic meters concrete foundation."),
        submitted_by_id=user_id,
    )

    attacker_invented_id = str(uuid.uuid4())
    mock_llm_json = {
        "raw_input_id": attacker_invented_id,
        "extracted_activities": [
            {
                "description": "Poured 50 cubic meters concrete foundation",
                "progress_value": 50.0,
                "progress_unit": "cubic meters",
                "discipline": "civil",
                "evidence_tokens": ["Poured 50 cubic meters"],
            }
        ],
        "extraction_confidence": 0.96,
        "model_version": "attacker-fake-model-v99",
    }

    result = await extraction_service.extract_and_persist(
        project_id=project_id,
        field_input_id=correct_input.id,
        fake_response=mock_llm_json,
    )

    assert result.field_input_id == correct_input.id
    assert result.extracted_data["raw_input_id"] == correct_input.id
    assert result.model_version == "gemini-1.5-flash:extraction_v1"


# --- 4. Deterministic Normalization Tests ---

@pytest.mark.asyncio
async def test_normalization_applied_to_extracted_data():
    project_id = "proj-test-01"
    inp = input_service.create_text_input(
        project_id=project_id,
        data=TextInputCreate(raw_text="Pulled 300 linear feet of cable and erected 10 spools of pipework."),
        submitted_by_id=str(uuid.uuid4()),
    )

    mock_llm_json = {
        "extracted_activities": [
            {
                "description": "Pulled 300 linear feet of cable",
                "progress_value": 300.0,
                "progress_unit": "linear feet",
                "discipline": "electrical works",
                "evidence_tokens": ["Pulled 300 linear feet"],
            },
            {
                "description": "Erected 10 spools of pipework",
                "progress_value": 10.0,
                "progress_unit": "spool",
                "discipline": "pipework",
                "evidence_tokens": ["erected 10 spools"],
            }
        ],
        "extraction_confidence": 0.92,
    }

    result = await extraction_service.extract_and_persist(
        project_id=project_id,
        field_input_id=inp.id,
        fake_response=mock_llm_json,
    )

    activities = result.extracted_data["extracted_activities"]
    assert activities[0]["progress_unit"] == "LF"
    assert activities[0]["discipline"] == "Electrical"
    assert activities[1]["progress_unit"] == "spools"
    assert activities[1]["discipline"] == "Piping"


# --- 5. Evidence Token Exact Substring Verification Tests ---

@pytest.mark.asyncio
async def test_valid_exact_evidence_token_passes():
    project_id = "proj-test-01"
    inp = input_service.create_text_input(
        project_id=project_id,
        data=TextInputCreate(raw_text="Welded joint J-401 on Rack 2."),
        submitted_by_id=str(uuid.uuid4()),
    )

    mock_llm_json = {
        "extracted_activities": [
            {
                "description": "Welded joint J-401 on Rack 2",
                "progress_value": 1.0,
                "progress_unit": "joint",
                "discipline": "piping",
                "evidence_tokens": ["Welded joint J-401 on Rack 2"],
            }
        ],
        "extraction_confidence": 0.98,
    }

    result = await extraction_service.extract_and_persist(
        project_id=project_id,
        field_input_id=inp.id,
        fake_response=mock_llm_json,
    )
    assert result.status == ExtractionStatus.COMPLETED


@pytest.mark.asyncio
async def test_invalid_hallucinated_evidence_token_blocks_completed_status():
    project_id = "proj-test-01"
    inp = input_service.create_text_input(
        project_id=project_id,
        data=TextInputCreate(raw_text="Welded joint J-401 on Rack 2."),
        submitted_by_id=str(uuid.uuid4()),
    )

    mock_llm_json = {
        "extracted_activities": [
            {
                "description": "Welded joint J-401 on Rack 2",
                "progress_value": 1.0,
                "progress_unit": "joints",
                "discipline": "Piping",
                "evidence_tokens": ["Installed flange F-10"],
            }
        ],
        "extraction_confidence": 0.90,
    }

    with pytest.raises(EvidenceVerificationError) as exc:
        await extraction_service.extract_and_persist(
            project_id=project_id,
            field_input_id=inp.id,
            fake_response=mock_llm_json,
        )
    assert "is not an exact substring" in str(exc.value)

    stored_ext = await extraction_service.get_extraction_by_input(project_id, inp.id)
    assert stored_ext is not None
    assert stored_ext.status == ExtractionStatus.FAILED
    assert "Evidence verification failed" in (stored_ext.error_message or "")


# --- 6. Concurrency-Safe Idempotency & Persistence Tests ---

@pytest.mark.asyncio
async def test_repeated_extraction_updates_existing_record_idempotently():
    project_id = "proj-test-01"
    inp = input_service.create_text_input(
        project_id=project_id,
        data=TextInputCreate(raw_text="Excavated trench for drainage Line D1."),
        submitted_by_id=str(uuid.uuid4()),
    )

    mock_llm_json_1 = {
        "extracted_activities": [
            {
                "description": "Excavated trench for Line D1",
                "progress_value": 50.0,
                "progress_unit": "%",
                "discipline": "civil",
                "evidence_tokens": ["Excavated trench"],
            }
        ],
        "extraction_confidence": 0.80,
    }

    res_1 = await extraction_service.extract_and_persist(
        project_id=project_id,
        field_input_id=inp.id,
        fake_response=mock_llm_json_1,
    )

    mock_llm_json_2 = {
        "extracted_activities": [
            {
                "description": "Excavated trench for Line D1 completely",
                "progress_value": 100.0,
                "progress_unit": "%",
                "discipline": "civil",
                "evidence_tokens": ["Excavated trench"],
            }
        ],
        "extraction_confidence": 0.95,
    }

    res_2 = await extraction_service.extract_and_persist(
        project_id=project_id,
        field_input_id=inp.id,
        fake_response=mock_llm_json_2,
    )

    assert res_1.id == res_2.id
    assert res_2.confidence_score == 0.95
    list_res = await extraction_service.list_extractions(project_id)
    assert list_res.total == 1


@pytest.mark.asyncio
async def test_concurrent_duplicate_persistence_maintains_exactly_one_row():
    """Simulates parallel concurrent extraction executions for the same (project_id, field_input_id)."""
    project_id = "proj-test-01"
    inp = input_service.create_text_input(
        project_id=project_id,
        data=TextInputCreate(raw_text="Installed foundation rebar on Grid A."),
        submitted_by_id=str(uuid.uuid4()),
    )

    mock_llm_json = {
        "extracted_activities": [
            {
                "description": "Installed foundation rebar on Grid A",
                "progress_value": 100.0,
                "progress_unit": "%",
                "discipline": "civil",
                "evidence_tokens": ["Installed foundation rebar"],
            }
        ],
        "extraction_confidence": 0.95,
    }

    # Execute 5 concurrent extractions simultaneously
    tasks = [
        extraction_service.extract_and_persist(
            project_id=project_id,
            field_input_id=inp.id,
            fake_response=mock_llm_json,
        )
        for _ in range(5)
    ]
    results = await asyncio.gather(*tasks)

    # All executions must resolve to the identical extraction ID
    first_id = results[0].id
    for res in results:
        assert res.id == first_id

    # Database/repository must contain exactly ONE logical row
    list_res = await extraction_service.list_extractions(project_id)
    assert list_res.total == 1


@pytest.mark.asyncio
async def test_failed_extraction_followed_by_successful_rerun_updates_same_record():
    """Validates that a failed extraction is updated in-place when re-run successfully."""
    project_id = "proj-test-01"
    inp = input_service.create_text_input(
        project_id=project_id,
        data=TextInputCreate(raw_text="Cable pulling in Tray T-100."),
        submitted_by_id=str(uuid.uuid4()),
    )

    # 1. First run fails due to invalid evidence token
    invalid_llm_json = {
        "extracted_activities": [
            {
                "description": "Cable pulling",
                "progress_value": 50.0,
                "progress_unit": "%",
                "discipline": "electrical",
                "evidence_tokens": ["Nonexistent text in raw_text"],
            }
        ],
        "extraction_confidence": 0.50,
    }

    with pytest.raises(EvidenceVerificationError):
        await extraction_service.extract_and_persist(
            project_id=project_id,
            field_input_id=inp.id,
            fake_response=invalid_llm_json,
        )

    failed_rec = await extraction_service.get_extraction_by_input(project_id, inp.id)
    assert failed_rec is not None
    assert failed_rec.status == ExtractionStatus.FAILED

    # 2. Re-run with valid extraction
    valid_llm_json = {
        "extracted_activities": [
            {
                "description": "Cable pulling in Tray T-100",
                "progress_value": 100.0,
                "progress_unit": "%",
                "discipline": "electrical",
                "evidence_tokens": ["Cable pulling in Tray T-100"],
            }
        ],
        "extraction_confidence": 0.95,
    }

    success_rec = await extraction_service.extract_and_persist(
        project_id=project_id,
        field_input_id=inp.id,
        fake_response=valid_llm_json,
    )

    assert success_rec.id == failed_rec.id
    assert success_rec.status == ExtractionStatus.COMPLETED
    assert success_rec.error_message is None

    list_res = await extraction_service.list_extractions(project_id)
    assert list_res.total == 1


@pytest.mark.asyncio
async def test_field_input_remains_strictly_immutable():
    project_id = "proj-test-01"
    original_text = "Poured 100 m3 foundation concrete on Substation 4."
    inp = input_service.create_text_input(
        project_id=project_id,
        data=TextInputCreate(
            title="Substation 4 Log",
            raw_text=original_text,
            field_date=date(2026, 8, 30),
        ),
        submitted_by_id=str(uuid.uuid4()),
    )

    mock_llm_json = {
        "extracted_activities": [
            {
                "description": "Poured 100 m3 foundation concrete",
                "progress_value": 100.0,
                "progress_unit": "m3",
                "discipline": "civil",
                "evidence_tokens": ["Poured 100 m3 foundation concrete"],
            }
        ],
        "extraction_confidence": 0.99,
    }

    await extraction_service.extract_and_persist(
        project_id=project_id,
        field_input_id=inp.id,
        fake_response=mock_llm_json,
    )

    persisted_input = input_service.get_input(project_id, inp.id)
    assert persisted_input is not None
    assert persisted_input.raw_text == original_text
    assert persisted_input.title == "Substation 4 Log"
    assert persisted_input.field_date == date(2026, 8, 30)


@pytest.mark.asyncio
async def test_gemini_failure_records_failed_status_and_preserves_input():
    project_id = "proj-test-01"
    inp = input_service.create_text_input(
        project_id=project_id,
        data=TextInputCreate(raw_text="Site inspection notes"),
        submitted_by_id=str(uuid.uuid4()),
    )

    failing_service = GeminiService(api_key="mock-key")

    async def fail_mock(prompt, raw_text):
        raise GeminiProviderError("Upstream API 503 Service Unavailable")

    failing_service._mock_provider = fail_mock
    custom_extraction_service = ExtractionService(gemini_provider=failing_service)

    with pytest.raises(GeminiProviderError):
        await custom_extraction_service.extract_and_persist(
            project_id=project_id,
            field_input_id=inp.id,
        )

    stored = await custom_extraction_service.get_extraction_by_input(project_id, inp.id)
    assert stored is not None
    assert stored.status == ExtractionStatus.FAILED
    assert "AI Provider Error" in (stored.error_message or "")

    persisted_input = input_service.get_input(project_id, inp.id)
    assert persisted_input is not None
    assert persisted_input.raw_text == "Site inspection notes"


@pytest.mark.asyncio
async def test_ai_extractions_repository_supabase_rest_upsert_integration():
    """Validates that AIExtractionRepository uses PostgREST on_conflict upsert semantics when configured."""
    repo = AIExtractionRepository()
    project_id = "proj-test-01"
    field_input_id = str(uuid.uuid4())
    extraction = ExtractionResult(
        raw_input_id=UUID(field_input_id),
        extracted_activities=[
            ExtractedActivity(
                description="Installed pipe",
                progress_value=1.0,
                progress_unit="m",
                discipline="Piping",
                evidence_tokens=["Installed pipe"],
            )
        ],
        extraction_confidence=0.95,
        model_version="gemini-1.5-flash:extraction_v1",
    )

    with patch("app.services.extraction_service.get_settings") as mock_settings:
        mock_settings.return_value.supabase_url = "https://example.supabase.co"
        mock_settings.return_value.supabase_service_role_key = "service-role-secret-key"
        mock_settings.return_value.is_development = False

        mock_post_resp = AsyncMock(spec=httpx.Response)
        mock_post_resp.status_code = 201
        mock_post_resp.text = '{"id": "ext-123"}'
        mock_post_resp.json.return_value = [
            {
                "id": "ext-123",
                "project_id": project_id,
                "field_input_id": field_input_id,
                "status": "completed",
                "extracted_data": extraction.model_dump(mode="json"),
                "confidence_score": 0.95,
                "model_version": "gemini-1.5-flash:extraction_v1",
                "error_message": None,
                "created_at": "2026-08-30T12:00:00Z",
                "updated_at": "2026-08-30T12:00:00Z",
            }
        ]

        with patch("httpx.AsyncClient.post", return_value=mock_post_resp) as mock_post:
            res = await repo.upsert_completed(project_id, field_input_id, extraction)
            assert res["id"] == "ext-123"
            assert mock_post.called
            call_args = mock_post.call_args
            url = call_args[0][0]
            assert url == "https://example.supabase.co/rest/v1/ai_extractions?on_conflict=project_id,field_input_id"
            headers = call_args[1]["headers"]
            assert headers["apikey"] == "service-role-secret-key"
            assert headers["Authorization"] == "Bearer service-role-secret-key"
            assert "resolution=merge-duplicates" in headers["Prefer"]


# --- 7. Boundary Rule Verification Tests ---

def test_extraction_service_has_no_phase6_dependencies():
    from app.services import extraction_service as es
    module_code = open(es.__file__).read()
    for forbidden in [
        "pgvector",
        "embeddings",
        "schedule_match",
        "similarity",
        "rerank",
        "approved_actual",
        "variance",
        "critical_path",
        "risk_engine",
    ]:
        assert f"import {forbidden}" not in module_code

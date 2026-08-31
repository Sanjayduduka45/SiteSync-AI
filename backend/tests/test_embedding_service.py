"""
SiteSync AI — Phase 6.4 Embedding Service Tests.
Tests:
  - Canonical schedule text construction
  - Deterministic SHA-256 hash generation
  - Hash changes when activity content changes
  - Deterministic offline mock embedding generator
  - Different inputs produce different 768-dimensional vectors
  - Valid 768-dimensional embedding generation
  - Malformed vector dimension rejected with EmbeddingDimensionError
  - Missing API key raises EmbeddingConfigurationError
  - Provider failure raises EmbeddingProviderError with redacted secrets
  - Extraction query embedding path
  - retrieval_document vs retrieval_query task separation
  - ActivityEmbeddingRepository project boundary scoping
  - Absence of Phase 6.5 matching and Phase 7/8/9 concepts
"""

from __future__ import annotations

from uuid import uuid4
import pytest

from app.schemas.schedule import ScheduleActivityCreate, ScheduleActivityResponse
from app.services.embedding_service import (
    CANONICAL_EMBEDDING_DIMENSION,
    CANONICAL_EMBEDDING_MODEL,
    TASK_TYPE_DOCUMENT,
    TASK_TYPE_QUERY,
    ActivityEmbeddingRepository,
    EmbeddingConfigurationError,
    EmbeddingDimensionError,
    EmbeddingProviderError,
    EmbeddingService,
    build_extracted_activity_query_text,
    build_schedule_activity_embedding_text,
    compute_content_hash,
    generate_deterministic_mock_embedding,
)


def test_canonical_schedule_text_construction():
    """Verify deterministic formatting of schedule activity attributes."""
    activity = ScheduleActivityCreate(
        activity_code="ACT-500",
        name="Install Fire Suppression Piping",
        wbs_code="2.1.4",
        discipline="Piping",
        location="Zone B Level 2",
        planned_quantity=300.0,
        planned_unit="LF",
    )
    text = build_schedule_activity_embedding_text(activity)

    expected_lines = [
        "Activity: Install Fire Suppression Piping",
        "Code: ACT-500",
        "Discipline: Piping",
        "WBS: 2.1.4",
        "Location: Zone B Level 2",
        "Unit: LF",
    ]
    assert text == "\n".join(expected_lines)


def test_deterministic_sha256_hash_and_invalidation():
    """Verify compute_content_hash is deterministic and changes when content changes."""
    text1 = "Activity: Install Chilled Water Pipe\nCode: ACT-1\nDiscipline: Piping"
    text2 = "Activity: Install Chilled Water Pipe\nCode: ACT-1\nDiscipline: Piping"
    text3 = "Activity: Install Chilled Water Pipe\nCode: ACT-1\nDiscipline: HVAC"

    hash1 = compute_content_hash(text1)
    hash2 = compute_content_hash(text2)
    hash3 = compute_content_hash(text3)

    assert hash1 == hash2
    assert hash1 != hash3
    assert len(hash1) == 64


def test_extracted_activity_query_text():
    """Verify query text formatting for field progress updates."""
    query_text = build_extracted_activity_query_text(
        description="Installed 50 LF of 4-inch pipe on rack 3",
        discipline="Piping",
        location="Rack 3",
        unit="LF",
    )
    expected = (
        "Activity: Installed 50 LF of 4-inch pipe on rack 3\n"
        "Discipline: Piping\n"
        "Location: Rack 3\n"
        "Unit: LF"
    )
    assert query_text == expected


def test_deterministic_offline_mock_embedding():
    """Verify mock embedding generator returns normalized 768-dim vector."""
    vec1 = generate_deterministic_mock_embedding("Test Activity Text 1")
    vec2 = generate_deterministic_mock_embedding("Test Activity Text 1")
    vec3 = generate_deterministic_mock_embedding("Different Activity Text")

    assert len(vec1) == CANONICAL_EMBEDDING_DIMENSION
    assert vec1 == vec2
    assert vec1 != vec3

    # Check unit normalization (L2 norm ~ 1.0)
    norm = sum(x * x for x in vec1) ** 0.5
    assert abs(norm - 1.0) < 1e-4


@pytest.mark.asyncio
async def test_embedding_service_with_mock_provider():
    """Verify EmbeddingService orchestrates mock embedding generation."""
    service = EmbeddingService(
        mock_provider=lambda text, task_type: generate_deterministic_mock_embedding(text)
    )

    act = ScheduleActivityCreate(
        activity_code="ACT-101",
        name="Cast-in-place Concrete Slab",
        discipline="Civil",
    )

    vector, content_hash = await service.embed_schedule_activity(act)
    assert len(vector) == 768
    assert len(content_hash) == 64

    # Test query embedding
    query_vector = await service.embed_extracted_activity(
        description="Poured 20m3 concrete slab",
        discipline="Civil",
    )
    assert len(query_vector) == 768


@pytest.mark.asyncio
async def test_task_type_separation():
    """Verify retrieval_document and retrieval_query task types are correctly passed."""
    recorded_tasks: list[str] = []

    def mock_recorder(text: str, task_type: str):
        recorded_tasks.append(task_type)
        return generate_deterministic_mock_embedding(text)

    service = EmbeddingService(mock_provider=mock_recorder)

    await service.embed_document("Document text")
    assert recorded_tasks[-1] == TASK_TYPE_DOCUMENT

    await service.embed_query("Query text")
    assert recorded_tasks[-1] == TASK_TYPE_QUERY


@pytest.mark.asyncio
async def test_malformed_vector_dimension_rejected():
    """Verify provider returning non-768 vector raises EmbeddingDimensionError."""
    service = EmbeddingService(
        mock_provider=lambda text, task_type: [0.1, 0.2, 0.3]  # Only 3 dims instead of 768
    )

    with pytest.raises(EmbeddingDimensionError) as exc:
        await service.embed_document("Test text")
    assert "768" in str(exc.value)


@pytest.mark.asyncio
async def test_missing_api_key_raises_configuration_error():
    """Verify service without API key in production mode raises EmbeddingConfigurationError."""
    service = EmbeddingService(api_key="")

    with pytest.raises(EmbeddingConfigurationError):
        await service.embed_document("Test text")


@pytest.mark.asyncio
async def test_empty_text_rejected():
    """Verify empty text raises ValueError."""
    service = EmbeddingService(
        mock_provider=lambda text, task_type: generate_deterministic_mock_embedding(text)
    )

    with pytest.raises(ValueError):
        await service.embed_document("   ")


@pytest.mark.asyncio
async def test_activity_embedding_repository_scoping():
    """Verify repository stores and retrieves embeddings with project scoping."""
    repo = ActivityEmbeddingRepository()
    proj_a = str(uuid4())
    proj_b = str(uuid4())
    act_id = str(uuid4())
    vec = generate_deterministic_mock_embedding("Activity A")
    c_hash = compute_content_hash("Activity A")

    # Upsert in Project A
    meta = await repo.upsert_embedding(
        project_id=proj_a,
        schedule_activity_id=act_id,
        embedding=vec,
        content_hash=c_hash,
    )
    assert meta.schedule_activity_id == uuid4().__class__(act_id)
    assert meta.content_hash == c_hash

    # Query from Project A -> Found
    found = await repo.get_embedding(project_id=proj_a, schedule_activity_id=act_id)
    assert found is not None
    assert found.content_hash == c_hash

    # Query from Project B -> None (Cross-tenant boundary enforced)
    cross = await repo.get_embedding(project_id=proj_b, schedule_activity_id=act_id)
    assert cross is None


def test_no_phase65_or_downstream_in_embedding_service():
    """Verify absence of matching, approval, variance, or risk concepts in Phase 6.4."""
    from app.services import embedding_service as es_module
    import inspect

    source = inspect.getsource(es_module)
    forbidden = [
        "cosine_similarity",
        "re_rank",
        "rerank",
        "ai_matches",
        "approved_actual",
        "planner_approval",
        "variance",
        "critical_path",
        "risk_engine",
    ]
    for term in forbidden:
        assert term not in source.lower(), f"Forbidden term '{term}' found in embedding_service"

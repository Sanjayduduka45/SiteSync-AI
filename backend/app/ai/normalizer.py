"""
Deterministic Normalization Layer — SiteSync AI Phase 5.
Standardizes units of measurement, trade disciplines, and formatting for extracted construction activities.

Invariants:
  - 100% deterministic (pure Python functions).
  - No LLM, no LangChain, no external network calls.
  - Preserves verbatim evidence tokens and numerical progress values.
  - Unknown units and disciplines are safely preserved without distortion.
"""

from __future__ import annotations

from app.schemas.extractions import ExtractedActivity, ExtractionResult

# Canonical Unit Mapping (Normalized lower string -> Standard canonical label)
UNIT_ALIASES: dict[str, str] = {
    # Length
    "m": "m",
    "meter": "m",
    "meters": "m",
    "metre": "m",
    "metres": "m",
    "lf": "LF",
    "linear foot": "LF",
    "linear feet": "LF",
    "foot": "LF",
    "feet": "LF",
    "ft": "LF",
    # Volume
    "m3": "m3",
    "m³": "m3",
    "cubic meter": "m3",
    "cubic meters": "m3",
    "cubic metre": "m3",
    "cubic metres": "m3",
    "cy": "CY",
    "yd3": "CY",
    "yd³": "CY",
    "cubic yard": "CY",
    "cubic yards": "CY",
    # Area
    "m2": "m2",
    "m²": "m2",
    "sqm": "m2",
    "square meter": "m2",
    "square meters": "m2",
    "sf": "SF",
    "ft2": "SF",
    "ft²": "SF",
    "sqft": "SF",
    "square foot": "SF",
    "square feet": "SF",
    # Percentage
    "%": "%",
    "percent": "%",
    "percentage": "%",
    # Construction counts & weight
    "spool": "spools",
    "spools": "spools",
    "ton": "tons",
    "tons": "tons",
    "tonne": "tons",
    "tonnes": "tons",
    "joint": "joints",
    "joints": "joints",
    "ea": "ea",
    "each": "ea",
    "piece": "ea",
    "pieces": "ea",
}

# Canonical Discipline Mapping (Normalized lower string -> Title Case canonical trade)
DISCIPLINE_ALIASES: dict[str, str] = {
    "piping": "Piping",
    "pipe": "Piping",
    "piping works": "Piping",
    "pipework": "Piping",
    "civil": "Civil",
    "civil works": "Civil",
    "concrete": "Civil",
    "earthworks": "Civil",
    "structural": "Structural",
    "structural works": "Structural",
    "steel": "Structural",
    "structural steel": "Structural",
    "electrical": "Electrical",
    "electrical works": "Electrical",
    "e&i": "Electrical",
    "mechanical": "Mechanical",
    "mechanical works": "Mechanical",
    "equipment": "Mechanical",
    "instrumentation": "Instrumentation",
    "instrumentation works": "Instrumentation",
    "scaffolding": "Scaffolding",
    "scaffold": "Scaffolding",
    "painting": "Painting/Insulation",
    "coating": "Painting/Insulation",
    "insulation": "Painting/Insulation",
}


def normalize_unit(unit: str | None) -> str | None:
    """
    Deterministically normalizes a construction unit string to canonical notation.
    Returns:
      - None if unit is None or empty/whitespace.
      - Canonical symbol (e.g. 'm', 'LF', 'm3', 'CY', '%', 'spools', 'tons') if known.
      - Stripped original string if unknown (avoids destructive false mapping).
    """
    if unit is None:
        return None
    cleaned = unit.strip()
    if not cleaned:
        return None
    key = cleaned.lower()
    return UNIT_ALIASES.get(key, cleaned)


def normalize_discipline(discipline: str | None) -> str | None:
    """
    Deterministically standardizes trade discipline names to canonical Title Case.
    Returns:
      - None if discipline is None or empty/whitespace.
      - Canonical title (e.g. 'Piping', 'Civil', 'Electrical') if known.
      - Stripped original string if unknown.
    """
    if discipline is None:
        return None
    cleaned = discipline.strip()
    if not cleaned:
        return None
    key = cleaned.lower()
    return DISCIPLINE_ALIASES.get(key, cleaned)


def normalize_activity(activity: ExtractedActivity) -> ExtractedActivity:
    """
    Returns a new ExtractedActivity with normalized unit and discipline fields.
    Guarantees that descriptions, progress quantities, locations, dates, constraints,
    and verbatim evidence tokens remain untouched.
    """
    normalized_u = normalize_unit(activity.progress_unit)
    normalized_d = normalize_discipline(activity.discipline)
    normalized_loc = activity.location.strip() if activity.location else None

    return ExtractedActivity(
        description=activity.description,
        progress_value=activity.progress_value,
        progress_unit=normalized_u,
        discipline=normalized_d,
        location=normalized_loc,
        event_date=activity.event_date,
        constraints=list(activity.constraints),
        evidence_tokens=list(activity.evidence_tokens),
    )


def normalize_extraction(result: ExtractionResult) -> ExtractionResult:
    """
    Normalizes all extracted activities in an ExtractionResult payload.
    Preserves raw_input_id, extraction_confidence, model_version, and processing_timestamp.
    """
    normalized_activities = [normalize_activity(act) for act in result.extracted_activities]

    return ExtractionResult(
        raw_input_id=result.raw_input_id,
        extracted_activities=normalized_activities,
        extraction_confidence=result.extraction_confidence,
        model_version=result.model_version,
        processing_timestamp=result.processing_timestamp,
    )

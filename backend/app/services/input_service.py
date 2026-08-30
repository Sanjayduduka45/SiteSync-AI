"""
Field Input Domain Service — SiteSync AI Phase 4.
Handles creation, listing, retrieval, and deletion of raw field submissions (text, voice, photo, document).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any

from app.schemas.inputs import (
    FieldInputListResponse,
    FieldInputResponse,
    FieldInputType,
    TextInputCreate,
    TranscriptionStatus,
)
from app.services.storage_service import storage_service
from app.services.stt_service import stt_service


class InputService:
    """In-memory & database abstraction service for multi-modal field inputs."""

    def __init__(self) -> None:
        # key: input_id -> input_dict
        self._inputs: dict[str, dict[str, Any]] = {}

    def list_inputs(
        self,
        project_id: str,
        input_type: FieldInputType | None = None,
        field_date: date | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> FieldInputListResponse:
        """List all field inputs for a project with optional type, date, and pagination filters."""
        matched = [
            self._to_response(inp, project_id=project_id)
            for inp in self._inputs.values()
            if inp["project_id"] == project_id
            and (input_type is None or inp["input_type"] == input_type)
            and (field_date is None or inp["field_date"] == field_date)
        ]
        # Sort newest submissions first
        matched.sort(key=lambda x: x.created_at, reverse=True)
        total = len(matched)
        paginated = matched[offset : offset + limit]

        return FieldInputListResponse(
            inputs=paginated,
            total=total,
        )

    def get_input(self, project_id: str, input_id: str) -> FieldInputResponse | None:
        """Get a single field input ensuring project boundary ownership."""
        inp = self._inputs.get(input_id)
        if not inp or inp["project_id"] != project_id:
            return None
        return self._to_response(inp, project_id=project_id)

    def create_text_input(
        self,
        project_id: str,
        data: TextInputCreate,
        submitted_by_id: str,
        submitted_by_email: str | None = None,
    ) -> FieldInputResponse:
        """Create a new raw text submission."""
        now = datetime.now(timezone.utc)
        input_id = str(uuid.uuid4())

        record = {
            "id": input_id,
            "project_id": project_id,
            "submitted_by": submitted_by_id,
            "submitted_by_email": submitted_by_email,
            "input_type": FieldInputType.TEXT,
            "title": data.title,
            "raw_text": data.raw_text,
            "media_path": None,
            "media_filename": None,
            "media_mime_type": None,
            "media_size_bytes": 0,
            "audio_duration_seconds": None,
            "transcription_status": TranscriptionStatus.NONE,
            "transcription_error": None,
            "field_date": getattr(data, "field_date", None) or now.date(),
            "metadata": getattr(data, "metadata", {}) or {},
            "created_at": now,
            "updated_at": now,
        }
        self._inputs[input_id] = record
        return self._to_response(record, project_id=project_id)

    async def create_media_input(
        self,
        project_id: str,
        input_type: FieldInputType,
        filename: str,
        file_bytes: bytes,
        content_type: str,
        submitted_by_id: str,
        submitted_by_email: str | None = None,
        title: str | None = None,
        raw_text: str | None = None,
        field_date: date | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> FieldInputResponse:
        """
        Processes and stores a voice recording, photo, or site document.
        Runs Whisper STT transcription for voice inputs.
        """
        # Validate file size, extension, and MIME type
        storage_service.validate_file(
            input_type=input_type,
            filename=filename,
            content_type=content_type,
            file_size=len(file_bytes),
        )

        now = datetime.now(timezone.utc)
        input_id = str(uuid.uuid4())
        safe_filename = storage_service.sanitize_filename(filename)

        # Upload file to private storage bucket
        media_path = storage_service.upload_file(
            project_id=project_id,
            input_id=input_id,
            filename=safe_filename,
            content=file_bytes,
            content_type=content_type,
        )

        transcription_status = TranscriptionStatus.NONE
        transcription_error = None
        transcribed_text = raw_text

        # If voice input, run isolated Whisper Speech-to-Text
        if input_type == FieldInputType.VOICE:
            transcription_status = TranscriptionStatus.PENDING
            transcript, stt_err = await stt_service.transcribe_audio(
                audio_bytes=file_bytes,
                filename=safe_filename,
                content_type=content_type,
            )
            if stt_err:
                transcription_status = TranscriptionStatus.FAILED
                transcription_error = stt_err
            else:
                transcription_status = TranscriptionStatus.COMPLETED
                transcribed_text = transcript

        record = {
            "id": input_id,
            "project_id": project_id,
            "submitted_by": submitted_by_id,
            "submitted_by_email": submitted_by_email,
            "input_type": input_type,
            "title": title,
            "raw_text": transcribed_text,
            "media_path": media_path,
            "media_filename": safe_filename,
            "media_mime_type": content_type.lower(),
            "media_size_bytes": len(file_bytes),
            "audio_duration_seconds": None,
            "transcription_status": transcription_status,
            "transcription_error": transcription_error,
            "field_date": field_date or now.date(),
            "metadata": metadata or {},
            "created_at": now,
            "updated_at": now,
        }
        self._inputs[input_id] = record
        return self._to_response(record, project_id=project_id)

    def delete_input(self, project_id: str, input_id: str) -> bool:
        """Deletes a field input and removes its storage object."""
        record = self._inputs.get(input_id)
        if not record or record["project_id"] != project_id:
            return False

        # Clean up storage object if present
        if record.get("media_path"):
            storage_service.delete_file(project_id, record["media_path"])

        del self._inputs[input_id]
        return True

    def _to_response(self, r: dict[str, Any], project_id: str) -> FieldInputResponse:
        media_url = None
        if r.get("media_path"):
            try:
                media_url = storage_service.create_signed_url(project_id, r["media_path"])
            except Exception:
                media_url = None

        return FieldInputResponse(
            id=r["id"],
            project_id=r["project_id"],
            submitted_by=r["submitted_by"],
            submitted_by_email=r.get("submitted_by_email"),
            input_type=r["input_type"],
            title=r.get("title"),
            raw_text=r.get("raw_text"),
            media_path=r.get("media_path"),
            media_filename=r.get("media_filename"),
            media_mime_type=r.get("media_mime_type"),
            media_size_bytes=r.get("media_size_bytes", 0),
            media_url=media_url,
            audio_duration_seconds=r.get("audio_duration_seconds"),
            transcription_status=r.get("transcription_status", TranscriptionStatus.NONE),
            transcription_error=r.get("transcription_error"),
            field_date=r["field_date"],
            metadata=r.get("metadata", {}),
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )

    def clear(self) -> None:
        self._inputs.clear()
        storage_service.clear()


input_service = InputService()

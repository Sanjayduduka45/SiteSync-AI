"""
Storage Service for Field Inputs — SiteSync AI Phase 4.
Handles file validation, filename sanitization, object path generation,
and signed URL creation for the private 'field-inputs' Supabase Storage bucket.
"""

from __future__ import annotations

import os
import re
import uuid
from typing import Any
from fastapi import HTTPException, status

from app.core.auth import create_error_response
from app.core.config import get_settings
from app.schemas.inputs import FieldInputType

# Storage Validation Rules per Phase 4.1 Specification
MAX_VOICE_SIZE = 25 * 1024 * 1024      # 25 MB
MAX_PHOTO_SIZE = 15 * 1024 * 1024      # 15 MB
MAX_DOCUMENT_SIZE = 25 * 1024 * 1024   # 25 MB

ALLOWED_VOICE_MIMES = {
    "audio/webm",
    "audio/mp4",
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/ogg",
    "audio/x-m4a",
    "audio/m4a",
    "audio/aac",
}
ALLOWED_VOICE_EXTENSIONS = {".webm", ".mp4", ".mp3", ".wav", ".ogg", ".m4a", ".aac"}

ALLOWED_PHOTO_MIMES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
}
ALLOWED_PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

ALLOWED_DOCUMENT_MIMES = {
    "application/pdf",
    "text/plain",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "text/csv",
}
ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".txt", ".xlsx", ".xls", ".csv"}

STORAGE_BUCKET = "field-inputs"


class StorageService:
    """Service managing upload validations, storage object paths, and signed URLs."""

    def __init__(self) -> None:
        # In-memory storage mock registry for development and test execution
        # key: media_path -> bytes
        self._storage_objects: dict[str, bytes] = {}

    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to prevent path traversal and shell special chars."""
        # Strip directory components
        base = os.path.basename(filename)
        # Separate name and extension
        name, ext = os.path.splitext(base)
        # Replace non-alphanumeric chars (excluding underscores, hyphens)
        clean_name = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
        clean_ext = ext.lower()
        if not clean_name:
            clean_name = f"file_{uuid.uuid4().hex[:8]}"
        return f"{clean_name}{clean_ext}"

    def validate_file(
        self,
        input_type: FieldInputType,
        filename: str,
        content_type: str,
        file_size: int,
    ) -> None:
        """
        Validates that the file conforms strictly to MIME type, extension,
        and maximum size limits for the given input modality.
        Fails closed with HTTPException 400.
        """
        _, ext = os.path.splitext(filename.lower())
        norm_mime = content_type.lower().split(";")[0].strip()

        if input_type == FieldInputType.VOICE:
            if file_size > MAX_VOICE_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=create_error_response(
                        "FILE_TOO_LARGE",
                        f"Voice audio exceeds maximum allowed size of {MAX_VOICE_SIZE // (1024*1024)}MB. Received: {file_size} bytes",
                    ),
                )
            if ext not in ALLOWED_VOICE_EXTENSIONS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=create_error_response(
                        "INVALID_EXTENSION",
                        f"Extension '{ext}' not permitted for voice. Allowed: {sorted(ALLOWED_VOICE_EXTENSIONS)}",
                    ),
                )
            if norm_mime not in ALLOWED_VOICE_MIMES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=create_error_response(
                        "INVALID_MIME_TYPE",
                        f"MIME type '{norm_mime}' not permitted for voice. Allowed: {sorted(ALLOWED_VOICE_MIMES)}",
                    ),
                )

        elif input_type == FieldInputType.PHOTO:
            if file_size > MAX_PHOTO_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=create_error_response(
                        "FILE_TOO_LARGE",
                        f"Photo exceeds maximum allowed size of {MAX_PHOTO_SIZE // (1024*1024)}MB. Received: {file_size} bytes",
                    ),
                )
            if ext not in ALLOWED_PHOTO_EXTENSIONS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=create_error_response(
                        "INVALID_EXTENSION",
                        f"Extension '{ext}' not permitted for photo. Allowed: {sorted(ALLOWED_PHOTO_EXTENSIONS)}",
                    ),
                )
            if norm_mime not in ALLOWED_PHOTO_MIMES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=create_error_response(
                        "INVALID_MIME_TYPE",
                        f"MIME type '{norm_mime}' not permitted for photo. Allowed: {sorted(ALLOWED_PHOTO_MIMES)}",
                    ),
                )

        elif input_type == FieldInputType.DOCUMENT:
            if file_size > MAX_DOCUMENT_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=create_error_response(
                        "FILE_TOO_LARGE",
                        f"Document exceeds maximum allowed size of {MAX_DOCUMENT_SIZE // (1024*1024)}MB. Received: {file_size} bytes",
                    ),
                )
            if ext not in ALLOWED_DOCUMENT_EXTENSIONS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=create_error_response(
                        "INVALID_EXTENSION",
                        f"Extension '{ext}' not permitted for document. Allowed: {sorted(ALLOWED_DOCUMENT_EXTENSIONS)}",
                    ),
                )
            if norm_mime not in ALLOWED_DOCUMENT_MIMES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=create_error_response(
                        "INVALID_MIME_TYPE",
                        f"MIME type '{norm_mime}' not permitted for document. Allowed: {sorted(ALLOWED_DOCUMENT_MIMES)}",
                    ),
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=create_error_response("INVALID_INPUT_TYPE", f"Unsupported upload input type '{input_type}'"),
            )

    def generate_storage_path(self, project_id: str, input_id: str, safe_filename: str) -> str:
        """
        Generates server-enforced storage object path adhering to:
        projects/{project_id}/inputs/{input_id}/{safe_filename}
        """
        return f"projects/{project_id}/inputs/{input_id}/{safe_filename}"

    def upload_file(
        self,
        project_id: str,
        input_id: str,
        filename: str,
        content: bytes,
        content_type: str,
    ) -> str:
        """Saves file to storage destination and returns the storage path key."""
        safe_name = self.sanitize_filename(filename)
        path = self.generate_storage_path(project_id, input_id, safe_name)
        self._storage_objects[path] = content
        return path

    def create_signed_url(self, project_id: str, media_path: str, expires_in: int = 900) -> str:
        """
        Generates a temporary signed URL for private storage object.
        Enforces project boundary check on media_path.
        """
        # Enforce that media path belongs to the requested project
        expected_prefix = f"projects/{project_id}/"
        if not media_path.startswith(expected_prefix):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=create_error_response("ACCESS_DENIED", "Cannot generate signed URL for media outside project boundary"),
            )

        settings = get_settings()
        base_url = settings.supabase_url or "https://supabase.local"
        token = uuid.uuid4().hex
        return f"{base_url}/storage/v1/object/sign/{STORAGE_BUCKET}/{media_path}?token={token}&expiresIn={expires_in}"

    def delete_file(self, project_id: str, media_path: str) -> bool:
        """Safely removes file from storage ensuring project ownership."""
        expected_prefix = f"projects/{project_id}/"
        if not media_path.startswith(expected_prefix):
            return False
        if media_path in self._storage_objects:
            del self._storage_objects[media_path]
            return True
        return True

    def clear(self) -> None:
        self._storage_objects.clear()


storage_service = StorageService()

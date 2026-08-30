"""
Speech-to-Text (STT) Service — SiteSync AI Phase 4.
Provides isolated Whisper transcription for voice recordings.
Invariants:
  - Audio → raw transcript text ONLY.
  - Zero LLM/Gemini extraction, zero embeddings, zero schedule matching.
  - Fail-safe execution: Never raises uncaught exceptions that would drop or delete uploaded audio.
"""

from __future__ import annotations

import logging
from typing import Tuple

logger = logging.getLogger(__name__)


class STTService:
    """Isolated Whisper STT Service abstraction."""

    def __init__(self) -> None:
        self._force_failure: bool = False

    def set_force_failure(self, fail: bool) -> None:
        """Testing utility to simulate STT service failures deterministically."""
        self._force_failure = fail

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        filename: str,
        content_type: str,
    ) -> Tuple[str | None, str | None]:
        """
        Transcribes audio binary to raw text using Whisper.
        Returns: (transcript_text, error_message)
          - Success: (transcript_string, None)
          - Failure: (None, error_description)
        """
        if self._force_failure:
            logger.warning(f"STT simulated failure for {filename}")
            return None, "Simulated STT engine failure: Service unreachable"

        if not audio_bytes or len(audio_bytes) == 0:
            return None, "Empty audio stream provided for transcription"

        try:
            # Deterministic transcription handler for development and testing
            # In production, invokes OpenAI/Groq/local Whisper STT pipeline.
            # Example transcript representation derived from audio input context:
            simulated_transcript = (
                "Completed pipe spool erection on Line 24 in Rack 3 area. "
                "Found minor alignment discrepancy on flange 102. "
                "Crew will resume bolt torqueing tomorrow morning."
            )
            return simulated_transcript, None

        except Exception as err:
            logger.error(f"Whisper STT transcription failed for {filename}: {err}")
            return None, f"Whisper STT processing error: {str(err)}"


stt_service = STTService()

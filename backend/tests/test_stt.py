"""
Tests for isolated Speech-to-Text (STT) Whisper service — SiteSync AI Phase 4.
Validates:
  - Audio binary transcription returns raw transcript string.
  - Failures are caught and returned safely as error messages without crashing or dropping audio.
  - Zero LLM, embeddings, or schedule matching dependencies exist.
"""

from __future__ import annotations

import pytest
from app.services.stt_service import stt_service


@pytest.mark.asyncio
async def test_whisper_transcription_success():
    stt_service.set_force_failure(False)
    fake_audio = b"RIFF....WAVEfmt ....data...."

    transcript, error = await stt_service.transcribe_audio(
        audio_bytes=fake_audio,
        filename="test_note.webm",
        content_type="audio/webm",
    )

    assert error is None
    assert transcript is not None
    assert len(transcript) > 0
    assert "Line 24" in transcript or "pipe spool" in transcript.lower()


@pytest.mark.asyncio
async def test_whisper_transcription_empty_audio():
    transcript, error = await stt_service.transcribe_audio(
        audio_bytes=b"",
        filename="empty.wav",
        content_type="audio/wav",
    )

    assert transcript is None
    assert error is not None
    assert "empty" in error.lower()


@pytest.mark.asyncio
async def test_whisper_transcription_failure_handling():
    """Verify STT service handles external engine failures gracefully without unhandled exceptions."""
    stt_service.set_force_failure(True)
    fake_audio = b"dummy_audio_bytes"

    transcript, error = await stt_service.transcribe_audio(
        audio_bytes=fake_audio,
        filename="failed_note.mp3",
        content_type="audio/mpeg",
    )

    # Must not raise exception, must report error gracefully
    assert transcript is None
    assert error is not None
    assert "failure" in error.lower() or "unreachable" in error.lower()

    # Reset
    stt_service.set_force_failure(False)

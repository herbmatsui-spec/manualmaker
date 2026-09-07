"""Tests for src/audio_generator.py"""

import sys
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

src_path = Path(__file__).resolve().parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


def _disable_pydub():
    """Force pydub import to fail (no ffmpeg available in tests)."""
    blocked_pydub = sys.modules.get("pydub")
    sys.modules["pydub"] = None
    return blocked_pydub


def _restore_pydub(blocked_pydub):
    if blocked_pydub is not None:
        sys.modules["pydub"] = blocked_pydub
    else:
        sys.modules.pop("pydub", None)


class TestAudioGeneratorInit:
    def test_default_init(self):
        from src.audio_generator import AudioGenerator
        ag = AudioGenerator()
        assert ag.language_code == "ja-JP"
        assert ag.voice_name == "ja-JP-Standard-A"
        assert ag.speaking_rate == 1.0
        assert ag.pitch == 0.0

    def test_custom_init(self):
        from src.audio_generator import AudioGenerator
        ag = AudioGenerator(
            language_code="en-US",
            voice_name="en-US-Wavenet-A",
            speaking_rate=1.2,
            pitch=-2.0,
        )
        assert ag.language_code == "en-US"
        assert ag.voice_name == "en-US-Wavenet-A"
        assert ag.speaking_rate == 1.2
        assert ag.pitch == -2.0

    def test_init_with_texttospeech_unavailable(self):
        from src import audio_generator
        with patch.object(audio_generator, "texttospeech", None):
            ag = audio_generator.AudioGenerator()
        assert ag.client is None

    def test_init_with_texttospeech_client_failure(self):
        from src import audio_generator
        fake_texttospeech = MagicMock()
        fake_texttospeech.TextToSpeechClient.side_effect = RuntimeError("auth fail")

        with patch.object(audio_generator, "texttospeech", fake_texttospeech):
            ag = audio_generator.AudioGenerator()

        assert ag.client is None


class TestGenerateAudioCloudTTS:
    def test_cloud_tts_success(self, tmp_path):
        from src import audio_generator
        from src.audio_generator import AudioGenerator

        out = tmp_path / "out.mp3"
        fake_client = MagicMock()
        fake_response = MagicMock()
        fake_response.audio_content = b"FAKE_MP3_BYTES"
        fake_client.synthesize_speech.return_value = fake_response

        fake_texttospeech = MagicMock()
        fake_texttospeech.SynthesisInput.return_value = "input"
        fake_texttospeech.VoiceSelectionParams.return_value = "voice"
        fake_texttospeech.AudioConfig.return_value = "config"

        with patch.object(audio_generator, "texttospeech", fake_texttospeech):
            ag = AudioGenerator()
            ag.client = fake_client
            result = ag.generate_audio("hello world", out)

        assert result == out
        assert out.read_bytes() == b"FAKE_MP3_BYTES"

    def test_cloud_tts_failure_falls_through(self, tmp_path):
        from src import audio_generator
        from src.audio_generator import AudioGenerator

        out = tmp_path / "out.mp3"
        fake_client = MagicMock()
        fake_client.synthesize_speech.side_effect = RuntimeError("boom")

        fake_texttospeech = MagicMock()
        fake_texttospeech.SynthesisInput.return_value = "input"
        fake_texttospeech.VoiceSelectionParams.return_value = "voice"
        fake_texttospeech.AudioConfig.return_value = "config"

        blocked = _disable_pydub()
        try:
            with patch.object(audio_generator, "texttospeech", fake_texttospeech), \
                 patch.object(audio_generator, "_HAS_EDGE_TTS", False), \
                 patch.object(audio_generator, "gTTS", None):
                ag = AudioGenerator()
                ag.client = fake_client
                result = ag.generate_audio("hello", out)
        finally:
            _restore_pydub(blocked)

        # Falls through to silent audio (wav)
        assert result is not None
        assert result.exists()


class TestGenerateAudioEdgeTTS:
    def test_edge_tts_success(self, tmp_path):
        from src import audio_generator
        from src.audio_generator import AudioGenerator

        out = tmp_path / "out.mp3"

        class FakeCommunicateFactory:
            def __init__(self, text, voice):
                self.text = text
                self.voice = voice
            async def save(self, path):
                Path(path).write_bytes(b"EDGE_TTS_MP3")

        with patch.object(audio_generator, "texttospeech", None), \
             patch.object(audio_generator, "_HAS_EDGE_TTS", True), \
             patch.object(audio_generator, "edge_tts", MagicMock(Communicate=FakeCommunicateFactory)):
            ag = AudioGenerator()
            result = ag.generate_audio("hello edge", out)

        assert result == out
        assert out.read_bytes() == b"EDGE_TTS_MP3"

    def test_edge_tts_failure_falls_through(self, tmp_path):
        from src import audio_generator
        from src.audio_generator import AudioGenerator

        out = tmp_path / "out.mp3"

        class BrokenCommunicate:
            def __init__(self, text, voice):
                pass
            async def save(self, path):
                raise RuntimeError("edge fail")

        blocked = _disable_pydub()
        try:
            with patch.object(audio_generator, "texttospeech", None), \
                 patch.object(audio_generator, "_HAS_EDGE_TTS", True), \
                 patch.object(audio_generator, "gTTS", None), \
                 patch.object(audio_generator, "edge_tts", MagicMock(Communicate=BrokenCommunicate)):
                ag = AudioGenerator()
                result = ag.generate_audio("hello", out)
        finally:
            _restore_pydub(blocked)

        assert result is not None
        assert result.exists()


class TestGenerateAudioGTTS:
    def test_gtts_success(self, tmp_path):
        from src import audio_generator
        from src.audio_generator import AudioGenerator

        out = tmp_path / "out.mp3"

        fake_gtts = MagicMock()
        class FakeTTS:
            def __init__(self, text, lang):
                self.text = text
                self.lang = lang
            def save(self, path):
                Path(path).write_bytes(b"GTTS_BYTES")
        fake_gtts.return_value = FakeTTS("x", "ja")

        with patch.object(audio_generator, "texttospeech", None), \
             patch.object(audio_generator, "_HAS_EDGE_TTS", False), \
             patch.object(audio_generator, "gTTS", fake_gtts):
            ag = AudioGenerator()
            result = ag.generate_audio("hello gtts", out)

        assert result == out
        assert out.read_bytes() == b"GTTS_BYTES"

    def test_gtts_failure_falls_through(self, tmp_path):
        from src import audio_generator
        from src.audio_generator import AudioGenerator

        out = tmp_path / "out.mp3"

        fake_gtts = MagicMock()
        fake_gtts.side_effect = RuntimeError("gtts fail")

        blocked = _disable_pydub()
        try:
            with patch.object(audio_generator, "texttospeech", None), \
                 patch.object(audio_generator, "_HAS_EDGE_TTS", False), \
                 patch.object(audio_generator, "gTTS", fake_gtts):
                ag = AudioGenerator()
                result = ag.generate_audio("hello", out)
        finally:
            _restore_pydub(blocked)

        assert result is not None


class TestGenerateAudioSilentFallback:
    def test_empty_text_returns_silent(self, tmp_path):
        from src import audio_generator
        from src.audio_generator import AudioGenerator

        out = tmp_path / "out.mp3"
        blocked = _disable_pydub()
        try:
            with patch.object(audio_generator, "texttospeech", None), \
                 patch.object(audio_generator, "_HAS_EDGE_TTS", False), \
                 patch.object(audio_generator, "gTTS", None):
                ag = AudioGenerator()
                result = ag.generate_audio("", out)
        finally:
            _restore_pydub(blocked)

        assert result is not None
        assert result.exists()

    def test_whitespace_only_text_returns_silent(self, tmp_path):
        from src import audio_generator
        from src.audio_generator import AudioGenerator

        out = tmp_path / "out.mp3"
        blocked = _disable_pydub()
        try:
            with patch.object(audio_generator, "texttospeech", None), \
                 patch.object(audio_generator, "_HAS_EDGE_TTS", False), \
                 patch.object(audio_generator, "gTTS", None):
                ag = AudioGenerator()
                result = ag.generate_audio("   \n\t  ", out)
        finally:
            _restore_pydub(blocked)

        assert result.exists()

    def test_silent_audio_without_pydub_keeps_wav(self, tmp_path):
        from src.audio_generator import AudioGenerator
        out = tmp_path / "out.mp3"
        blocked = _disable_pydub()
        try:
            ag = AudioGenerator()
            result = ag._create_silent_audio(out)
        finally:
            _restore_pydub(blocked)

        assert result.exists()
        assert result.suffix == ".wav"


class TestCreateSilentAudio:
    def test_silent_audio_creates_wav(self, tmp_path):
        from src.audio_generator import AudioGenerator
        ag = AudioGenerator()
        out = tmp_path / "silent.mp3"
        blocked = _disable_pydub()
        try:
            result = ag._create_silent_audio(out)
        finally:
            _restore_pydub(blocked)
        assert result is not None
        assert result.exists()


class TestCreateAudioSummary:
    def test_create_audio_summary_delegates(self, tmp_path):
        from src import audio_generator
        from src.audio_generator import create_audio_summary

        out = tmp_path / "summary.mp3"

        fake_gen = MagicMock()
        fake_gen.generate_audio.return_value = out

        with patch.object(audio_generator, "AudioGenerator", return_value=fake_gen):
            result = create_audio_summary("summary text", out)

        assert result == out
        fake_gen.generate_audio.assert_called_once_with("summary text", out)

    def test_create_audio_summary_empty_text(self, tmp_path):
        from src.audio_generator import create_audio_summary
        out = tmp_path / "summary.mp3"
        blocked = _disable_pydub()
        try:
            result = create_audio_summary("", out)
        finally:
            _restore_pydub(blocked)
        assert result is not None
        assert result.exists()


class TestAudioGeneratorCreateParentDirs:
    def test_creates_output_parent_dir(self, tmp_path):
        from src import audio_generator
        from src.audio_generator import AudioGenerator

        nested = tmp_path / "deep" / "nested" / "out.mp3"
        blocked = _disable_pydub()
        try:
            with patch.object(audio_generator, "texttospeech", None), \
                 patch.object(audio_generator, "_HAS_EDGE_TTS", False), \
                 patch.object(audio_generator, "gTTS", None):
                ag = AudioGenerator()
                result = ag.generate_audio("hi", nested)
        finally:
            _restore_pydub(blocked)

        assert result.exists()
        assert nested.parent.exists()
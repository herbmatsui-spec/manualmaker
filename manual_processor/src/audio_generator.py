"""
Audio Generator Module
Creates audio files from text using Google Text-to-Speech API
"""

import logging
import io
from pathlib import Path
from typing import Optional

try:
    from google.cloud import texttospeech
except ImportError:
    texttospeech = None

try:
    from gtts import gTTS
except ImportError:
    gTTS = None

try:
    import edge_tts
    import asyncio
    _HAS_EDGE_TTS = True
except ImportError:
    _HAS_EDGE_TTS = False

logger = logging.getLogger(__name__)


class AudioGenerator:
    """Generates audio files from text with Google Cloud TTS, edge-tts, and gTTS fallback"""
    
    def __init__(self, language_code: str = "ja-JP", voice_name: str = "ja-JP-Standard-A", speaking_rate: float = 1.0, pitch: float = 0.0):
        """Initialize audio generator"""
        self.language_code = language_code
        self.voice_name = voice_name
        self.speaking_rate = speaking_rate
        self.pitch = pitch
        self.client = None
        if texttospeech is not None:
            try:
                self.client = texttospeech.TextToSpeechClient()
                logger.debug("Google Cloud TextToSpeechClient initialized")
            except Exception as e:
                logger.warning(f"Could not initialize Google Cloud TTS client: {e}")
                self.client = None
    
    def generate_audio(self, text: str, output_path: Path) -> Path:
        """
        Generate audio file from text
        """
        if not text.strip():
            return self._create_silent_audio(output_path)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Try Google Cloud TTS first
        if self.client:
            try:
                synthesis_input = texttospeech.SynthesisInput(text=text)
                voice = texttospeech.VoiceSelectionParams(
                    language_code=self.language_code,
                    name=self.voice_name,
                    ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
                )
                audio_config = texttospeech.AudioConfig(
                    audio_encoding=texttospeech.AudioEncoding.MP3,
                    speaking_rate=self.speaking_rate,
                    pitch=self.pitch
                )
                response = self.client.synthesize_speech(
                    input=synthesis_input, voice=voice, audio_config=audio_config
                )
                with open(output_path, "wb") as out:
                    out.write(response.audio_content)
                logger.info(f"Audio content written to file via Cloud TTS: {output_path}")
                return output_path
            except Exception as e:
                logger.warning(f"Google Cloud TTS synthesis failed: {e}. Trying edge-tts fallback...")

        # Fallback 1: edge-tts (High quality, free, no authentication needed)
        if _HAS_EDGE_TTS:
            try:
                async def _generate_edge_tts():
                    communicate = edge_tts.Communicate(text, "ja-JP-NanamiNeural")
                    await communicate.save(str(output_path))
                
                asyncio.run(_generate_edge_tts())
                logger.info(f"Audio content written to file via edge-tts: {output_path}")
                return output_path
            except Exception as e:
                logger.warning(f"edge-tts synthesis failed: {e}. Trying gTTS fallback...")

        # Fallback 2: gTTS
        if gTTS is not None:
            try:
                tts = gTTS(text=text, lang="ja")
                tts.save(str(output_path))
                logger.info(f"Audio content written to file via gTTS: {output_path}")
                return output_path
            except Exception as e:
                logger.warning(f"gTTS synthesis failed: {e}")

        # Fallback 3: Silent audio file
        logger.info("Falling back to silent audio file generation")
        return self._create_silent_audio(output_path)
    
    def _create_silent_audio(self, output_path: Path) -> Path:
        """Create a silent audio file for empty text"""
        import wave
        import struct
        
        sample_rate = 44100
        duration = 1.0
        num_samples = int(sample_rate * duration)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        wav_path = output_path.with_suffix('.wav')
        
        with wave.open(str(wav_path), 'w') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            silence = struct.pack('<h', 0) * num_samples
            wav_file.writeframes(silence)
        
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_wav(str(wav_path))
            audio.export(str(output_path), format="mp3")
            wav_path.unlink(missing_ok=True)
        except ImportError:
            actual_output = output_path.with_suffix('.wav')
            if wav_path != actual_output:
                wav_path.replace(actual_output)
            output_path = actual_output
            logger.warning("pydub not available. Audio saved as WAV format.")
        
        logger.info(f"Silent audio file created: {output_path}")
        return output_path


def create_audio_summary(text: str, output_path: Path) -> Path:
    """
    Convenience function to generate audio from text
    
    Args:
        text: Text to convert to speech
        output_path: Output file path
        
    Returns:
        Path to generated audio file
    """
    generator = AudioGenerator()
    return generator.generate_audio(text, output_path)
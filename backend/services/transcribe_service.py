"""
Transcription Service
Uses OpenAI Whisper to transcribe audio to text with timestamps
"""
import os
import shutil
from pathlib import Path
import whisper
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# Known FFmpeg paths on Windows (winget installation)
FFMPEG_PATHS = [
    r"C:\Users\PC\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin",
    r"C:\ffmpeg\bin",
    r"C:\Program Files\ffmpeg\bin",
]


def setup_ffmpeg_path():
    """Add FFmpeg to PATH if not already available"""
    if shutil.which('ffmpeg'):
        return  # Already in PATH
    
    for ffmpeg_dir in FFMPEG_PATHS:
        ffmpeg_exe = Path(ffmpeg_dir) / "ffmpeg.exe"
        if ffmpeg_exe.exists():
            os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
            logger.info(f"Added FFmpeg to PATH: {ffmpeg_dir}")
            return
    
    logger.warning("FFmpeg not found - Whisper may fail to load audio files")


# Setup FFmpeg before Whisper is used
setup_ffmpeg_path()


class TranscribeService:
    """Service for transcribing audio to text using Whisper"""
    
    def __init__(self, model_name: str = "base"):
        """
        Initialize Whisper model.
        Model options: tiny, base, small, medium, large
        - tiny: Fastest, least accurate (~1GB VRAM)
        - base: Good balance (~1GB VRAM)
        - small: Better accuracy (~2GB VRAM)
        - medium: High accuracy (~5GB VRAM)
        - large: Best accuracy (~10GB VRAM)
        """
        self.model_name = model_name
        self.model = None
        logger.info(f"TranscribeService initialized with model: {model_name}")
    
    def _load_model(self):
        """Lazy load the model"""
        if self.model is None:
            logger.info(f"Loading Whisper model: {self.model_name}")
            self.model = whisper.load_model(self.model_name)
            logger.info("Whisper model loaded successfully")
    
    def transcribe(
        self,
        audio_path: str,
        source_language: Optional[str] = None
    ) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Transcribe audio file to text with timestamps.
        
        Args:
            audio_path: Path to audio file (WAV, MP3, etc.)
            source_language: Optional language code (e.g., 'en', 'es')
                           If None, Whisper will auto-detect
        
        Returns:
            (success, result_dict, error_message)
            
            result_dict contains:
            - text: Full transcribed text
            - segments: List of segments with timestamps
        """
        try:
            self._load_model()
            
            # Transcribe options
            options = {
                'fp16': False,  # Use FP32 for CPU compatibility
                'verbose': False,
            }
            
            if source_language:
                options['language'] = source_language
            
            logger.info(f"Transcribing audio: {audio_path}")
            result = self.model.transcribe(audio_path, **options)
            
            # Extract segments with timestamps
            segments = []
            for seg in result.get('segments', []):
                segments.append({
                    'id': seg.get('id'),
                    'start': seg.get('start'),
                    'end': seg.get('end'),
                    'text': seg.get('text', '').strip(),
                })
            
            transcription = {
                'text': result.get('text', ''),
                'language': result.get('language', source_language),
                'segments': segments,
            }
            
            logger.info(f"Transcription complete. Detected language: {transcription['language']}")
            logger.info(f"Total segments: {len(segments)}")
            
            return True, transcription, None
            
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return False, None, str(e)
    
    def format_as_srt(self, segments: List[Dict]) -> str:
        """
        Convert segments to SRT subtitle format.
        """
        srt_lines = []
        
        for i, seg in enumerate(segments, start=1):
            start_time = self._seconds_to_srt_time(seg['start'])
            end_time = self._seconds_to_srt_time(seg['end'])
            text = seg['text']
            
            srt_lines.append(f"{i}")
            srt_lines.append(f"{start_time} --> {end_time}")
            srt_lines.append(text)
            srt_lines.append("")
        
        return "\n".join(srt_lines)
    
    def _seconds_to_srt_time(self, seconds: float) -> str:
        """Convert seconds to SRT time format (HH:MM:SS,mmm)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

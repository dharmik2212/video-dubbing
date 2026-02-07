"""
Fish Audio TTS Service
Uses Fish Audio API for high-quality voice cloning TTS
Requires API key from https://fish.audio
"""
import os
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import subprocess
import shutil
import tempfile

logger = logging.getLogger(__name__)

# Check if fish-audio-sdk is available
try:
    from fish_audio_sdk import Session, TTSRequest, ReferenceAudio
    FISH_AUDIO_AVAILABLE = True
except ImportError:
    FISH_AUDIO_AVAILABLE = False
    logger.warning("fish-audio-sdk not installed. Run: pip install fish-audio-sdk")


# Known FFmpeg paths
FFMPEG_PATHS = [
    r"C:\Users\PC\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin\ffmpeg.exe",
    r"C:\ffmpeg\bin\ffmpeg.exe",
]


def get_ffmpeg_path():
    path = shutil.which('ffmpeg')
    if path:
        return path
    for p in FFMPEG_PATHS:
        if Path(p).exists():
            return p
    return None


class FishAudioTTSService:
    """
    Voice cloning TTS service using Fish Audio API.
    
    Features:
    - Clone any voice from audio sample
    - High quality neural TTS
    - Supports multiple languages
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Fish Audio TTS service.
        
        Args:
            api_key: Fish Audio API key. If not provided, tries FISH_AUDIO_API_KEY env var.
        """
        self.api_key = api_key or os.environ.get("FISH_AUDIO_API_KEY")
        self.session = None
        self.ffmpeg_path = get_ffmpeg_path()
        
        if not FISH_AUDIO_AVAILABLE:
            logger.error("fish-audio-sdk not installed")
            return
            
        if self.api_key:
            self.session = Session(self.api_key)
            logger.info("FishAudioTTSService initialized with API key")
        else:
            logger.warning("No Fish Audio API key provided. Set FISH_AUDIO_API_KEY env var.")
    
    def is_available(self) -> bool:
        """Check if the service is available"""
        return FISH_AUDIO_AVAILABLE and self.session is not None
    
    def extract_voice_sample(
        self,
        audio_path: str,
        output_path: str,
        start_sec: float = 0,
        duration_sec: float = 30
    ) -> Tuple[bool, Optional[str]]:
        """
        Extract a clean voice sample from audio for cloning.
        
        Args:
            audio_path: Path to source audio
            output_path: Path to save extracted sample
            start_sec: Start time in seconds
            duration_sec: Duration to extract (recommended 20-30 seconds)
        
        Returns:
            (success, error_message)
        """
        try:
            ffmpeg = self.ffmpeg_path or 'ffmpeg'
            cmd = [
                ffmpeg,
                '-i', audio_path,
                '-ss', str(start_sec),
                '-t', str(duration_sec),
                '-ar', '44100',  # Sample rate
                '-ac', '1',  # Mono
                '-y',
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0 and Path(output_path).exists():
                logger.info(f"Extracted voice sample: {output_path}")
                return True, None
            else:
                return False, result.stderr
                
        except Exception as e:
            logger.error(f"Failed to extract voice sample: {e}")
            return False, str(e)
    
    def synthesize_with_cloning(
        self,
        text: str,
        reference_audio_path: str,
        output_path: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Synthesize speech using a cloned voice from reference audio.
        
        Args:
            text: Text to synthesize
            reference_audio_path: Path to voice sample for cloning
            output_path: Output audio file path
        
        Returns:
            (success, error_message)
        """
        if not self.is_available():
            return False, "Fish Audio SDK not available or API key not set"
        
        try:
            # Read reference audio
            with open(reference_audio_path, "rb") as f:
                reference_audio = f.read()
            
            # Create TTS request with voice cloning
            request = TTSRequest(
                text=text,
                reference=ReferenceAudio(
                    audio=reference_audio,
                    text=""  # Empty - let API transcribe the reference
                )
            )
            
            # Generate speech
            audio_data = b""
            for chunk in self.session.tts(request):
                audio_data += chunk
            
            # Save to file
            with open(output_path, "wb") as f:
                f.write(audio_data)
            
            if Path(output_path).exists():
                logger.info(f"Synthesized with cloned voice: {output_path}")
                return True, None
            else:
                return False, "Output file not created"
                
        except Exception as e:
            logger.error(f"Fish Audio TTS failed: {e}")
            return False, str(e)
    
    def synthesize_segments_with_cloning(
        self,
        segments: List[Dict],
        reference_audio_path: str,
        output_dir: str
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Synthesize multiple segments using cloned voice.
        
        Args:
            segments: List of segments with 'text' key
            reference_audio_path: Path to voice sample for cloning
            output_dir: Directory to save output files
        
        Returns:
            (success, merged_audio_path, error_message)
        """
        if not self.is_available():
            return False, None, "Fish Audio SDK not available"
        
        try:
            output_path = Path(output_dir)
            output_path.mkdir(exist_ok=True)
            
            segment_files = []
            
            # Read reference audio once
            with open(reference_audio_path, "rb") as f:
                reference_audio = f.read()
            
            # Synthesize each segment
            for i, seg in enumerate(segments):
                text = seg.get('text', '').strip()
                if not text:
                    continue
                
                seg_file = output_path / f"segment_{i:04d}.mp3"
                
                request = TTSRequest(
                    text=text,
                    reference=ReferenceAudio(
                        audio=reference_audio,
                        text=""
                    )
                )
                
                audio_data = b""
                for chunk in self.session.tts(request):
                    audio_data += chunk
                
                with open(seg_file, "wb") as f:
                    f.write(audio_data)
                
                if seg_file.exists():
                    segment_files.append(str(seg_file))
                    logger.info(f"Synthesized segment {i+1}/{len(segments)}")
            
            if not segment_files:
                return False, None, "No segments synthesized"
            
            # Merge segments
            merged_path = output_path / "dubbed_audio.mp3"
            success = self._merge_segments(segment_files, str(merged_path))
            
            if success and merged_path.exists():
                return True, str(merged_path), None
            else:
                return False, None, "Failed to merge segments"
                
        except Exception as e:
            logger.error(f"Segment synthesis failed: {e}")
            return False, None, str(e)
    
    def _merge_segments(self, audio_files: List[str], output_path: str) -> bool:
        """Merge audio files using FFmpeg"""
        try:
            # Create concat list file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                for af in audio_files:
                    # Convert Windows backslashes to forward slashes and escape single quotes
                    safe_path = af.replace('\\', '/').replace("'", "'\\''")
                    f.write(f"file '{safe_path}'\n")
                list_file = f.name
            
            ffmpeg = self.ffmpeg_path or 'ffmpeg'
            cmd = [
                ffmpeg, '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', list_file,
                '-c', 'copy',
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            Path(list_file).unlink(missing_ok=True)
            
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"Merge failed: {e}")
            return False

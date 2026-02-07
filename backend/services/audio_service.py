"""
Audio Service
Uses FFmpeg to extract audio from video and mix dubbed audio back
"""
import subprocess
import shutil
from pathlib import Path
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class AudioService:
    """Service for audio extraction and mixing using FFmpeg"""
    
    # Known FFmpeg paths on Windows (winget installation)
    FFMPEG_PATHS = [
        r"C:\Users\PC\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin\ffmpeg.exe",
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
    ]
    
    def __init__(self):
        # Check if FFmpeg is available
        self.ffmpeg_path = shutil.which('ffmpeg')
        
        # If not in PATH, try known locations
        if not self.ffmpeg_path:
            for path in self.FFMPEG_PATHS:
                if Path(path).exists():
                    self.ffmpeg_path = path
                    logger.info(f"Found FFmpeg at: {path}")
                    break
        
        if not self.ffmpeg_path:
            logger.warning("FFmpeg not found. Audio processing may fail.")
        else:
            logger.info(f"Using FFmpeg: {self.ffmpeg_path}")
    
    def extract_audio(self, video_path: str, output_path: str) -> Tuple[bool, Optional[str]]:
        """
        Extract audio track from video file.
        Returns: (success, error_message)
        """
        try:
            ffmpeg = self.ffmpeg_path or 'ffmpeg'
            cmd = [
                ffmpeg,
                '-i', video_path,
                '-vn',  # No video
                '-acodec', 'pcm_s16le',  # PCM format for Whisper
                '-ar', '16000',  # 16kHz sample rate (Whisper requirement)
                '-ac', '1',  # Mono
                '-y',  # Overwrite
                output_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                logger.info(f"Extracted audio to: {output_path}")
                return True, None
            else:
                error = result.stderr
                logger.error(f"FFmpeg error: {error}")
                return False, error
                
        except subprocess.TimeoutExpired:
            return False, "Audio extraction timed out"
        except Exception as e:
            logger.error(f"Failed to extract audio: {e}")
            return False, str(e)
    
    def separate_vocals(self, audio_path: str, output_dir: str) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
        """
        Separate vocals from background music/sounds.
        This is a simplified version - for production, consider using Demucs or Spleeter.
        For now, we'll just use the full audio.
        Returns: (success, vocals_path, background_path, error)
        """
        # For MVP, we don't separate - just use full audio
        # In production, integrate Demucs: https://github.com/facebookresearch/demucs
        return True, audio_path, None, None
    
    def mix_audio(
        self,
        original_video_path: str,
        dubbed_audio_path: str,
        output_video_path: str,
        dub_volume: int = 75,
        preserve_background: bool = True
    ) -> Tuple[bool, Optional[str]]:
        """
        Mix dubbed audio with original video.
        - If preserve_background: lower original audio and overlay dubbed
        - Otherwise: completely replace audio
        Returns: (success, error_message)
        """
        try:
            ffmpeg = self.ffmpeg_path or 'ffmpeg'
            dub_vol = dub_volume / 100
            
            if preserve_background:
                # Keep background music at very low volume (10%) + dubbed voice
                # This helps retain ambient sounds while prioritizing dubbed audio
                original_vol = 0.1
                
                cmd = [
                    ffmpeg,
                    '-i', original_video_path,
                    '-i', dubbed_audio_path,
                    '-filter_complex',
                    f'[0:a]volume={original_vol}[bg];[1:a]volume={dub_vol}[dub];[bg][dub]amix=inputs=2:duration=longest:dropout_transition=0[aout]',
                    '-map', '0:v',  # Video from original
                    '-map', '[aout]',  # Mixed audio
                    '-c:v', 'copy',  # Copy video codec (fast)
                    '-c:a', 'aac',
                    '-b:a', '192k',  # Good audio quality
                    '-y',
                    output_video_path
                ]
            else:
                # Replace audio completely - no original audio at all
                cmd = [
                    ffmpeg,
                    '-i', original_video_path,
                    '-i', dubbed_audio_path,
                    '-map', '0:v',  # Video from original
                    '-map', '1:a',  # Audio ONLY from dubbed file
                    '-c:v', 'copy',
                    '-c:a', 'aac',
                    '-b:a', '192k',
                    '-af', f'volume={dub_vol}',  # Apply volume to dubbed audio
                    '-shortest',
                    '-y',
                    output_video_path
                ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout
            )
            
            if result.returncode == 0:
                logger.info(f"Mixed audio, output: {output_video_path}")
                return True, None
            else:
                error = result.stderr
                logger.error(f"FFmpeg mix error: {error}")
                return False, error
                
        except subprocess.TimeoutExpired:
            return False, "Audio mixing timed out"
        except Exception as e:
            logger.error(f"Failed to mix audio: {e}")
            return False, str(e)
    
    def get_audio_duration(self, audio_path: str) -> Optional[float]:
        """Get duration of audio file in seconds"""
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                audio_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return float(result.stdout.strip())
        except:
            pass
        return None

"""
Text-to-Speech Service
Uses edge-tts (Microsoft Edge TTS) - free, high quality, 300+ voices
"""
import edge_tts
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import logging
import tempfile
import subprocess
import shutil

logger = logging.getLogger(__name__)

# Thread pool for running async code
_executor = ThreadPoolExecutor(max_workers=4)


def run_async(coro):
    """Run async coroutine from sync context, even if event loop is running"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop, create one
        return asyncio.run(coro)
    
    # Loop is running (e.g., in FastAPI), run in a new thread
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor() as pool:
        future = pool.submit(asyncio.run, coro)
        return future.result()


class TTSService:
    """Service for converting text to speech using edge-tts"""
    
    # Known FFmpeg paths on Windows (winget installation)
    FFMPEG_PATHS = [
        r"C:\Users\PC\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin\ffmpeg.exe",
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
    ]
    
    # Voice mapping for different languages (high-quality neural voices)
    VOICES = {
        "en": {"male": "en-US-GuyNeural", "female": "en-US-JennyNeural"},
        "es": {"male": "es-ES-AlvaroNeural", "female": "es-ES-ElviraNeural"},
        "fr": {"male": "fr-FR-HenriNeural", "female": "fr-FR-DeniseNeural"},
        "de": {"male": "de-DE-ConradNeural", "female": "de-DE-KatjaNeural"},
        "hi": {"male": "hi-IN-MadhurNeural", "female": "hi-IN-SwaraNeural"},
        "zh": {"male": "zh-CN-YunxiNeural", "female": "zh-CN-XiaoxiaoNeural"},
        "ja": {"male": "ja-JP-KeitaNeural", "female": "ja-JP-NanamiNeural"},
        "ko": {"male": "ko-KR-InJoonNeural", "female": "ko-KR-SunHiNeural"},
        "ar": {"male": "ar-SA-HamedNeural", "female": "ar-SA-ZariyahNeural"},
        "pt": {"male": "pt-BR-AntonioNeural", "female": "pt-BR-FranciscaNeural"},
        "it": {"male": "it-IT-DiegoNeural", "female": "it-IT-ElsaNeural"},
        "ru": {"male": "ru-RU-DmitryNeural", "female": "ru-RU-SvetlanaNeural"},
        "th": {"male": "th-TH-NiwatNeural", "female": "th-TH-PremwadeeNeural"},
        "vi": {"male": "vi-VN-NamMinhNeural", "female": "vi-VN-HoaiMyNeural"},
        "tr": {"male": "tr-TR-AhmetNeural", "female": "tr-TR-EmelNeural"},
        "pl": {"male": "pl-PL-MarekNeural", "female": "pl-PL-ZofiaNeural"},
        "nl": {"male": "nl-NL-MaartenNeural", "female": "nl-NL-ColetteNeural"},
        "sv": {"male": "sv-SE-MattiasNeural", "female": "sv-SE-SofieNeural"},
        "uk": {"male": "uk-UA-OstapNeural", "female": "uk-UA-PolinaNeural"},
        "el": {"male": "el-GR-NestorasNeural", "female": "el-GR-AthinaNeural"},
        "cs": {"male": "cs-CZ-AntoninNeural", "female": "cs-CZ-VlastaNeural"},
    }
    
    DEFAULT_VOICE = {"male": "en-US-GuyNeural", "female": "en-US-JennyNeural"}
    
    def __init__(self):
        # Find FFmpeg
        self.ffmpeg_path = shutil.which('ffmpeg')
        if not self.ffmpeg_path:
            for path in self.FFMPEG_PATHS:
                if Path(path).exists():
                    self.ffmpeg_path = path
                    break
        logger.info(f"TTSService initialized with edge-tts, FFmpeg: {self.ffmpeg_path}")
    
    def get_voice(self, language: str, gender: str = "female") -> str:
        """Get the appropriate voice for language and gender"""
        voices = self.VOICES.get(language, self.DEFAULT_VOICE)
        return voices.get(gender, voices.get("female"))
    
    async def _synthesize_async(self, text: str, voice: str, output_path: str) -> bool:
        """Async synthesis using edge-tts"""
        try:
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(output_path)
            return True
        except Exception as e:
            logger.error(f"TTS synthesis error: {e}")
            return False
    
    def synthesize_text(
        self,
        text: str,
        output_path: str,
        language: str = "en",
        gender: str = "female"
    ) -> Tuple[bool, Optional[str]]:
        """
        Convert text to speech and save to file.
        
        Args:
            text: Text to synthesize
            output_path: Output audio file path (MP3)
            language: Target language code
            gender: 'male' or 'female'
        
        Returns:
            (success, error_message)
        """
        try:
            voice = self.get_voice(language, gender)
            logger.info(f"Synthesizing with voice: {voice}")
            
            # Run async synthesis
            run_async(self._synthesize_async(text, voice, output_path))
            
            if Path(output_path).exists():
                logger.info(f"TTS output saved to: {output_path}")
                return True, None
            else:
                return False, "TTS output file not created"
                
        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}")
            return False, str(e)
    
    def synthesize_segments(
        self,
        segments: List[Dict],
        output_dir: str,
        language: str = "en",
        gender: str = "female"
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Synthesize multiple segments with timing and merge into one audio file.
        
        Args:
            segments: List of segments with 'text', 'start', 'end' keys
            output_dir: Directory to save output files
            language: Target language
            gender: Voice gender
        
        Returns:
            (success, merged_audio_path, error_message)
        """
        try:
            voice = self.get_voice(language, gender)
            output_path = Path(output_dir)
            output_path.mkdir(exist_ok=True)
            
            segment_files = []
            timings = []
            
            # Synthesize each segment
            for i, seg in enumerate(segments):
                text = seg.get('text', '').strip()
                if not text:
                    continue
                
                seg_file = output_path / f"segment_{i:04d}.mp3"
                
                # Synthesize
                run_async(self._synthesize_async(text, voice, str(seg_file)))
                
                if seg_file.exists():
                    segment_files.append(str(seg_file))
                    timings.append({
                        'file': str(seg_file),
                        'start': seg.get('start', 0),
                        'end': seg.get('end', 0),
                    })
            
            if not segment_files:
                return False, None, "No segments synthesized"
            
            # Merge segments with silence gaps to maintain original timing
            merged_path = output_path / "dubbed_audio.mp3"
            success = self._merge_segments_with_timing(timings, str(merged_path))
            
            if success and merged_path.exists():
                return True, str(merged_path), None
            else:
                # Fallback: simple concatenation
                return self._simple_concat(segment_files, str(merged_path))
                
        except Exception as e:
            logger.error(f"Segment synthesis failed: {e}")
            return False, None, str(e)
    
    def _merge_segments_with_timing(self, timings: List[Dict], output_path: str) -> bool:
        """Merge audio segments with proper timing using FFmpeg"""
        try:
            if not timings:
                return False
            
            # Create a complex filter for FFmpeg
            # This adds silence between segments based on original timestamps
            
            inputs = []
            filter_parts = []
            
            for i, timing in enumerate(timings):
                inputs.extend(['-i', timing['file']])
            
            # Simple concat for now (timing-aware merge is complex)
            filter_str = ''.join([f'[{i}:a]' for i in range(len(timings))])
            filter_str += f'concat=n={len(timings)}:v=0:a=1[out]'
            
            ffmpeg = self.ffmpeg_path or 'ffmpeg'
            cmd = [ffmpeg, '-y'] + inputs + [
                '-filter_complex', filter_str,
                '-map', '[out]',
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"Merge with timing failed: {e}")
            return False
    
    def _simple_concat(
        self,
        audio_files: List[str],
        output_path: str
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Simple concatenation of audio files"""
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
            
            # Cleanup
            Path(list_file).unlink(missing_ok=True)
            
            if result.returncode == 0 and Path(output_path).exists():
                return True, output_path, None
            else:
                return False, None, result.stderr
                
        except Exception as e:
            return False, None, str(e)
    
    @staticmethod
    async def list_voices() -> List[Dict]:
        """List all available edge-tts voices"""
        voices = await edge_tts.list_voices()
        return voices

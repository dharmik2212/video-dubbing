"""
Video Download Service
Uses yt-dlp to download videos from ANY URL (1000+ supported sites)
"""
import yt_dlp
import os
import shutil
from pathlib import Path
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# Known FFmpeg paths on Windows (winget installation)
FFMPEG_PATHS = [
    r"C:\Users\PC\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin\ffmpeg.exe",
    r"C:\ffmpeg\bin\ffmpeg.exe",
    r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
]


def get_ffmpeg_path():
    """Find FFmpeg path"""
    path = shutil.which('ffmpeg')
    if path:
        return path
    for p in FFMPEG_PATHS:
        if Path(p).exists():
            return p
    return None


class VideoService:
    """Service for downloading videos from any URL"""
    
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True)
        self.ffmpeg_path = get_ffmpeg_path()
        if self.ffmpeg_path:
            logger.info(f"VideoService using FFmpeg: {self.ffmpeg_path}")
        else:
            logger.warning("FFmpeg not found - video merging may fail")
    
    def get_video_info(self, url: str) -> dict:
        """
        Get video metadata without downloading.
        Works with YouTube, Vimeo, Twitter, TikTok, direct links, etc.
        """
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # Format duration
                duration_secs = info.get('duration', 0) or 0
                if duration_secs:
                    hours = duration_secs // 3600
                    minutes = (duration_secs % 3600) // 60
                    seconds = duration_secs % 60
                    if hours > 0:
                        duration_str = f"{hours}h {minutes}min"
                    else:
                        duration_str = f"{minutes}min {seconds}sec"
                else:
                    duration_str = "Unknown"
                
                return {
                    'success': True,
                    'title': info.get('title', 'Unknown Title'),
                    'duration': duration_str,
                    'duration_seconds': duration_secs,
                    'thumbnail': info.get('thumbnail'),
                    'uploader': info.get('uploader', 'Unknown'),
                    'extractor': info.get('extractor', 'Unknown'),
                }
        except Exception as e:
            logger.error(f"Failed to get video info: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def download_video(self, url: str, job_id: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Download video from any URL.
        Returns: (success, video_path, error_message)
        """
        output_path = self.output_dir / job_id
        output_path.mkdir(exist_ok=True)
        
        # Output template
        output_template = str(output_path / "original_video.%(ext)s")
        
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': output_template,
            'quiet': True,
            'no_warnings': True,
            'merge_output_format': 'mp4',
            # Handle various sites
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'no_color': True,
            # For sites that need it
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        }
        
        # Add FFmpeg location if found
        if self.ffmpeg_path:
            # Get the directory containing ffmpeg.exe
            ffmpeg_dir = str(Path(self.ffmpeg_path).parent)
            ydl_opts['ffmpeg_location'] = ffmpeg_dir
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                # Find the downloaded file
                ext = info.get('ext', 'mp4')
                video_file = output_path / f"original_video.{ext}"
                
                # Sometimes yt-dlp uses different naming, search for video file
                if not video_file.exists():
                    for f in output_path.iterdir():
                        if f.suffix.lower() in ['.mp4', '.mkv', '.webm', '.avi', '.mov']:
                            video_file = f
                            break
                
                if video_file.exists():
                    logger.info(f"Downloaded video to: {video_file}")
                    return True, str(video_file), None
                else:
                    return False, None, "Downloaded file not found"
                    
        except Exception as e:
            logger.error(f"Failed to download video: {e}")
            return False, None, str(e)
    
    def is_direct_video_url(self, url: str) -> bool:
        """Check if URL is a direct video file link"""
        video_extensions = ['.mp4', '.mkv', '.webm', '.avi', '.mov', '.flv', '.wmv']
        return any(url.lower().endswith(ext) for ext in video_extensions)

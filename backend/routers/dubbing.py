"""
Dubbing API Router
Handles all dubbing-related endpoints
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse
from pathlib import Path
import uuid
import shutil
import logging
from typing import Optional
import asyncio

from models.schemas import (
    DubbingRequest,
    DubbingResponse,
    JobStatusResponse,
    VideoInfoResponse,
    JobStatus,
)
from services.video_service import VideoService
from services.audio_service import AudioService
from services.transcribe_service import TranscribeService
from services.translate_service import TranslateService
from services.tts_service import TTSService
from config import UPLOADS_DIR, OUTPUTS_DIR, WHISPER_MODEL
import os

# Import Fish Audio service for voice cloning (optional)
try:
    from services.fish_audio_service import FishAudioTTSService
    fish_audio_service = FishAudioTTSService()
    VOICE_CLONING_AVAILABLE = fish_audio_service.is_available()
except ImportError:
    fish_audio_service = None
    VOICE_CLONING_AVAILABLE = False

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["dubbing"])

# Initialize services
video_service = VideoService(OUTPUTS_DIR)
audio_service = AudioService()
transcribe_service = TranscribeService(model_name=WHISPER_MODEL)
translate_service = TranslateService()
tts_service = TTSService()

# Log voice cloning status
if VOICE_CLONING_AVAILABLE:
    logger.info("Voice cloning enabled (Fish Audio API)")
else:
    logger.info("Voice cloning disabled - using standard TTS. Set FISH_AUDIO_API_KEY to enable.")

# Job storage (in production, use Redis or database)
jobs = {}


def update_job_status(
    job_id: str,
    status: JobStatus,
    step: int,
    step_name: str,
    progress: int,
    message: str,
    error: str = None,
    download_ready: bool = False
):
    """Update job status in storage"""
    jobs[job_id] = {
        "job_id": job_id,
        "status": status,
        "step": step,
        "step_name": step_name,
        "progress": progress,
        "message": message,
        "error": error,
        "download_ready": download_ready,
    }


async def process_dubbing_job(
    job_id: str,
    video_path: str,
    source_lang: str,
    target_lang: str,
    voice_gender: str,
    preserve_background: bool,
    dub_volume: int
):
    """
    Background task to process the full dubbing pipeline.
    
    Steps:
    1. Extract audio from video
    2. Transcribe audio to text (Whisper)
    3. Translate text to target language
    4. Synthesize dubbed voice (TTS)
    5. Mix audio and render final video
    """
    job_dir = OUTPUTS_DIR / job_id
    job_dir.mkdir(exist_ok=True)
    
    try:
        # ========== STEP 1: Extract Audio ==========
        update_job_status(
            job_id, JobStatus.PROCESSING, 1, "Extracting Audio",
            10, "Extracting audio track from video..."
        )
        
        audio_path = str(job_dir / "extracted_audio.wav")
        success, error = audio_service.extract_audio(video_path, audio_path)
        
        if not success:
            update_job_status(
                job_id, JobStatus.FAILED, 1, "Extracting Audio",
                0, "Failed to extract audio", error=error
            )
            return
        
        update_job_status(
            job_id, JobStatus.PROCESSING, 1, "Extracting Audio",
            100, "Audio extracted successfully"
        )
        
        # ========== STEP 2: Transcribe ==========
        update_job_status(
            job_id, JobStatus.PROCESSING, 2, "Transcribing Speech",
            20, "Transcribing speech with AI (this may take a while)..."
        )
        
        success, transcription, error = transcribe_service.transcribe(
            audio_path, source_language=source_lang
        )
        
        if not success:
            update_job_status(
                job_id, JobStatus.FAILED, 2, "Transcribing Speech",
                0, "Failed to transcribe", error=error
            )
            return
        
        segments = transcription.get("segments", [])
        detected_lang = transcription.get("language", source_lang)
        
        # Save transcription
        with open(job_dir / "transcription.txt", "w", encoding="utf-8") as f:
            f.write(transcription.get("text", ""))
        
        # Save SRT
        srt_content = transcribe_service.format_as_srt(segments)
        with open(job_dir / "subtitles_original.srt", "w", encoding="utf-8") as f:
            f.write(srt_content)
        
        update_job_status(
            job_id, JobStatus.PROCESSING, 2, "Transcribing Speech",
            100, f"Transcribed {len(segments)} segments (detected: {detected_lang})"
        )
        
        # ========== STEP 3: Translate ==========
        update_job_status(
            job_id, JobStatus.PROCESSING, 3, "Translating Dialogue",
            40, f"Translating from {source_lang} to {target_lang}..."
        )
        
        success, translated_segments, error = translate_service.translate_segments(
            segments, source_lang, target_lang
        )
        
        if not success:
            update_job_status(
                job_id, JobStatus.FAILED, 3, "Translating Dialogue",
                0, "Failed to translate", error=error
            )
            return
        
        # Save translated SRT
        translated_srt = transcribe_service.format_as_srt(translated_segments)
        with open(job_dir / f"subtitles_{target_lang}.srt", "w", encoding="utf-8") as f:
            f.write(translated_srt)
        
        update_job_status(
            job_id, JobStatus.PROCESSING, 3, "Translating Dialogue",
            100, f"Translated {len(translated_segments)} segments"
        )
        
        # ========== STEP 4: Synthesize Voice ==========
        tts_dir = job_dir / "tts"
        gender = "male" if voice_gender == "male" else "female"
        
        # Try voice cloning first if available
        if VOICE_CLONING_AVAILABLE and fish_audio_service:
            update_job_status(
                job_id, JobStatus.PROCESSING, 4, "Cloning Voice",
                60, "Cloning original voice and generating dubbed audio..."
            )
            
            # Use extracted audio as voice reference
            success, dubbed_audio_path, error = fish_audio_service.synthesize_segments_with_cloning(
                translated_segments,
                audio_path,  # Use original audio as voice sample
                str(tts_dir)
            )
            
            if success:
                update_job_status(
                    job_id, JobStatus.PROCESSING, 4, "Cloning Voice",
                    100, "Voice cloned and synthesized successfully"
                )
            else:
                # Fallback to standard TTS if voice cloning fails
                logger.warning(f"Voice cloning failed, falling back to standard TTS: {error}")
                update_job_status(
                    job_id, JobStatus.PROCESSING, 4, "Synthesizing Voice",
                    60, "Voice cloning failed, using standard TTS..."
                )
                success, dubbed_audio_path, error = tts_service.synthesize_segments(
                    translated_segments,
                    str(tts_dir),
                    language=target_lang,
                    gender=gender
                )
        else:
            # Standard TTS (no voice cloning)
            update_job_status(
                job_id, JobStatus.PROCESSING, 4, "Synthesizing Voice",
                60, "Generating dubbed voice with AI TTS..."
            )
            
            success, dubbed_audio_path, error = tts_service.synthesize_segments(
                translated_segments,
                str(tts_dir),
                language=target_lang,
                gender=gender
            )
        
        if not success:
            update_job_status(
                job_id, JobStatus.FAILED, 4, "Synthesizing Voice",
                0, "Failed to synthesize voice", error=error
            )
            return
        
        update_job_status(
            job_id, JobStatus.PROCESSING, 4, "Synthesizing Voice",
            100, "Voice synthesized successfully"
        )
        
        # ========== STEP 5: Mix & Render ==========
        update_job_status(
            job_id, JobStatus.PROCESSING, 5, "Mixing & Rendering",
            80, "Mixing audio and rendering final video..."
        )
        
        output_video_path = str(job_dir / "dubbed_video.mp4")
        
        success, error = audio_service.mix_audio(
            video_path,
            dubbed_audio_path,
            output_video_path,
            dub_volume=dub_volume,
            preserve_background=preserve_background
        )
        
        if not success:
            update_job_status(
                job_id, JobStatus.FAILED, 5, "Mixing & Rendering",
                0, "Failed to mix audio", error=error
            )
            return
        
        # ========== COMPLETE ==========
        update_job_status(
            job_id, JobStatus.COMPLETED, 5, "Complete",
            100, "Dubbing complete! Your video is ready.",
            download_ready=True
        )
        
        logger.info(f"Job {job_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Job {job_id} failed with error: {e}")
        update_job_status(
            job_id, JobStatus.FAILED, 0, "Error",
            0, "An unexpected error occurred", error=str(e)
        )


@router.post("/video-info", response_model=VideoInfoResponse)
async def get_video_info(url: str):
    """Get video information from any URL (YouTube, Vimeo, direct link, etc.)"""
    info = video_service.get_video_info(url)
    
    if info.get('success'):
        return VideoInfoResponse(
            success=True,
            title=info.get('title'),
            duration=info.get('duration'),
            thumbnail=info.get('thumbnail'),
        )
    else:
        return VideoInfoResponse(
            success=False,
            error=info.get('error', 'Failed to fetch video info')
        )


@router.post("/dub", response_model=DubbingResponse)
async def start_dubbing(
    background_tasks: BackgroundTasks,
    request: DubbingRequest
):
    """
    Start a new dubbing job from a video URL.
    Supports YouTube, Vimeo, Twitter, TikTok, direct video links, and 1000+ more sites.
    """
    job_id = str(uuid.uuid4())[:8]
    
    # Initialize job
    update_job_status(
        job_id, JobStatus.PENDING, 0, "Starting",
        0, "Initializing dubbing job..."
    )
    
    try:
        # Download video first
        update_job_status(
            job_id, JobStatus.PROCESSING, 0, "Downloading",
            5, "Downloading video from URL..."
        )
        
        success, video_path, error = video_service.download_video(request.video_url, job_id)
        
        if not success:
            update_job_status(
                job_id, JobStatus.FAILED, 0, "Download Failed",
                0, "Failed to download video", error=error
            )
            raise HTTPException(status_code=400, detail=f"Failed to download video: {error}")
        
        # Start background processing
        background_tasks.add_task(
            process_dubbing_job,
            job_id,
            video_path,
            request.source_lang,
            request.target_lang,
            request.voice_gender,
            request.preserve_background,
            request.dub_volume
        )
        
        return DubbingResponse(
            job_id=job_id,
            status=JobStatus.PROCESSING,
            message="Dubbing job started successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start dubbing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dub/upload", response_model=DubbingResponse)
async def start_dubbing_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    source_lang: str = Form("en"),
    target_lang: str = Form("hi"),
    voice_gender: str = Form("female"),
    preserve_background: bool = Form(True),
    dub_volume: int = Form(75),
):
    """Start a new dubbing job from an uploaded video file"""
    job_id = str(uuid.uuid4())[:8]
    
    try:
        # Save uploaded file
        job_dir = OUTPUTS_DIR / job_id
        job_dir.mkdir(exist_ok=True)
        
        file_ext = Path(file.filename).suffix or ".mp4"
        video_path = str(job_dir / f"original_video{file_ext}")
        
        update_job_status(
            job_id, JobStatus.PROCESSING, 0, "Uploading",
            5, "Saving uploaded video..."
        )
        
        with open(video_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        
        # Start background processing
        background_tasks.add_task(
            process_dubbing_job,
            job_id,
            video_path,
            source_lang,
            target_lang,
            voice_gender,
            preserve_background,
            dub_volume
        )
        
        return DubbingResponse(
            job_id=job_id,
            status=JobStatus.PROCESSING,
            message="Dubbing job started successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to start dubbing with upload: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Get the current status of a dubbing job"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    return JobStatusResponse(**job)


@router.get("/download/{job_id}")
async def download_dubbed_video(job_id: str):
    """Download the dubbed video"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    if not job.get("download_ready"):
        raise HTTPException(status_code=400, detail="Video not ready for download")
    
    video_path = OUTPUTS_DIR / job_id / "dubbed_video.mp4"
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")
    
    return FileResponse(
        path=str(video_path),
        media_type="video/mp4",
        filename=f"dubbed_video_{job_id}.mp4"
    )


@router.get("/download/{job_id}/subtitles")
async def download_subtitles(job_id: str, lang: str = None):
    """Download subtitles (SRT format)"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job_dir = OUTPUTS_DIR / job_id
    
    # Find subtitle file
    if lang:
        srt_path = job_dir / f"subtitles_{lang}.srt"
    else:
        # Try to find any translated subtitle
        srt_files = list(job_dir.glob("subtitles_*.srt"))
        if srt_files:
            srt_path = srt_files[0]
        else:
            raise HTTPException(status_code=404, detail="Subtitles not found")
    
    if not srt_path.exists():
        raise HTTPException(status_code=404, detail="Subtitle file not found")
    
    return FileResponse(
        path=str(srt_path),
        media_type="text/plain",
        filename=srt_path.name
    )

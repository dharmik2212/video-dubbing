"""
Pydantic models for request/response validation
"""
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class VoiceGender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    AUTO = "auto"


class DubbingRequest(BaseModel):
    """Request to start a dubbing job"""
    video_url: Optional[str] = Field(None, description="URL of video to download (YouTube, Vimeo, any supported site, or direct link)")
    source_lang: str = Field("en", description="Source language code (e.g., 'en', 'es')")
    target_lang: str = Field("hi", description="Target language code for dubbing")
    voice_gender: VoiceGender = Field(VoiceGender.FEMALE, description="Voice gender for TTS")
    preserve_background: bool = Field(True, description="Keep original background music/sounds")
    dub_volume: int = Field(75, ge=10, le=100, description="Dubbed audio volume (10-100)")


class DubbingResponse(BaseModel):
    """Response after starting a dubbing job"""
    job_id: str
    status: JobStatus
    message: str


class JobStatusResponse(BaseModel):
    """Response for job status check"""
    job_id: str
    status: JobStatus
    step: int = Field(ge=0, le=5, description="Current step (1-5)")
    step_name: str
    progress: int = Field(ge=0, le=100)
    message: str
    download_ready: bool = False
    error: Optional[str] = None


class VideoInfoResponse(BaseModel):
    """Response for video info fetch"""
    success: bool
    title: Optional[str] = None
    duration: Optional[str] = None
    thumbnail: Optional[str] = None
    error: Optional[str] = None

"""
DubMaster FastAPI Backend
AI-Powered Video Dubbing Application
"""
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file (must be before other imports)
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import logging

from routers import dubbing
from config import UPLOADS_DIR, OUTPUTS_DIR

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="DubMaster API",
    description="AI-Powered Video Dubbing Backend - Supports 1000+ video sites",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware (allow frontend to access API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(dubbing.router)

# Serve static files (frontend)
FRONTEND_DIR = Path(__file__).parent.parent

# Mount outputs for video downloads
app.mount("/outputs", StaticFiles(directory=str(OUTPUTS_DIR)), name="outputs")


@app.get("/")
async def serve_frontend():
    """Serve the main frontend page"""
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "DubMaster API is running. Visit /docs for API documentation."}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "DubMaster API"}


@app.get("/{filename}")
async def serve_static(filename: str):
    """Serve static frontend files (CSS, JS)"""
    file_path = FRONTEND_DIR / filename
    if file_path.exists() and file_path.is_file():
        # Determine content type
        content_types = {
            '.html': 'text/html',
            '.css': 'text/css',
            '.js': 'application/javascript',
            '.json': 'application/json',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.svg': 'image/svg+xml',
            '.ico': 'image/x-icon',
        }
        content_type = content_types.get(file_path.suffix.lower(), 'text/plain')
        return FileResponse(str(file_path), media_type=content_type)
    return {"error": "File not found"}


if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting DubMaster API server...")
    logger.info(f"Frontend directory: {FRONTEND_DIR}")
    logger.info(f"Outputs directory: {OUTPUTS_DIR}")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

from fastapi import APIRouter

router = APIRouter()

@router.get("/health-check")
def health_check():
    return {
        "service": "Maritime Agentic Control API",
        "status": "healthy",
        "version": "1.0.0"
    }

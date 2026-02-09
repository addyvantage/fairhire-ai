from fastapi import APIRouter

from app.schemas.common import Message

router = APIRouter()


@router.get("/health", response_model=Message)
async def healthcheck() -> Message:
    return Message(message="ok")

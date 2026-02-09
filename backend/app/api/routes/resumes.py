import os

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.resume import Resume
from app.models.user import User
from app.schemas.resume import ResumeOut
from app.services.resume_parser import BasicResumeParser
from app.utils.storage import LocalStorageService

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".docx"}


@router.post("/upload", response_model=ResumeOut, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Resume:
    extension = os.path.splitext(file.filename or "")[1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported")

    content = await file.read()
    max_size_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_size_bytes:
        raise HTTPException(status_code=413, detail="Uploaded file exceeds configured max size")

    storage = LocalStorageService()
    parser = BasicResumeParser()

    stored_path = await storage.save_upload(file.filename or "resume", content)
    extracted_text = await parser.parse(content, file.filename or "resume")

    resume = Resume(
        user_id=current_user.id,
        original_filename=file.filename or "resume",
        stored_path=stored_path,
        extracted_text=extracted_text,
    )
    db.add(resume)
    await db.commit()
    await db.refresh(resume)
    return resume


@router.get("", response_model=list[ResumeOut])
async def list_resumes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Resume]:
    result = await db.execute(select(Resume).where(Resume.user_id == current_user.id).order_by(Resume.created_at.desc()))
    return list(result.scalars().all())

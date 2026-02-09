from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_db_session
from app.models.resume import Resume
from app.models.user import User
from app.schemas.resume import ResumeOut
from app.services.resume_parser import ResumeParserService

router = APIRouter()


@router.post("/upload", response_model=ResumeOut, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Resume:
    allowed_ext = {".pdf", ".docx"}
    ext = Path(file.filename or "").suffix.lower()
    if ext not in allowed_ext:
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    settings = get_settings()
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    generated_name = f"{uuid4()}{ext}"
    storage_path = upload_dir / generated_name
    storage_path.write_bytes(content)

    parser = ResumeParserService()
    parsed_text = await parser.parse(file.filename or generated_name, content)

    resume = Resume(
        user_id=user.id,
        original_filename=file.filename or generated_name,
        storage_path=str(storage_path),
        parsed_text=parsed_text,
    )
    db.add(resume)
    await db.commit()
    await db.refresh(resume)
    return resume


@router.get("", response_model=list[ResumeOut])
async def list_resumes(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)
) -> list[Resume]:
    result = await db.execute(select(Resume).where(Resume.user_id == user.id).order_by(Resume.id.desc()))
    return list(result.scalars().all())

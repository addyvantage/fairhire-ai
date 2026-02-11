from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from rq import Retry
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_db_session
from app.models.resume import Resume
from app.models.resume_studio import ResumeStudioExport, ResumeStudioProject, ResumeStudioVersion
from app.models.user import User
from app.schemas.resume_studio import (
    StudioExportOut,
    StudioExportSummary,
    StudioImportResponse,
    StudioProjectCreate,
    StudioProjectDetailOut,
    StudioProjectOut,
    StudioProjectUpdate,
    StudioTailorRequest,
    StudioVersionCreate,
    StudioVersionOut,
    StudioVersionUpdate,
)
from app.services.resume_studio import ResumeStudioService, default_structured_resume
from app.workers.job_handlers import run_resume_studio_export_job
from app.workers.queue import get_queue, get_redis_connection

router = APIRouter()


def _project_to_out(
    project: ResumeStudioProject,
    latest_version: ResumeStudioVersion | None,
    tailored_tags: list[str],
    versions_count: int = 0,
    last_export_status: str | None = None,
) -> StudioProjectOut:
    return StudioProjectOut(
        id=project.id,
        user_id=project.user_id,
        title=project.title,
        source_type=project.source_type,
        base_resume_id=project.base_resume_id,
        created_at=project.created_at,
        updated_at=project.updated_at,
        latest_version_id=latest_version.id if latest_version else None,
        latest_version_kind=latest_version.kind if latest_version else None,
        latest_version_created_at=latest_version.created_at if latest_version else None,
        tailored_tags=tailored_tags,
        versions_count=versions_count,
        last_export_status=last_export_status,
    )


def _version_to_out(
    version: ResumeStudioVersion,
    latest_export: ResumeStudioExport | None = None,
) -> StudioVersionOut:
    label = None
    if isinstance(version.template_settings_json, dict):
        raw_label = version.template_settings_json.get("version_label")
        if isinstance(raw_label, str) and raw_label.strip():
            label = raw_label.strip()

    if not label and version.kind == "tailored":
        role_title = (version.jd_structured_json or {}).get("role_title")
        if isinstance(role_title, str) and role_title.strip():
            label = f"{role_title.strip()} — {version.created_at.strftime('%b %d')}"

    export_summary = None
    if latest_export is not None:
        export_summary = StudioExportSummary(
            id=latest_export.id,
            format=latest_export.format,
            status=latest_export.status,
            created_at=latest_export.created_at,
            completed_at=latest_export.completed_at,
        )

    return StudioVersionOut(
        id=version.id,
        project_id=version.project_id,
        kind=version.kind,
        job_profile_id=version.job_profile_id,
        jd_text_hash=version.jd_text_hash,
        jd_structured_json=version.jd_structured_json,
        resume_structured_json=version.resume_structured_json,
        resume_render_html=version.resume_render_html,
        resume_plain_text=version.resume_plain_text,
        score_snapshot_json=version.score_snapshot_json,
        template_name=version.template_name,
        template_settings_json=version.template_settings_json,
        version_label=label,
        latest_export=export_summary,
        created_at=version.created_at,
    )


def _export_to_out(export: ResumeStudioExport) -> StudioExportOut:
    download_url = (
        f"/api/v1/studio/exports/{export.id}/download" if export.status == "completed" and export.file_path else None
    )
    return StudioExportOut(
        id=export.id,
        version_id=export.version_id,
        format=export.format,
        status=export.status,
        job_id=export.job_id,
        file_path=export.file_path,
        download_url=download_url,
        error_message=export.error_message,
        created_at=export.created_at,
        completed_at=export.completed_at,
    )


async def _get_owned_project(
    db: AsyncSession,
    user_id: int,
    project_id: int,
) -> ResumeStudioProject:
    result = await db.execute(
        select(ResumeStudioProject).where(
            ResumeStudioProject.id == project_id,
            ResumeStudioProject.user_id == user_id,
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Studio project not found")
    return project


async def _get_owned_version(
    db: AsyncSession,
    user_id: int,
    version_id: int,
) -> tuple[ResumeStudioProject, ResumeStudioVersion]:
    result = await db.execute(
        select(ResumeStudioVersion, ResumeStudioProject)
        .join(ResumeStudioProject, ResumeStudioProject.id == ResumeStudioVersion.project_id)
        .where(
            ResumeStudioVersion.id == version_id,
            ResumeStudioProject.user_id == user_id,
        )
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=404, detail="Studio version not found")
    version, project = row
    return project, version


async def _get_latest_exports_by_version(
    db: AsyncSession,
    version_ids: list[int],
) -> dict[int, ResumeStudioExport]:
    if not version_ids:
        return {}
    result = await db.execute(
        select(ResumeStudioExport)
        .where(ResumeStudioExport.version_id.in_(version_ids))
        .order_by(desc(ResumeStudioExport.created_at), desc(ResumeStudioExport.id))
    )
    latest: dict[int, ResumeStudioExport] = {}
    for export in result.scalars().all():
        latest.setdefault(export.version_id, export)
    return latest


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@router.post("/projects", response_model=StudioProjectOut, status_code=status.HTTP_201_CREATED)
async def create_studio_project(
    payload: StudioProjectCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> StudioProjectOut:
    service = ResumeStudioService()
    title = payload.title.strip()
    source_type = payload.source_type
    base_structured = default_structured_resume(title)

    if payload.base_resume_id is not None:
        resume_result = await db.execute(
            select(Resume).where(Resume.id == payload.base_resume_id, Resume.user_id == user.id)
        )
        base_resume = resume_result.scalar_one_or_none()
        if base_resume is None:
            raise HTTPException(status_code=404, detail="Base resume not found")
        base_structured = service.parse_resume_text(base_resume.parsed_text, title_hint=title)

    project = ResumeStudioProject(
        user_id=user.id,
        title=title,
        source_type=source_type,
        base_resume_id=payload.base_resume_id,
    )
    db.add(project)
    await db.flush()

    version = ResumeStudioVersion(
        project_id=project.id,
        kind="base",
        resume_structured_json=base_structured,
        resume_plain_text=service.structured_to_plain_text(base_structured),
        resume_render_html=service.render_resume_html(base_structured, template_name="ats_classic"),
        template_name="ats_classic",
        template_settings_json=None,
    )
    db.add(version)
    await db.commit()
    await db.refresh(project)
    await db.refresh(version)
    return _project_to_out(
        project=project,
        latest_version=version,
        tailored_tags=[],
        versions_count=1,
        last_export_status=None,
    )


@router.patch("/projects/{project_id}", response_model=StudioProjectOut)
async def update_studio_project(
    project_id: int,
    payload: StudioProjectUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> StudioProjectOut:
    project = await _get_owned_project(db=db, user_id=user.id, project_id=project_id)
    project.title = payload.title.strip()
    project.updated_at = _utc_now()
    await db.commit()
    await db.refresh(project)

    latest_result = await db.execute(
        select(ResumeStudioVersion)
        .where(ResumeStudioVersion.project_id == project.id)
        .order_by(desc(ResumeStudioVersion.created_at), desc(ResumeStudioVersion.id))
        .limit(1)
    )
    latest_version = latest_result.scalar_one_or_none()

    versions_count_result = await db.execute(
        select(ResumeStudioVersion.id).where(ResumeStudioVersion.project_id == project.id)
    )
    version_ids = [row[0] for row in versions_count_result.all()]
    latest_exports = await _get_latest_exports_by_version(db=db, version_ids=version_ids)
    last_export_status = (
        latest_exports.get(latest_version.id).status
        if latest_version is not None and latest_version.id in latest_exports
        else None
    )
    return _project_to_out(
        project=project,
        latest_version=latest_version,
        tailored_tags=[],
        versions_count=len(version_ids),
        last_export_status=last_export_status,
    )


@router.get("/projects", response_model=list[StudioProjectOut])
async def list_studio_projects(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[StudioProjectOut]:
    result = await db.execute(
        select(ResumeStudioProject)
        .where(ResumeStudioProject.user_id == user.id)
        .order_by(desc(ResumeStudioProject.updated_at), desc(ResumeStudioProject.id))
    )
    projects = list(result.scalars().all())
    if not projects:
        return []

    project_ids = [project.id for project in projects]
    versions_result = await db.execute(
        select(ResumeStudioVersion)
        .where(ResumeStudioVersion.project_id.in_(project_ids))
        .order_by(desc(ResumeStudioVersion.created_at), desc(ResumeStudioVersion.id))
    )
    versions = list(versions_result.scalars().all())
    latest_by_project: dict[int, ResumeStudioVersion] = {}
    tags_by_project: dict[int, list[str]] = {project_id: [] for project_id in project_ids}
    count_by_project: dict[int, int] = {project_id: 0 for project_id in project_ids}
    for version in versions:
        count_by_project[version.project_id] = count_by_project.get(version.project_id, 0) + 1
        latest_by_project.setdefault(version.project_id, version)
        if version.kind == "tailored":
            role = (
                (version.jd_structured_json or {}).get("role_title")
                or (version.jd_structured_json or {}).get("normalized_title")
                or "Tailored"
            )
            tags_by_project[version.project_id].append(str(role))
    latest_exports_by_version = await _get_latest_exports_by_version(
        db=db,
        version_ids=[version.id for version in versions],
    )

    return [
        _project_to_out(
            project=project,
            latest_version=latest_by_project.get(project.id),
            tailored_tags=tags_by_project.get(project.id, [])[:3],
            versions_count=count_by_project.get(project.id, 0),
            last_export_status=(
                latest_exports_by_version[latest_by_project[project.id].id].status
                if latest_by_project.get(project.id) is not None
                and latest_by_project[project.id].id in latest_exports_by_version
                else None
            ),
        )
        for project in projects
    ]


@router.get("/projects/{project_id}", response_model=StudioProjectDetailOut)
async def get_studio_project_detail(
    project_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> StudioProjectDetailOut:
    project = await _get_owned_project(db=db, user_id=user.id, project_id=project_id)
    versions_result = await db.execute(
        select(ResumeStudioVersion)
        .where(ResumeStudioVersion.project_id == project.id)
        .order_by(desc(ResumeStudioVersion.created_at), desc(ResumeStudioVersion.id))
    )
    versions = list(versions_result.scalars().all())
    latest_exports_by_version = await _get_latest_exports_by_version(
        db=db,
        version_ids=[version.id for version in versions],
    )
    latest = versions[0] if versions else None
    tags = [
        str(((version.jd_structured_json or {}).get("role_title") or "Tailored"))
        for version in versions
        if version.kind == "tailored"
    ]
    return StudioProjectDetailOut(
        project=_project_to_out(
            project=project,
            latest_version=latest,
            tailored_tags=tags[:3],
            versions_count=len(versions),
            last_export_status=(
                latest_exports_by_version[latest.id].status
                if latest is not None and latest.id in latest_exports_by_version
                else None
            ),
        ),
        versions=[
            _version_to_out(version, latest_export=latest_exports_by_version.get(version.id))
            for version in versions
        ],
    )


@router.post("/projects/{project_id}/import", response_model=StudioImportResponse)
async def import_into_studio_project(
    project_id: int,
    text: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> StudioImportResponse:
    if text is None and file is None:
        raise HTTPException(status_code=400, detail="Provide either text or a file to import")

    service = ResumeStudioService()
    settings = get_settings()
    project = await _get_owned_project(db=db, user_id=user.id, project_id=project_id)

    parsed_text = (text or "").strip()
    source_type = "import_text"

    if file is not None:
        ext = Path(file.filename or "").suffix.lower()
        if ext not in {".pdf", ".docx", ".txt"}:
            raise HTTPException(status_code=400, detail="Only PDF, DOCX, or TXT files are supported")

        content = await file.read()
        max_size = settings.studio_max_upload_mb * 1024 * 1024
        if len(content) > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds {settings.studio_max_upload_mb}MB upload limit",
            )
        if not content:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

        parsed_text = await service.parse_upload(file.filename or "resume.txt", content)
        source_type = "import_pdf" if ext == ".pdf" else ("import_docx" if ext == ".docx" else "import_text")

    if not parsed_text.strip():
        raise HTTPException(status_code=400, detail="No readable text found for import")

    structured = service.parse_resume_text(parsed_text, title_hint=project.title)
    template_name = "modern_clean" if source_type.startswith("import_") else "ats_classic"
    render_html = service.render_resume_html(
        structured_resume=structured,
        template_name=template_name,
        template_settings=None,
    )

    version = ResumeStudioVersion(
        project_id=project.id,
        kind="base",
        resume_structured_json=structured,
        resume_plain_text=service.structured_to_plain_text(structured),
        resume_render_html=render_html,
        template_name=template_name,
        template_settings_json=None,
    )
    project.source_type = source_type
    project.updated_at = _utc_now()
    db.add(version)
    await db.commit()
    await db.refresh(project)
    await db.refresh(version)
    version_count_result = await db.execute(
        select(ResumeStudioVersion.id).where(ResumeStudioVersion.project_id == project.id)
    )
    version_count = len(version_count_result.all())

    return StudioImportResponse(
        project=_project_to_out(
            project=project,
            latest_version=version,
            tailored_tags=[],
            versions_count=version_count,
            last_export_status=None,
        ),
        version=_version_to_out(version, latest_export=None),
    )


@router.post("/projects/{project_id}/versions", response_model=StudioVersionOut, status_code=status.HTTP_201_CREATED)
async def create_studio_version(
    project_id: int,
    payload: StudioVersionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> StudioVersionOut:
    project = await _get_owned_project(db=db, user_id=user.id, project_id=project_id)
    service = ResumeStudioService()

    source_version: ResumeStudioVersion | None = None
    if payload.source_version_id is not None:
        source_result = await db.execute(
            select(ResumeStudioVersion).where(
                ResumeStudioVersion.id == payload.source_version_id,
                ResumeStudioVersion.project_id == project.id,
            )
        )
        source_version = source_result.scalar_one_or_none()
        if source_version is None:
            raise HTTPException(status_code=404, detail="Source version not found")
    else:
        latest_result = await db.execute(
            select(ResumeStudioVersion)
            .where(ResumeStudioVersion.project_id == project.id)
            .order_by(desc(ResumeStudioVersion.created_at), desc(ResumeStudioVersion.id))
            .limit(1)
        )
        source_version = latest_result.scalar_one_or_none()

    base_structured = (
        source_version.resume_structured_json
        if source_version is not None
        else default_structured_resume(project.title)
    )
    template_name = payload.template_name or (source_version.template_name if source_version else "ats_classic")
    template_settings = payload.template_settings or (
        source_version.template_settings_json if source_version else None
    )

    version = ResumeStudioVersion(
        project_id=project.id,
        kind=payload.kind,
        job_profile_id=payload.job_profile_id,
        resume_structured_json=base_structured,
        resume_plain_text=service.structured_to_plain_text(base_structured),
        resume_render_html=service.render_resume_html(base_structured, template_name, template_settings),
        template_name=template_name,
        template_settings_json=template_settings,
    )
    db.add(version)
    project.updated_at = _utc_now()
    await db.commit()
    await db.refresh(version)
    return _version_to_out(version, latest_export=None)


@router.patch("/versions/{version_id}", response_model=StudioVersionOut)
async def update_studio_version(
    version_id: int,
    payload: StudioVersionUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> StudioVersionOut:
    project, version = await _get_owned_version(db=db, user_id=user.id, version_id=version_id)
    service = ResumeStudioService()
    structured = service.ensure_schema(payload.resume_structured_json.model_dump())
    template_name = payload.template_name or version.template_name
    template_settings = payload.template_settings if payload.template_settings is not None else version.template_settings_json

    version.resume_structured_json = structured
    version.resume_plain_text = service.structured_to_plain_text(structured)
    version.resume_render_html = service.render_resume_html(
        structured_resume=structured,
        template_name=template_name,
        template_settings=template_settings,
    )
    version.template_name = template_name
    version.template_settings_json = template_settings
    project.updated_at = _utc_now()

    await db.commit()
    await db.refresh(version)
    latest_export_map = await _get_latest_exports_by_version(db=db, version_ids=[version.id])
    return _version_to_out(version, latest_export=latest_export_map.get(version.id))


@router.post("/versions/{version_id}/tailor", response_model=StudioVersionOut, status_code=status.HTTP_201_CREATED)
async def tailor_studio_version(
    version_id: int,
    payload: StudioTailorRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> StudioVersionOut:
    project, source_version = await _get_owned_version(db=db, user_id=user.id, version_id=version_id)
    service = ResumeStudioService()
    template_name = payload.template_name or source_version.template_name
    template_settings = payload.template_settings or source_version.template_settings_json

    tailored = service.tailor_resume(
        base_structured_resume=source_version.resume_structured_json,
        jd_text=payload.jd_text,
        strict_mode=payload.strict_mode,
    )
    tailored_html = service.render_resume_html(
        structured_resume=tailored["resume_structured_json"],
        template_name=template_name,
        template_settings=template_settings,
    )
    new_version = ResumeStudioVersion(
        project_id=project.id,
        kind="tailored",
        job_profile_id=payload.job_profile_id or source_version.job_profile_id,
        jd_text_hash=tailored["jd_text_hash"],
        jd_structured_json=tailored["jd_structured_json"],
        resume_structured_json=tailored["resume_structured_json"],
        resume_plain_text=tailored["resume_plain_text"],
        resume_render_html=tailored_html,
        score_snapshot_json=tailored["score_snapshot_json"],
        template_name=template_name,
        template_settings_json=template_settings,
    )
    db.add(new_version)
    project.updated_at = _utc_now()
    await db.commit()
    await db.refresh(new_version)
    return _version_to_out(new_version, latest_export=None)


@router.delete("/versions/{version_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_studio_version(
    version_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    project, version = await _get_owned_version(db=db, user_id=user.id, version_id=version_id)
    version_rows = await db.execute(
        select(ResumeStudioVersion.id).where(ResumeStudioVersion.project_id == project.id)
    )
    version_ids = [row[0] for row in version_rows.all()]
    if len(version_ids) <= 1:
        raise HTTPException(status_code=409, detail="At least one version must remain in a project")

    await db.delete(version)
    project.updated_at = _utc_now()
    await db.commit()


@router.get("/versions/{version_id}/exports", response_model=list[StudioExportOut])
async def list_studio_version_exports(
    version_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[StudioExportOut]:
    _project, version = await _get_owned_version(db=db, user_id=user.id, version_id=version_id)
    result = await db.execute(
        select(ResumeStudioExport)
        .where(ResumeStudioExport.version_id == version.id)
        .order_by(desc(ResumeStudioExport.created_at), desc(ResumeStudioExport.id))
    )
    exports = list(result.scalars().all())
    return [_export_to_out(export) for export in exports]


@router.post("/versions/{version_id}/export", response_model=StudioExportOut, status_code=status.HTTP_202_ACCEPTED)
async def queue_studio_export(
    version_id: int,
    format: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> StudioExportOut:
    _project, version = await _get_owned_version(db=db, user_id=user.id, version_id=version_id)
    export_format = format.strip().lower()
    if export_format not in {"pdf", "docx"}:
        raise HTTPException(status_code=400, detail="format must be 'pdf' or 'docx'")

    export = ResumeStudioExport(
        version_id=version.id,
        format=export_format,
        status="queued",
    )
    db.add(export)
    await db.flush()
    export_id = export.id

    try:
        settings = get_settings()
        conn = get_redis_connection()
        queue = get_queue(connection=conn)
        job = queue.enqueue(
            run_resume_studio_export_job,
            export_id,
            job_id=f"studio-export-{export_id}",
            retry=Retry(max=settings.async_job_retry_max, interval=settings.async_job_retry_interval),
            job_timeout="8m",
        )
        export.job_id = job.id
        await db.commit()
    except Exception as exc:
        await db.rollback()
        export = await db.get(ResumeStudioExport, export_id)
        if export is None:
            raise HTTPException(status_code=500, detail="Failed to create export record") from exc
        export.status = "failed"
        export.error_message = f"Failed to enqueue export: {exc}"
        await db.commit()
        if isinstance(exc, RuntimeError):
            raise HTTPException(status_code=503, detail="Export queue unavailable") from exc
        raise HTTPException(status_code=500, detail="Failed to enqueue export") from exc

    await db.refresh(export)
    return _export_to_out(export)


@router.get("/exports/{export_id}", response_model=StudioExportOut)
async def get_studio_export(
    export_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> StudioExportOut:
    result = await db.execute(
        select(ResumeStudioExport)
        .join(ResumeStudioVersion, ResumeStudioVersion.id == ResumeStudioExport.version_id)
        .join(ResumeStudioProject, ResumeStudioProject.id == ResumeStudioVersion.project_id)
        .where(
            and_(
                ResumeStudioExport.id == export_id,
                ResumeStudioProject.user_id == user.id,
            )
        )
    )
    export = result.scalar_one_or_none()
    if export is None:
        raise HTTPException(status_code=404, detail="Export not found")
    return _export_to_out(export)


@router.get("/exports/{export_id}/download")
async def download_studio_export(
    export_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> FileResponse:
    result = await db.execute(
        select(ResumeStudioExport)
        .join(ResumeStudioVersion, ResumeStudioVersion.id == ResumeStudioExport.version_id)
        .join(ResumeStudioProject, ResumeStudioProject.id == ResumeStudioVersion.project_id)
        .where(
            and_(
                ResumeStudioExport.id == export_id,
                ResumeStudioProject.user_id == user.id,
            )
        )
    )
    export = result.scalar_one_or_none()
    if export is None:
        raise HTTPException(status_code=404, detail="Export not found")
    if export.status != "completed" or not export.file_path:
        raise HTTPException(status_code=409, detail="Export is not ready yet")

    path = Path(export.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Export file is missing")

    media_type = "application/pdf" if export.format == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return FileResponse(
        path=str(path),
        media_type=media_type,
        filename=path.name,
    )

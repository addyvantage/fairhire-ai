"use client"

import Link from "next/link"
import { useEffect, useMemo, useRef, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import {
  AlertCircle,
  ArrowDown,
  ArrowUp,
  CheckCircle2,
  ClipboardList,
  CopyPlus,
  Download,
  Eye,
  EyeOff,
  FileJson2,
  Loader2,
  Pencil,
  Plus,
  RefreshCw,
  Save,
  ShieldCheck,
  Sparkles,
  Trash2,
  Undo2,
  WandSparkles,
  X,
} from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import {
  JobTargetPreview,
  ResumeStudioStructuredResume,
  StudioExport,
  StudioProjectDetail,
  StudioVersion,
  createStudioVersion,
  deleteStudioVersion,
  downloadStudioExportBlob,
  getStudioExport,
  getStudioProject,
  listStudioVersionExports,
  parseJobProfilePreview,
  requestStudioExport,
  tailorStudioVersion,
  updateStudioProject,
  updateStudioVersion,
} from "@/lib/api"
import {
  StudioSuggestion,
  StudioTemplateSettings,
  TemplateName,
  applySuggestionToResume,
  bulletImpactLevel,
  cloneStructuredResume,
  collectResumeDiagnostics,
  createEmptyStructuredResume,
  diffStructuredResumes,
  groupSuggestions,
  normalizeTemplateSettings,
  renderResumeHtmlClient,
} from "@/lib/resume-studio"
import { cn } from "@/lib/utils"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/ui/empty-state"
import { Input } from "@/components/ui/input"
import { PageTransition } from "@/components/ui/page-transition"
import { SectionCard } from "@/components/ui/section-card"
import { SegmentedControl } from "@/components/ui/segmented-control"
import { Skeleton } from "@/components/ui/skeleton"
import { useToast } from "@/components/ui/use-toast"

type WorkspaceTab = "edit" | "preview" | "tailor" | "versions"
type EditSection =
  | "profile"
  | "summary"
  | "skills"
  | "experience"
  | "projects"
  | "education"
  | "certifications"
type SaveState = "saved" | "saving" | "error"

const EDIT_SECTIONS: Array<{ value: EditSection; label: string }> = [
  { value: "profile", label: "Profile" },
  { value: "summary", label: "Summary" },
  { value: "skills", label: "Skills" },
  { value: "experience", label: "Experience" },
  { value: "projects", label: "Projects" },
  { value: "education", label: "Education" },
  { value: "certifications", label: "Extras" },
]

const TEMPLATE_OPTIONS: Array<{ label: string; value: TemplateName }> = [
  { label: "ATS Classic", value: "ats_classic" },
  { label: "Modern Clean", value: "modern_clean" },
  { label: "Compact Onepager", value: "compact_onepager" },
]

function formatDateTime(value: string | null | undefined) {
  if (!value) return "—"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "—"
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  })
}

function StudioEditorSkeleton() {
  return (
    <DashboardLayout title="Resume Studio" description="Loading workspace...">
      <div className="mx-auto w-full max-w-7xl space-y-5">
        <Skeleton className="h-12 w-80 rounded-xl" />
        <div className="grid gap-5 lg:grid-cols-[1.2fr_0.8fr]">
          <Skeleton className="h-[640px] w-full rounded-[var(--radius)]" />
          <Skeleton className="h-[640px] w-full rounded-[var(--radius)]" />
        </div>
      </div>
    </DashboardLayout>
  )
}

function moveItem<T>(items: T[], from: number, to: number) {
  if (to < 0 || to >= items.length) return items
  const next = [...items]
  const [entry] = next.splice(from, 1)
  next.splice(to, 0, entry)
  return next
}

function exportStatusPill(status: StudioExport["status"]) {
  const styles =
    status === "completed"
      ? "bg-emerald-50 text-emerald-700"
      : status === "failed"
        ? "bg-rose-50 text-rose-700"
        : "bg-amber-50 text-amber-700"
  return <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium capitalize ${styles}`}>{status}</span>
}

export default function StudioProjectEditorPage() {
  const params = useParams()
  const projectId = Number(params.projectId)
  const router = useRouter()
  const { token, isAuthenticated, isLoading } = useAuth()
  const { toast } = useToast()

  const [projectDetail, setProjectDetail] = useState<StudioProjectDetail | null>(null)
  const [selectedVersionId, setSelectedVersionId] = useState<number | null>(null)
  const [structured, setStructured] = useState<ResumeStudioStructuredResume | null>(null)
  const [workspaceTab, setWorkspaceTab] = useState<WorkspaceTab>("edit")
  const [activeSection, setActiveSection] = useState<EditSection>("profile")
  const [templateName, setTemplateName] = useState<TemplateName>("ats_classic")
  const [templateSettings, setTemplateSettings] = useState<StudioTemplateSettings>(
    normalizeTemplateSettings(null)
  )
  const [projectTitleDraft, setProjectTitleDraft] = useState("")
  const [editingProjectTitle, setEditingProjectTitle] = useState(false)
  const [loadingProject, setLoadingProject] = useState(true)
  const [saveState, setSaveState] = useState<SaveState>("saved")
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null)
  const [undoStack, setUndoStack] = useState<ResumeStudioStructuredResume[]>([])
  const [creatingVersion, setCreatingVersion] = useState(false)
  const [deletingVersionId, setDeletingVersionId] = useState<number | null>(null)
  const [renamingVersionId, setRenamingVersionId] = useState<number | null>(null)
  const [renameVersionLabelDraft, setRenameVersionLabelDraft] = useState("")

  const [jdText, setJdText] = useState("")
  const [jdRoleTitle, setJdRoleTitle] = useState("")
  const [strictMode, setStrictMode] = useState(true)
  const [parsingJd, setParsingJd] = useState(false)
  const [jdPreview, setJdPreview] = useState<JobTargetPreview | null>(null)
  const [tailoring, setTailoring] = useState(false)

  const [conditionalSuggestion, setConditionalSuggestion] = useState<StudioSuggestion | null>(
    null
  )
  const [conditionalProof, setConditionalProof] = useState("")
  const [compareMode, setCompareMode] = useState(false)

  const [versionExports, setVersionExports] = useState<StudioExport[]>([])
  const [loadingExports, setLoadingExports] = useState(false)
  const [activeExportId, setActiveExportId] = useState<number | null>(null)
  const [activeExportProgress, setActiveExportProgress] = useState(0)
  const [previewModalMode, setPreviewModalMode] = useState<"html" | "pdf" | null>(null)
  const [previewPdfUrl, setPreviewPdfUrl] = useState<string | null>(null)

  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastSavedVersionRef = useRef<string>("")
  const lastProjectLoadRef = useRef<number>(0)

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login")
    }
  }, [isLoading, isAuthenticated, router])

  const selectedVersion = useMemo(() => {
    if (!projectDetail || selectedVersionId == null) return null
    return projectDetail.versions.find((version) => version.id === selectedVersionId) ?? null
  }, [projectDetail, selectedVersionId])

  const baseVersion = useMemo(() => {
    if (!projectDetail) return null
    const baseVersions = projectDetail.versions.filter((version) => version.kind === "base")
    return baseVersions.length ? baseVersions[baseVersions.length - 1] : null
  }, [projectDetail])

  const previewHtml = useMemo(() => {
    if (!structured) return ""
    return renderResumeHtmlClient(structured, templateName, templateSettings)
  }, [structured, templateName, templateSettings])

  const basePreviewHtml = useMemo(() => {
    if (!baseVersion) return ""
    return renderResumeHtmlClient(
      baseVersion.resume_structured_json,
      (baseVersion.template_name as TemplateName) ?? "ats_classic",
      baseVersion.template_settings_json
    )
  }, [baseVersion])

  const diagnostics = useMemo(
    () => (structured ? collectResumeDiagnostics(structured) : null),
    [structured]
  )

  const diffSummary = useMemo(() => {
    if (!structured || !baseVersion || selectedVersion?.kind !== "tailored") return null
    return diffStructuredResumes(baseVersion.resume_structured_json, structured)
  }, [baseVersion, selectedVersion?.kind, structured])

  const suggestionGroups = useMemo(
    () => groupSuggestions((selectedVersion?.score_snapshot_json as Record<string, unknown>) ?? null),
    [selectedVersion?.score_snapshot_json]
  )

  useEffect(() => {
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
      if (previewPdfUrl) URL.revokeObjectURL(previewPdfUrl)
    }
  }, [previewPdfUrl])

  async function loadProject(force = false) {
    if (!token || !projectId) return
    const requestId = Date.now()
    lastProjectLoadRef.current = requestId
    if (!force) setLoadingProject(true)
    try {
      const detail = await getStudioProject(token, projectId)
      if (lastProjectLoadRef.current !== requestId) return
      setProjectDetail(detail)
      setProjectTitleDraft(detail.project.title)
      setSelectedVersionId((current) => current ?? detail.versions[0]?.id ?? null)
      setJdRoleTitle((current) => current || detail.project.title)
    } catch (error) {
      toast({
        title: "Unable to load project",
        description: (error as Error).message,
        variant: "destructive",
      })
    } finally {
      if (lastProjectLoadRef.current === requestId) {
        setLoadingProject(false)
      }
    }
  }

  useEffect(() => {
    loadProject()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, projectId])

  useEffect(() => {
    if (!selectedVersion) return
    setStructured(cloneStructuredResume(selectedVersion.resume_structured_json))
    setTemplateName((selectedVersion.template_name as TemplateName) ?? "ats_classic")
    setTemplateSettings(normalizeTemplateSettings(selectedVersion.template_settings_json))
    setLastSavedAt(selectedVersion.created_at)
    setSaveState("saved")
    setUndoStack([])
    const payload = JSON.stringify({
      structured: selectedVersion.resume_structured_json,
      templateName: selectedVersion.template_name,
      templateSettings: normalizeTemplateSettings(selectedVersion.template_settings_json),
    })
    lastSavedVersionRef.current = payload
  }, [selectedVersion])

  useEffect(() => {
    if (!token || !selectedVersion) return
    setLoadingExports(true)
    listStudioVersionExports(token, selectedVersion.id)
      .then((exports) => setVersionExports(exports))
      .catch(() => setVersionExports([]))
      .finally(() => setLoadingExports(false))
  }, [token, selectedVersion])

  useEffect(() => {
    if (!token || !selectedVersion || !structured) return
    const payload = JSON.stringify({
      structured,
      templateName,
      templateSettings,
    })
    if (payload === lastSavedVersionRef.current) return

    if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    saveTimerRef.current = setTimeout(async () => {
      try {
        setSaveState("saving")
        const updated = await updateStudioVersion(token, selectedVersion.id, {
          resume_structured_json: structured,
          template_name: templateName,
          template_settings: templateSettings,
        })
        setProjectDetail((previous) => {
          if (!previous) return previous
          return {
            ...previous,
            project: {
              ...previous.project,
              updated_at: new Date().toISOString(),
            },
            versions: previous.versions.map((entry) =>
              entry.id === updated.id ? updated : entry
            ),
          }
        })
        setLastSavedAt(new Date().toISOString())
        setSaveState("saved")
        lastSavedVersionRef.current = JSON.stringify({
          structured: updated.resume_structured_json,
          templateName: updated.template_name,
          templateSettings: normalizeTemplateSettings(updated.template_settings_json),
        })
      } catch (error) {
        setSaveState("error")
        toast({
          title: "Autosave failed",
          description: (error as Error).message,
          variant: "destructive",
        })
      }
    }, 820)

    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    }
  }, [token, selectedVersion, structured, templateName, templateSettings, toast])

  async function commitProjectTitle() {
    if (!token || !projectDetail) return
    const title = projectTitleDraft.trim()
    if (!title || title === projectDetail.project.title) {
      setEditingProjectTitle(false)
      return
    }
    try {
      const updated = await updateStudioProject(token, projectDetail.project.id, { title })
      setProjectDetail((previous) => {
        if (!previous) return previous
        return { ...previous, project: updated }
      })
      setEditingProjectTitle(false)
      toast({ title: "Project title updated" })
    } catch (error) {
      toast({
        title: "Unable to update title",
        description: (error as Error).message,
        variant: "destructive",
      })
    }
  }

  function pushUndoSnapshot() {
    if (!structured) return
    setUndoStack((previous) => [...previous.slice(-19), cloneStructuredResume(structured)])
  }

  function applyStructured(next: ResumeStudioStructuredResume) {
    setStructured(next)
  }

  function handleUndo() {
    setUndoStack((previous) => {
      if (previous.length === 0) return previous
      const nextStack = [...previous]
      const previousSnapshot = nextStack.pop()
      if (previousSnapshot) {
        setStructured(previousSnapshot)
        toast({ title: "Reverted last Studio change" })
      }
      return nextStack
    })
  }

  function removeExperience(index: number) {
    if (!structured) return
    pushUndoSnapshot()
    const next = cloneStructuredResume(structured)
    next.experience.items.splice(index, 1)
    applyStructured(next)
  }

  function removeProject(index: number) {
    if (!structured) return
    pushUndoSnapshot()
    const next = cloneStructuredResume(structured)
    next.projects.items.splice(index, 1)
    applyStructured(next)
  }

  function removeEducation(index: number) {
    if (!structured) return
    pushUndoSnapshot()
    const next = cloneStructuredResume(structured)
    next.education.items.splice(index, 1)
    applyStructured(next)
  }

  function removeSkillCategory(index: number) {
    if (!structured) return
    pushUndoSnapshot()
    const next = cloneStructuredResume(structured)
    next.skills.categories.splice(index, 1)
    applyStructured(next)
  }

  function moveExperience(from: number, to: number) {
    if (!structured) return
    pushUndoSnapshot()
    const next = cloneStructuredResume(structured)
    next.experience.items = moveItem(next.experience.items, from, to)
    applyStructured(next)
  }

  function moveProject(from: number, to: number) {
    if (!structured) return
    pushUndoSnapshot()
    const next = cloneStructuredResume(structured)
    next.projects.items = moveItem(next.projects.items, from, to)
    applyStructured(next)
  }

  function moveEducation(from: number, to: number) {
    if (!structured) return
    pushUndoSnapshot()
    const next = cloneStructuredResume(structured)
    next.education.items = moveItem(next.education.items, from, to)
    applyStructured(next)
  }

  async function handleCreateVersionFrom(version: StudioVersion) {
    if (!token || !projectDetail) return
    setCreatingVersion(true)
    try {
      const created = await createStudioVersion(token, projectDetail.project.id, {
        source_version_id: version.id,
        kind: "base",
      })
      setProjectDetail((previous) => {
        if (!previous) return previous
        return {
          ...previous,
          project: {
            ...previous.project,
            updated_at: new Date().toISOString(),
            versions_count: previous.project.versions_count + 1,
          },
          versions: [created, ...previous.versions],
        }
      })
      setSelectedVersionId(created.id)
      toast({ title: "Version duplicated", description: "Created a new editable base version." })
    } catch (error) {
      toast({
        title: "Unable to duplicate version",
        description: (error as Error).message,
        variant: "destructive",
      })
    } finally {
      setCreatingVersion(false)
    }
  }

  async function handleDeleteVersion(version: StudioVersion) {
    if (!token || !projectDetail) return
    const confirmed = window.confirm(
      `Delete version #${version.id}? This cannot be undone.`
    )
    if (!confirmed) return
    setDeletingVersionId(version.id)
    try {
      await deleteStudioVersion(token, version.id)
      setProjectDetail((previous) => {
        if (!previous) return previous
        const remaining = previous.versions.filter((entry) => entry.id !== version.id)
        return {
          ...previous,
          project: {
            ...previous.project,
            updated_at: new Date().toISOString(),
            versions_count: Math.max(remaining.length, 0),
          },
          versions: remaining,
        }
      })
      setSelectedVersionId((current) => {
        if (current !== version.id) return current
        const fallback = projectDetail.versions.find((entry) => entry.id !== version.id)
        return fallback?.id ?? null
      })
      toast({ title: "Version deleted" })
    } catch (error) {
      toast({
        title: "Unable to delete version",
        description: (error as Error).message,
        variant: "destructive",
      })
    } finally {
      setDeletingVersionId(null)
    }
  }

  async function handleRenameVersion(version: StudioVersion) {
    if (!token || !renameVersionLabelDraft.trim()) return
    const nextLabel = renameVersionLabelDraft.trim()
    try {
      const updated = await updateStudioVersion(token, version.id, {
        resume_structured_json: version.resume_structured_json,
        template_name: (version.template_name as TemplateName) ?? "ats_classic",
        template_settings: {
          ...(version.template_settings_json ?? {}),
          version_label: nextLabel,
        },
      })
      setProjectDetail((previous) => {
        if (!previous) return previous
        return {
          ...previous,
          versions: previous.versions.map((entry) =>
            entry.id === updated.id ? updated : entry
          ),
        }
      })
      setRenamingVersionId(null)
      setRenameVersionLabelDraft("")
      toast({ title: "Version label updated" })
    } catch (error) {
      toast({
        title: "Unable to rename version",
        description: (error as Error).message,
        variant: "destructive",
      })
    }
  }

  async function parseJdPreview() {
    if (!token || jdText.trim().length < 50) return
    setParsingJd(true)
    try {
      const preview = await parseJobProfilePreview(token, {
        title: jdRoleTitle.trim() || projectTitleDraft || "Target role",
        raw_description: jdText.trim(),
      })
      setJdPreview(preview)
      toast({ title: "Job description parsed", description: "Preview is ready." })
    } catch (error) {
      toast({
        title: "Unable to parse JD",
        description: (error as Error).message,
        variant: "destructive",
      })
    } finally {
      setParsingJd(false)
    }
  }

  async function tailorCurrentVersion() {
    if (!token || !selectedVersion || jdText.trim().length < 50) return
    setTailoring(true)
    try {
      const tailored = await tailorStudioVersion(token, selectedVersion.id, {
        jd_text: jdText.trim(),
        strict_mode: strictMode,
        template_name: templateName,
        template_settings: templateSettings,
      })
      setProjectDetail((previous) => {
        if (!previous) return previous
        return {
          ...previous,
          project: {
            ...previous.project,
            updated_at: new Date().toISOString(),
            versions_count: previous.project.versions_count + 1,
          },
          versions: [tailored, ...previous.versions],
        }
      })
      setSelectedVersionId(tailored.id)
      setWorkspaceTab("preview")
      toast({
        title: "Tailored version created",
        description: strictMode
          ? "Strict Truth Mode enforced grounded suggestions."
          : "Draft suggestions created. Validate before publishing.",
      })
    } catch (error) {
      toast({
        title: "Tailoring failed",
        description: (error as Error).message,
        variant: "destructive",
      })
    } finally {
      setTailoring(false)
    }
  }

  function applySuggestion(suggestion: StudioSuggestion, proofText?: string) {
    if (!structured) return
    pushUndoSnapshot()
    const next = applySuggestionToResume(structured, suggestion, proofText)
    setStructured(next)
    toast({
      title: "Suggestion applied",
      description:
        suggestion.label === "conditional"
          ? "Conditional suggestion added with proof context."
          : "Grounded rewrite applied to experience bullets.",
    })
  }

  async function queueExport(format: "pdf" | "docx") {
    if (!token || !selectedVersion) return
    try {
      const queued = await requestStudioExport(token, selectedVersion.id, format)
      setVersionExports((previous) => [queued, ...previous])
      setActiveExportId(queued.id)
      setActiveExportProgress(10)
      let attempts = 0
      let current = queued
      while (
        current.status !== "completed" &&
        current.status !== "failed" &&
        attempts < 45
      ) {
        await new Promise((resolve) => setTimeout(resolve, 1200))
        current = await getStudioExport(token, current.id)
        setActiveExportProgress(Math.min(95, 10 + attempts * 2))
        attempts += 1
      }

      await listStudioVersionExports(token, selectedVersion.id).then(setVersionExports)
      setActiveExportId(null)
      setActiveExportProgress(0)

      if (current.status === "completed") {
        toast({ title: `${format.toUpperCase()} export ready` })
      } else if (current.status === "failed") {
        throw new Error(current.error_message || "Export failed")
      } else {
        toast({
          title: "Export still processing",
          description: "Refresh exports shortly to see final status.",
        })
      }
    } catch (error) {
      setActiveExportId(null)
      setActiveExportProgress(0)
      toast({
        title: "Export failed",
        description: (error as Error).message,
        variant: "destructive",
      })
    }
  }

  async function openExport(versionExport: StudioExport, mode: "download" | "preview_pdf") {
    if (!token) return
    try {
      const blob = await downloadStudioExportBlob(token, versionExport.id)
      const objectUrl = URL.createObjectURL(blob)
      if (mode === "download") {
        const anchor = document.createElement("a")
        anchor.href = objectUrl
        anchor.download = `resume_export_${versionExport.id}.${versionExport.format}`
        document.body.appendChild(anchor)
        anchor.click()
        anchor.remove()
        setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000)
      } else {
        if (previewPdfUrl) URL.revokeObjectURL(previewPdfUrl)
        setPreviewPdfUrl(objectUrl)
        setPreviewModalMode("pdf")
      }
    } catch (error) {
      toast({
        title: "Unable to open export",
        description: (error as Error).message,
        variant: "destructive",
      })
    }
  }

  if (isLoading || !isAuthenticated || loadingProject) return <StudioEditorSkeleton />

  if (!projectDetail || !selectedVersion || !structured) {
    return (
      <DashboardLayout title="Resume Studio" description="Project unavailable">
        <div className="mx-auto w-full max-w-4xl">
          <EmptyState
            icon={<FileJson2 className="h-5 w-5" />}
            title="Studio project not found"
            description="Return to Studio and select an existing project."
            action={
              <Button asChild>
                <Link href="/dashboard/studio">Back to Studio</Link>
              </Button>
            }
          />
        </div>
      </DashboardLayout>
    )
  }

  return (
    <DashboardLayout
      title="Resume Studio"
      description="Structured editing, JD tailoring, safe suggestions, and export operations."
      actions={
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" asChild>
            <Link href="/dashboard/studio">Back to Studio</Link>
          </Button>
          <Button variant="outline" size="sm" onClick={handleUndo} disabled={undoStack.length === 0}>
            <Undo2 className="h-4 w-4" />
            Undo
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => handleCreateVersionFrom(selectedVersion)}
            disabled={creatingVersion}
          >
            {creatingVersion ? <Loader2 className="h-4 w-4 animate-spin" /> : <CopyPlus className="h-4 w-4" />}
            Duplicate version
          </Button>
        </div>
      }
    >
      <PageTransition className="mx-auto w-full max-w-7xl space-y-5">
        <section className="surface-card space-y-4 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-[220px] flex-1">
              <p className="mb-1 text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                Project
              </p>
              {editingProjectTitle ? (
                <div className="flex items-center gap-2">
                  <Input
                    value={projectTitleDraft}
                    onChange={(event) => setProjectTitleDraft(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        event.preventDefault()
                        commitProjectTitle()
                      }
                    }}
                  />
                  <Button size="sm" onClick={commitProjectTitle}>
                    <Save className="h-4 w-4" />
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setProjectTitleDraft(projectDetail.project.title)
                      setEditingProjectTitle(false)
                    }}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => setEditingProjectTitle(true)}
                  className="inline-flex items-center gap-2 text-left text-xl font-semibold tracking-tight text-foreground hover:text-primary"
                >
                  {projectDetail.project.title}
                  <Pencil className="h-4 w-4" />
                </button>
              )}
            </div>
            <div className="min-w-[230px] rounded-xl border border-border/80 bg-muted/30 px-3 py-2">
              <p className="text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                Autosave
              </p>
              <p className="mt-1 inline-flex items-center gap-2 text-sm text-foreground">
                {saveState === "saving" ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin text-primary" />
                    Saving…
                  </>
                ) : saveState === "error" ? (
                  <>
                    <AlertCircle className="h-4 w-4 text-destructive" />
                    Save failed
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                    Saved {formatDateTime(lastSavedAt)}
                  </>
                )}
              </p>
            </div>
          </div>

          <div className="grid gap-3 lg:grid-cols-[1fr_auto_auto_auto]">
            <div className="flex items-center gap-2 rounded-xl border border-border bg-background px-3 py-2">
              <span className="text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                Version
              </span>
              <select
                value={selectedVersionId ?? undefined}
                onChange={(event) => setSelectedVersionId(Number(event.target.value))}
                className="min-w-[240px] bg-transparent text-sm text-foreground outline-none"
              >
                {projectDetail.versions.map((version) => (
                  <option key={version.id} value={version.id}>
                    #{version.id} · {version.version_label ?? version.kind} · {formatDateTime(version.created_at)}
                  </option>
                ))}
              </select>
            </div>
            <select
              value={templateName}
              onChange={(event) => setTemplateName(event.target.value as TemplateName)}
              className="rounded-xl border border-border bg-background px-3 py-2 text-sm"
            >
              {TEMPLATE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCompareMode((previous) => !previous)}
              disabled={!baseVersion || selectedVersion.kind !== "tailored"}
            >
              {compareMode ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              {compareMode ? "Hide Diff" : "Base vs Current"}
            </Button>
            <Button variant="outline" size="sm" onClick={() => setPreviewModalMode("html")}>
              <ClipboardList className="h-4 w-4" />
              Print Preview
            </Button>
          </div>

          <div className="grid gap-2 md:grid-cols-4">
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Font scale</label>
              <select
                value={templateSettings.font_scale}
                onChange={(event) =>
                  setTemplateSettings((previous) => ({
                    ...previous,
                    font_scale: event.target.value as StudioTemplateSettings["font_scale"],
                  }))
                }
                className="w-full rounded-lg border border-border bg-background px-2 py-1.5 text-sm"
              >
                <option value="small">Small</option>
                <option value="normal">Normal</option>
                <option value="large">Large</option>
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Spacing density</label>
              <select
                value={templateSettings.density}
                onChange={(event) =>
                  setTemplateSettings((previous) => ({
                    ...previous,
                    density: event.target.value as StudioTemplateSettings["density"],
                  }))
                }
                className="w-full rounded-lg border border-border bg-background px-2 py-1.5 text-sm"
              >
                <option value="compact">Compact</option>
                <option value="normal">Normal</option>
                <option value="airy">Airy</option>
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Accent</label>
              <select
                value={templateSettings.accent}
                onChange={(event) =>
                  setTemplateSettings((previous) => ({
                    ...previous,
                    accent: event.target.value as StudioTemplateSettings["accent"],
                  }))
                }
                className="w-full rounded-lg border border-border bg-background px-2 py-1.5 text-sm"
              >
                <option value="slate">Slate</option>
                <option value="indigo">Indigo</option>
                <option value="emerald">Emerald</option>
              </select>
            </div>
            <label className="inline-flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-sm text-muted-foreground">
              <input
                type="checkbox"
                checked={templateSettings.show_icons}
                onChange={(event) =>
                  setTemplateSettings((previous) => ({
                    ...previous,
                    show_icons: event.target.checked,
                  }))
                }
              />
              Show section icons
            </label>
          </div>
        </section>

        <div className="md:hidden">
          <SegmentedControl
            options={[
              { label: "Edit", value: "edit" },
              { label: "Preview", value: "preview" },
              { label: "Tailor", value: "tailor" },
              { label: "Versions", value: "versions" },
            ]}
            value={workspaceTab}
            onChange={setWorkspaceTab}
          />
        </div>

        <div className="grid gap-5 xl:grid-cols-[1.15fr_0.85fr]">
          <section className={cn("space-y-4", workspaceTab !== "edit" && "md:space-y-4")}>
            <div className={cn(workspaceTab === "edit" ? "block" : "hidden md:block")}>
              <SectionCard
                title="Structured Editor"
                description="Edit sections with recruiter-grade clarity and ATS-safe formatting."
                action={
                  <SegmentedControl
                    options={EDIT_SECTIONS}
                    value={activeSection}
                    onChange={setActiveSection}
                  />
                }
              >
                {activeSection === "profile" && (
                  <div className="space-y-4">
                    <div className="grid gap-2 md:grid-cols-2">
                      <Input
                        value={structured.header.name}
                        onChange={(event) =>
                          setStructured((previous) => {
                            if (!previous) return previous
                            const next = cloneStructuredResume(previous)
                            next.header.name = event.target.value
                            return next
                          })
                        }
                        placeholder="Full name"
                      />
                      <Input
                        value={structured.header.title}
                        onChange={(event) =>
                          setStructured((previous) => {
                            if (!previous) return previous
                            const next = cloneStructuredResume(previous)
                            next.header.title = event.target.value
                            return next
                          })
                        }
                        placeholder="Headline"
                      />
                      <Input
                        value={structured.header.email}
                        onChange={(event) =>
                          setStructured((previous) => {
                            if (!previous) return previous
                            const next = cloneStructuredResume(previous)
                            next.header.email = event.target.value
                            return next
                          })
                        }
                        placeholder="Email"
                      />
                      <Input
                        value={structured.header.phone}
                        onChange={(event) =>
                          setStructured((previous) => {
                            if (!previous) return previous
                            const next = cloneStructuredResume(previous)
                            next.header.phone = event.target.value
                            return next
                          })
                        }
                        placeholder="Phone"
                      />
                      <Input
                        value={structured.header.location}
                        onChange={(event) =>
                          setStructured((previous) => {
                            if (!previous) return previous
                            const next = cloneStructuredResume(previous)
                            next.header.location = event.target.value
                            return next
                          })
                        }
                        placeholder="Location"
                      />
                    </div>
                    <div className="space-y-2">
                      <p className="text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                        Links
                      </p>
                      {structured.header.links.map((link, index) => (
                        <div key={`${link.url}-${index}`} className="grid gap-2 md:grid-cols-[0.35fr_0.55fr_auto]">
                          <Input
                            value={link.label}
                            onChange={(event) =>
                              setStructured((previous) => {
                                if (!previous) return previous
                                const next = cloneStructuredResume(previous)
                                next.header.links[index].label = event.target.value
                                return next
                              })
                            }
                            placeholder="Label"
                          />
                          <Input
                            value={link.url}
                            onChange={(event) =>
                              setStructured((previous) => {
                                if (!previous) return previous
                                const next = cloneStructuredResume(previous)
                                next.header.links[index].url = event.target.value
                                return next
                              })
                            }
                            placeholder="https://..."
                          />
                          <Button
                            variant="outline"
                            onClick={() =>
                              setStructured((previous) => {
                                if (!previous) return previous
                                const next = cloneStructuredResume(previous)
                                next.header.links.splice(index, 1)
                                return next
                              })
                            }
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      ))}
                      <Button
                        variant="outline"
                        onClick={() =>
                          setStructured((previous) => {
                            if (!previous) return previous
                            const next = cloneStructuredResume(previous)
                            next.header.links.push({ label: "Link", url: "" })
                            return next
                          })
                        }
                      >
                        <Plus className="h-4 w-4" />
                        Add link
                      </Button>
                    </div>
                  </div>
                )}

                {activeSection === "summary" && (
                  <textarea
                    value={structured.summary}
                    onChange={(event) =>
                      setStructured((previous) => {
                        if (!previous) return previous
                        const next = cloneStructuredResume(previous)
                        next.summary = event.target.value
                        return next
                      })
                    }
                    className="min-h-[180px] w-full rounded-xl border border-border bg-background px-3 py-2 text-sm outline-none ring-primary transition focus:ring-2"
                    placeholder="Write a concise recruiter-style summary..."
                  />
                )}

                {activeSection === "skills" && (
                  <div className="space-y-3">
                    {structured.skills.categories.map((category, index) => (
                      <div key={`${category.name}-${index}`} className="rounded-xl border border-border/80 p-3">
                        <div className="mb-2 grid gap-2 md:grid-cols-[1fr_auto_auto_auto]">
                          <Input
                            value={category.name}
                            onChange={(event) =>
                              setStructured((previous) => {
                                if (!previous) return previous
                                const next = cloneStructuredResume(previous)
                                next.skills.categories[index].name = event.target.value
                                return next
                              })
                            }
                            placeholder="Category"
                          />
                          <Button
                            variant="outline"
                            onClick={() =>
                              setStructured((previous) => {
                                if (!previous) return previous
                                const next = cloneStructuredResume(previous)
                                next.skills.categories = moveItem(next.skills.categories, index, index - 1)
                                return next
                              })
                            }
                          >
                            <ArrowUp className="h-4 w-4" />
                          </Button>
                          <Button variant="outline" onClick={() => setStructured((previous) => {
                              if (!previous) return previous
                              const next = cloneStructuredResume(previous)
                              next.skills.categories = moveItem(next.skills.categories, index, index + 1)
                              return next
                            })}>
                            <ArrowDown className="h-4 w-4" />
                          </Button>
                          <Button variant="outline" onClick={() => removeSkillCategory(index)}>
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                        <textarea
                          value={category.items.join(", ")}
                          onChange={(event) =>
                            setStructured((previous) => {
                              if (!previous) return previous
                              const next = cloneStructuredResume(previous)
                              next.skills.categories[index].items = event.target.value
                                .split(",")
                                .map((item) => item.trim())
                                .filter(Boolean)
                              return next
                            })
                          }
                          className="min-h-[90px] w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none ring-primary transition focus:ring-2"
                          placeholder="Comma separated skills"
                        />
                      </div>
                    ))}
                    <Button
                      variant="outline"
                      onClick={() =>
                        setStructured((previous) => {
                          if (!previous) return previous
                          const next = cloneStructuredResume(previous)
                          next.skills.categories.push({ name: "Category", items: [] })
                          return next
                        })
                      }
                    >
                      <Plus className="h-4 w-4" />
                      Add skill category
                    </Button>
                  </div>
                )}

                {activeSection === "experience" && (
                  <div className="space-y-3">
                    {structured.experience.items.map((item, index) => (
                      <div key={`${item.role}-${item.company}-${index}`} className="rounded-xl border border-border/80 p-3">
                        <div className="mb-2 grid gap-2 md:grid-cols-2">
                          <Input
                            value={item.role}
                            onChange={(event) =>
                              setStructured((previous) => {
                                if (!previous) return previous
                                const next = cloneStructuredResume(previous)
                                next.experience.items[index].role = event.target.value
                                return next
                              })
                            }
                            placeholder="Role"
                          />
                          <Input
                            value={item.company}
                            onChange={(event) =>
                              setStructured((previous) => {
                                if (!previous) return previous
                                const next = cloneStructuredResume(previous)
                                next.experience.items[index].company = event.target.value
                                return next
                              })
                            }
                            placeholder="Company"
                          />
                          <Input
                            value={item.start}
                            onChange={(event) =>
                              setStructured((previous) => {
                                if (!previous) return previous
                                const next = cloneStructuredResume(previous)
                                next.experience.items[index].start = event.target.value
                                return next
                              })
                            }
                            placeholder="Start"
                          />
                          <Input
                            value={item.end}
                            onChange={(event) =>
                              setStructured((previous) => {
                                if (!previous) return previous
                                const next = cloneStructuredResume(previous)
                                next.experience.items[index].end = event.target.value
                                return next
                              })
                            }
                            placeholder="End"
                          />
                        </div>
                        <div className="mb-2 flex items-center gap-2">
                          <Button variant="outline" onClick={() => moveExperience(index, index - 1)}>
                            <ArrowUp className="h-4 w-4" />
                          </Button>
                          <Button variant="outline" onClick={() => moveExperience(index, index + 1)}>
                            <ArrowDown className="h-4 w-4" />
                          </Button>
                          <Button variant="outline" onClick={() => removeExperience(index)}>
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                        <textarea
                          value={item.bullets.join("\n")}
                          onChange={(event) =>
                            setStructured((previous) => {
                              if (!previous) return previous
                              const next = cloneStructuredResume(previous)
                              next.experience.items[index].bullets = event.target.value
                                .split("\n")
                                .map((line) => line.trim())
                                .filter(Boolean)
                              return next
                            })
                          }
                          className="min-h-[130px] w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none ring-primary transition focus:ring-2"
                          placeholder="One bullet per line"
                        />
                        <div className="mt-2 space-y-1">
                          {item.bullets.map((bullet, bulletIndex) => {
                            const level = bulletImpactLevel(bullet)
                            const tone =
                              level === "high"
                                ? "text-emerald-700 bg-emerald-50"
                                : level === "medium"
                                  ? "text-amber-700 bg-amber-50"
                                  : "text-slate-600 bg-slate-100"
                            return (
                              <p
                                key={`${bulletIndex}-${bullet.slice(0, 10)}`}
                                className={`inline-flex items-center gap-2 rounded-full px-2 py-0.5 text-[11px] ${tone}`}
                              >
                                Impact {bulletIndex + 1}: {level}
                              </p>
                            )
                          })}
                        </div>
                      </div>
                    ))}
                    <Button
                      variant="outline"
                      onClick={() =>
                        setStructured((previous) => {
                          if (!previous) return previous
                          const next = cloneStructuredResume(previous)
                          next.experience.items.push({
                            company: "",
                            role: "",
                            location: "",
                            start: "",
                            end: "",
                            bullets: [],
                            tech: [],
                          })
                          return next
                        })
                      }
                    >
                      <Plus className="h-4 w-4" />
                      Add experience item
                    </Button>
                  </div>
                )}

                {activeSection === "projects" && (
                  <div className="space-y-3">
                    {structured.projects.items.map((item, index) => (
                      <div key={`${item.name}-${index}`} className="rounded-xl border border-border/80 p-3">
                        <div className="mb-2 grid gap-2 md:grid-cols-2">
                          <Input
                            value={item.name}
                            onChange={(event) =>
                              setStructured((previous) => {
                                if (!previous) return previous
                                const next = cloneStructuredResume(previous)
                                next.projects.items[index].name = event.target.value
                                return next
                              })
                            }
                            placeholder="Project"
                          />
                          <Input
                            value={item.link}
                            onChange={(event) =>
                              setStructured((previous) => {
                                if (!previous) return previous
                                const next = cloneStructuredResume(previous)
                                next.projects.items[index].link = event.target.value
                                return next
                              })
                            }
                            placeholder="Link"
                          />
                        </div>
                        <div className="mb-2 flex items-center gap-2">
                          <Button variant="outline" onClick={() => moveProject(index, index - 1)}>
                            <ArrowUp className="h-4 w-4" />
                          </Button>
                          <Button variant="outline" onClick={() => moveProject(index, index + 1)}>
                            <ArrowDown className="h-4 w-4" />
                          </Button>
                          <Button variant="outline" onClick={() => removeProject(index)}>
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                        <textarea
                          value={item.bullets.join("\n")}
                          onChange={(event) =>
                            setStructured((previous) => {
                              if (!previous) return previous
                              const next = cloneStructuredResume(previous)
                              next.projects.items[index].bullets = event.target.value
                                .split("\n")
                                .map((line) => line.trim())
                                .filter(Boolean)
                              return next
                            })
                          }
                          className="min-h-[110px] w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none ring-primary transition focus:ring-2"
                          placeholder="One bullet per line"
                        />
                      </div>
                    ))}
                    <Button
                      variant="outline"
                      onClick={() =>
                        setStructured((previous) => {
                          if (!previous) return previous
                          const next = cloneStructuredResume(previous)
                          next.projects.items.push({ name: "", link: "", bullets: [], tech: [] })
                          return next
                        })
                      }
                    >
                      <Plus className="h-4 w-4" />
                      Add project
                    </Button>
                  </div>
                )}

                {activeSection === "education" && (
                  <div className="space-y-3">
                    {structured.education.items.map((item, index) => (
                      <div key={`${item.school}-${index}`} className="rounded-xl border border-border/80 p-3">
                        <div className="mb-2 grid gap-2 md:grid-cols-2">
                          <Input
                            value={item.school}
                            onChange={(event) =>
                              setStructured((previous) => {
                                if (!previous) return previous
                                const next = cloneStructuredResume(previous)
                                next.education.items[index].school = event.target.value
                                return next
                              })
                            }
                            placeholder="School"
                          />
                          <Input
                            value={item.degree}
                            onChange={(event) =>
                              setStructured((previous) => {
                                if (!previous) return previous
                                const next = cloneStructuredResume(previous)
                                next.education.items[index].degree = event.target.value
                                return next
                              })
                            }
                            placeholder="Degree"
                          />
                          <Input
                            value={item.start}
                            onChange={(event) =>
                              setStructured((previous) => {
                                if (!previous) return previous
                                const next = cloneStructuredResume(previous)
                                next.education.items[index].start = event.target.value
                                return next
                              })
                            }
                            placeholder="Start"
                          />
                          <Input
                            value={item.end}
                            onChange={(event) =>
                              setStructured((previous) => {
                                if (!previous) return previous
                                const next = cloneStructuredResume(previous)
                                next.education.items[index].end = event.target.value
                                return next
                              })
                            }
                            placeholder="End"
                          />
                        </div>
                        <div className="flex items-center gap-2">
                          <Button variant="outline" onClick={() => moveEducation(index, index - 1)}>
                            <ArrowUp className="h-4 w-4" />
                          </Button>
                          <Button variant="outline" onClick={() => moveEducation(index, index + 1)}>
                            <ArrowDown className="h-4 w-4" />
                          </Button>
                          <Button variant="outline" onClick={() => removeEducation(index)}>
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    ))}
                    <Button
                      variant="outline"
                      onClick={() =>
                        setStructured((previous) => {
                          if (!previous) return previous
                          const next = cloneStructuredResume(previous)
                          next.education.items.push({
                            school: "",
                            degree: "",
                            start: "",
                            end: "",
                            notes: [],
                          })
                          return next
                        })
                      }
                    >
                      <Plus className="h-4 w-4" />
                      Add education item
                    </Button>
                  </div>
                )}

                {activeSection === "certifications" && (
                  <div className="grid gap-3 md:grid-cols-2">
                    <div className="space-y-2">
                      <p className="text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                        Certifications
                      </p>
                      <textarea
                        value={structured.certifications.join("\n")}
                        onChange={(event) =>
                          setStructured((previous) => {
                            if (!previous) return previous
                            const next = cloneStructuredResume(previous)
                            next.certifications = event.target.value
                              .split("\n")
                              .map((line) => line.trim())
                              .filter(Boolean)
                            return next
                          })
                        }
                        className="min-h-[120px] w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none ring-primary transition focus:ring-2"
                        placeholder="One certification per line"
                      />
                    </div>
                    <div className="space-y-2">
                      <p className="text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                        Awards
                      </p>
                      <textarea
                        value={structured.awards.join("\n")}
                        onChange={(event) =>
                          setStructured((previous) => {
                            if (!previous) return previous
                            const next = cloneStructuredResume(previous)
                            next.awards = event.target.value
                              .split("\n")
                              .map((line) => line.trim())
                              .filter(Boolean)
                            return next
                          })
                        }
                        className="min-h-[120px] w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none ring-primary transition focus:ring-2"
                        placeholder="One award per line"
                      />
                    </div>
                  </div>
                )}
              </SectionCard>

              {diagnostics && (
                <SectionCard title="ATS Hygiene" description="Live formatting and quality checks.">
                  <div className="grid gap-3 md:grid-cols-3">
                    <div className="rounded-xl border border-border/80 bg-muted/30 px-3 py-2">
                      <p className="text-xs uppercase tracking-[0.08em] text-muted-foreground">Word count</p>
                      <p className="text-xl font-semibold text-foreground">{diagnostics.wordCount}</p>
                    </div>
                    <div className="rounded-xl border border-border/80 bg-muted/30 px-3 py-2">
                      <p className="text-xs uppercase tracking-[0.08em] text-muted-foreground">Skills</p>
                      <p className="text-xl font-semibold text-foreground">{diagnostics.skillsCount}</p>
                    </div>
                    <div className="rounded-xl border border-border/80 bg-muted/30 px-3 py-2">
                      <p className="text-xs uppercase tracking-[0.08em] text-muted-foreground">Sections</p>
                      <p className="text-xl font-semibold text-foreground">{diagnostics.sectionCount}</p>
                    </div>
                  </div>
                  {diagnostics.warnings.length > 0 ? (
                    <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-amber-700">
                      {diagnostics.warnings.map((warning) => (
                        <li key={warning}>{warning}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-3 inline-flex items-center gap-2 text-sm text-emerald-700">
                      <ShieldCheck className="h-4 w-4" />
                      Looks clean for ATS parsing.
                    </p>
                  )}
                </SectionCard>
              )}
            </div>

            <div className={cn(workspaceTab === "tailor" ? "block" : "hidden md:block")}>
              <SectionCard
                title="Tailor to Job Description"
                description="Parse JD context and generate a new tailored version safely."
              >
                <div className="space-y-3">
                  <Input
                    value={jdRoleTitle}
                    onChange={(event) => setJdRoleTitle(event.target.value)}
                    placeholder="Role title (optional)"
                  />
                  <textarea
                    value={jdText}
                    onChange={(event) => setJdText(event.target.value)}
                    className="min-h-[180px] w-full rounded-xl border border-border bg-background px-3 py-2 text-sm outline-none ring-primary transition focus:ring-2"
                    placeholder="Paste full job description..."
                  />
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>{jdText.length} characters</span>
                    <label className="inline-flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={strictMode}
                        onChange={(event) => setStrictMode(event.target.checked)}
                      />
                      Strict Truth Mode
                    </label>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <Button variant="outline" onClick={parseJdPreview} disabled={parsingJd || jdText.trim().length < 50}>
                      {parsingJd ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                      Parse JD
                    </Button>
                    <Button onClick={tailorCurrentVersion} disabled={tailoring || jdText.trim().length < 50}>
                      {tailoring ? <Loader2 className="h-4 w-4 animate-spin" /> : <WandSparkles className="h-4 w-4" />}
                      Tailor resume
                    </Button>
                  </div>
                  {jdPreview && (
                    <div className="rounded-xl border border-border/80 bg-muted/25 p-3">
                      <p className="text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                        JD Extraction Preview
                      </p>
                      <p className="mt-1 text-sm font-medium text-foreground">{jdPreview.role_title}</p>
                      <p className="text-xs text-muted-foreground">
                        {jdPreview.seniority_level} · {jdPreview.role_archetype}
                      </p>
                      <div className="mt-2 grid gap-2 md:grid-cols-3">
                        <div>
                          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                            Hard reqs
                          </p>
                          <ul className="mt-1 list-disc space-y-1 pl-4 text-xs text-foreground">
                            {jdPreview.requirements_hard.slice(0, 4).map((item) => (
                              <li key={item}>{item}</li>
                            ))}
                          </ul>
                        </div>
                        <div>
                          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                            Soft reqs
                          </p>
                          <ul className="mt-1 list-disc space-y-1 pl-4 text-xs text-foreground">
                            {jdPreview.requirements_soft.slice(0, 4).map((item) => (
                              <li key={item}>{item}</li>
                            ))}
                          </ul>
                        </div>
                        <div>
                          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                            Responsibilities
                          </p>
                          <ul className="mt-1 list-disc space-y-1 pl-4 text-xs text-foreground">
                            {jdPreview.responsibilities.slice(0, 4).map((item) => (
                              <li key={item}>{item}</li>
                            ))}
                          </ul>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </SectionCard>

              <SectionCard title="Suggestions" description="Apply grounded rewrites safely.">
                <div className="space-y-3">
                  <SuggestionGroup
                    title="Highest impact fixes"
                    items={suggestionGroups.highImpact}
                  />
                  <SuggestionGroup
                    title="Missing keywords & tools"
                    items={suggestionGroups.missingKeywords}
                  />
                  <SuggestionCardList
                    title="Bullet rewrites (grounded)"
                    suggestions={suggestionGroups.groundedRewrites}
                    actionLabel="Apply"
                    onAction={(suggestion) => applySuggestion(suggestion)}
                  />
                  <SuggestionCardList
                    title="Missing evidence (add only if true)"
                    suggestions={suggestionGroups.conditionalRewrites}
                    actionLabel="Apply with proof"
                    onAction={(suggestion) => {
                      setConditionalSuggestion(suggestion)
                      setConditionalProof("")
                    }}
                    conditional
                  />
                  <SuggestionGroup
                    title="Missing evidence"
                    items={suggestionGroups.missingEvidence}
                  />
                  {suggestionGroups.atsMap.length > 0 && (
                    <div className="rounded-xl border border-border/80 bg-muted/20 p-3">
                      <p className="text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                        ATS alignment map
                      </p>
                      <div className="mt-2 space-y-2">
                        {suggestionGroups.atsMap.slice(0, 6).map((entry) => (
                          <div key={entry.keyword} className="flex items-center justify-between gap-2 text-xs">
                            <span className="text-foreground">{entry.keyword}</span>
                            <span
                              className={cn(
                                "rounded-full px-2 py-0.5 font-medium capitalize",
                                entry.status === "matched"
                                  ? "bg-emerald-50 text-emerald-700"
                                  : "bg-amber-50 text-amber-700"
                              )}
                            >
                              {entry.status}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </SectionCard>
            </div>
          </section>

          <aside className="space-y-4">
            <div className={cn(workspaceTab === "preview" ? "block" : "hidden md:block")}>
              <SectionCard
                title="Live Preview"
                description="Template-rendered preview of the current version."
                action={
                  <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm" onClick={() => setPreviewModalMode("html")}>
                      Print Preview
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => setCompareMode((previous) => !previous)}>
                      {compareMode ? "Hide Diff" : "Compare"}
                    </Button>
                  </div>
                }
              >
                {!compareMode ? (
                  <iframe
                    title="Resume preview"
                    srcDoc={previewHtml}
                    className="h-[620px] w-full rounded-xl border border-border bg-white"
                  />
                ) : (
                  <div className="space-y-3">
                    <div className="grid gap-3 md:grid-cols-2">
                      <div>
                        <p className="mb-2 text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                          Base
                        </p>
                        <iframe
                          title="Base version preview"
                          srcDoc={basePreviewHtml}
                          className="h-[400px] w-full rounded-xl border border-border bg-white"
                        />
                      </div>
                      <div>
                        <p className="mb-2 text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                          Current
                        </p>
                        <iframe
                          title="Current version preview"
                          srcDoc={previewHtml}
                          className="h-[400px] w-full rounded-xl border border-border bg-white"
                        />
                      </div>
                    </div>
                    {diffSummary && (
                      <div className="rounded-xl border border-border/80 bg-muted/20 p-3">
                        <p className="text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                          Changes summary
                        </p>
                        <div className="mt-2 grid gap-2 md:grid-cols-2 text-xs">
                          <p className="text-foreground">Keywords added: {diffSummary.keywordsAdded.length}</p>
                          <p className="text-foreground">Skills delta: +{diffSummary.skillsAdded.length} / -{diffSummary.skillsRemoved.length}</p>
                          <p className="text-foreground">Sections changed: {diffSummary.sectionsChanged.join(", ") || "None"}</p>
                          <p className="text-foreground">Bullet delta: {diffSummary.bulletDelta >= 0 ? "+" : ""}{diffSummary.bulletDelta}</p>
                        </div>
                        <div className="mt-3 grid gap-2 md:grid-cols-3">
                          <DiffList title="Added" tone="emerald" items={diffSummary.addedBullets} />
                          <DiffList title="Removed" tone="rose" items={diffSummary.removedBullets} />
                          <DiffList
                            title="Modified"
                            tone="slate"
                            items={diffSummary.modifiedBullets.map((entry) => `${entry.from} → ${entry.to}`)}
                          />
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </SectionCard>
            </div>

            <div className={cn(workspaceTab === "versions" ? "block" : "hidden md:block")}>
              <SectionCard title="Version History" description="Track drafts, tailored runs, and export status.">
                <div className="space-y-3">
                  {projectDetail.versions.map((version) => {
                    const active = version.id === selectedVersion.id
                    const maybeScore = version.score_snapshot_json
                      ? (version.score_snapshot_json["overall_match_score"] as number | string | undefined)
                      : undefined
                    const autoLabel =
                      version.version_label ??
                      (version.kind === "tailored"
                        ? `${(version.jd_structured_json?.role_title as string | undefined) || "Tailored"} — ${formatDateTime(version.created_at)}`
                        : `Base — ${formatDateTime(version.created_at)}`)
                    const canDelete = projectDetail.versions.length > 1
                    return (
                      <div
                        key={version.id}
                        className={cn(
                          "rounded-xl border p-3",
                          active ? "border-primary/40 bg-primary-soft/20" : "border-border/80 bg-muted/20"
                        )}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="space-y-1">
                            <p className="text-sm font-medium text-foreground">#{version.id} · {autoLabel}</p>
                            <p className="text-xs text-muted-foreground">
                              {version.kind} · {version.template_name} · {formatDateTime(version.created_at)}
                            </p>
                            {maybeScore != null && maybeScore !== "" && (
                              <p className="text-xs text-foreground">
                                Match score: {String(maybeScore)}%
                              </p>
                            )}
                            {version.latest_export && exportStatusPill(version.latest_export.status)}
                          </div>
                          <div className="flex items-center gap-1">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => setSelectedVersionId(version.id)}
                            >
                              Open
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleCreateVersionFrom(version)}
                              disabled={creatingVersion}
                            >
                              <CopyPlus className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              disabled={!canDelete || deletingVersionId === version.id}
                              onClick={() => handleDeleteVersion(version)}
                            >
                              {deletingVersionId === version.id ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                <Trash2 className="h-4 w-4" />
                              )}
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => {
                                setRenamingVersionId(version.id)
                                setRenameVersionLabelDraft(version.version_label ?? "")
                              }}
                            >
                              <Pencil className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                        {renamingVersionId === version.id && (
                          <div className="mt-2 flex items-center gap-2">
                            <Input
                              value={renameVersionLabelDraft}
                              onChange={(event) => setRenameVersionLabelDraft(event.target.value)}
                              placeholder="Version label"
                            />
                            <Button size="sm" onClick={() => handleRenameVersion(version)}>
                              Save
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                setRenamingVersionId(null)
                                setRenameVersionLabelDraft("")
                              }}
                            >
                              Cancel
                            </Button>
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </SectionCard>
            </div>

            <SectionCard title="Export Panel" description="Queue PDF/DOCX jobs and download when ready.">
              <div className="grid grid-cols-2 gap-2">
                <Button onClick={() => queueExport("pdf")} disabled={activeExportId !== null}>
                  {activeExportId ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                  Export PDF
                </Button>
                <Button variant="outline" onClick={() => queueExport("docx")} disabled={activeExportId !== null}>
                  {activeExportId ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                  Export DOCX
                </Button>
              </div>
              {activeExportId && (
                <div className="mt-3 rounded-xl border border-border/80 bg-muted/30 px-3 py-2">
                  <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
                    <span>Processing export #{activeExportId}</span>
                    <span>{activeExportProgress}%</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-primary transition-all"
                      style={{ width: `${activeExportProgress}%` }}
                    />
                  </div>
                </div>
              )}
              <div className="mt-3 space-y-2">
                {loadingExports ? (
                  <p className="text-sm text-muted-foreground">Loading exports…</p>
                ) : versionExports.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No exports yet for this version.</p>
                ) : (
                  versionExports.slice(0, 6).map((versionExport) => (
                    <div key={versionExport.id} className="rounded-xl border border-border/80 bg-muted/20 p-3">
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-sm font-medium text-foreground">
                          {versionExport.format.toUpperCase()} #{versionExport.id}
                        </p>
                        {exportStatusPill(versionExport.status)}
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">
                        Created {formatDateTime(versionExport.created_at)}
                        {versionExport.completed_at ? ` · Completed ${formatDateTime(versionExport.completed_at)}` : ""}
                      </p>
                      {versionExport.status === "failed" && (
                        <p className="mt-1 text-xs text-destructive">
                          {versionExport.error_message || "Export failed unexpectedly."}
                        </p>
                      )}
                      <div className="mt-2 flex items-center gap-2">
                        {versionExport.status === "completed" && (
                          <>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => openExport(versionExport, "download")}
                            >
                              Download
                            </Button>
                            {versionExport.format === "pdf" && (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => openExport(versionExport, "preview_pdf")}
                              >
                                Preview PDF
                              </Button>
                            )}
                          </>
                        )}
                        {versionExport.status === "failed" && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => queueExport(versionExport.format)}
                          >
                            Retry
                          </Button>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </SectionCard>
          </aside>
        </div>
      </PageTransition>

      {conditionalSuggestion && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-slate-900/35 px-4 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-[var(--radius-lg)] border border-border bg-card p-5 shadow-[var(--shadow-lg)]">
            <div className="mb-3 flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-foreground">Add only if true</p>
                <p className="text-xs text-muted-foreground">
                  Provide proof text or metric before applying this conditional suggestion.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setConditionalSuggestion(null)}
                className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <p className="rounded-lg bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
              {conditionalSuggestion.recommendation || conditionalSuggestion.example_bullet}
            </p>
            <textarea
              value={conditionalProof}
              onChange={(event) => setConditionalProof(event.target.value)}
              className="mt-3 min-h-[110px] w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none ring-primary transition focus:ring-2"
              placeholder="Add proof text (e.g., project context, metric, source bullet)..."
            />
            <div className="mt-3 flex items-center justify-end gap-2">
              <Button variant="outline" onClick={() => setConditionalSuggestion(null)}>
                Cancel
              </Button>
              <Button
                onClick={() => {
                  applySuggestion(conditionalSuggestion, conditionalProof)
                  setConditionalSuggestion(null)
                }}
                disabled={conditionalProof.trim().length < 6}
              >
                Apply safely
              </Button>
            </div>
          </div>
        </div>
      )}

      {previewModalMode && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-slate-900/35 px-4 backdrop-blur-sm">
          <div className="h-[86vh] w-full max-w-6xl rounded-[var(--radius-lg)] border border-border bg-card p-4 shadow-[var(--shadow-lg)]">
            <div className="mb-3 flex items-center justify-between">
              <p className="text-sm font-semibold text-foreground">
                {previewModalMode === "html" ? "Print Preview (HTML)" : "PDF Preview"}
              </p>
              <div className="flex items-center gap-2">
                {previewModalMode === "html" && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      const tab = window.open("", "_blank")
                      if (!tab) return
                      tab.document.write(previewHtml)
                      tab.document.close()
                    }}
                  >
                    Open in new tab
                  </Button>
                )}
                {previewModalMode === "pdf" && previewPdfUrl && (
                  <Button variant="outline" size="sm" onClick={() => window.open(previewPdfUrl, "_blank")}>
                    Open in new tab
                  </Button>
                )}
                <Button variant="outline" size="sm" onClick={() => setPreviewModalMode(null)}>
                  Close
                </Button>
              </div>
            </div>
            {previewModalMode === "html" ? (
              <iframe title="Print preview" srcDoc={previewHtml} className="h-[calc(86vh-72px)] w-full rounded-xl border border-border bg-white" />
            ) : previewPdfUrl ? (
              <iframe title="PDF preview" src={previewPdfUrl} className="h-[calc(86vh-72px)] w-full rounded-xl border border-border bg-white" />
            ) : (
              <div className="flex h-[calc(86vh-72px)] items-center justify-center rounded-xl border border-border bg-muted/30 text-sm text-muted-foreground">
                PDF preview unavailable.
              </div>
            )}
          </div>
        </div>
      )}
    </DashboardLayout>
  )
}

function SuggestionGroup({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null
  return (
    <div className="rounded-xl border border-border/80 bg-muted/20 p-3">
      <p className="text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">{title}</p>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-foreground">
        {items.slice(0, 6).map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  )
}

function SuggestionCardList({
  title,
  suggestions,
  onAction,
  actionLabel,
  conditional = false,
}: {
  title: string
  suggestions: StudioSuggestion[]
  onAction: (suggestion: StudioSuggestion) => void
  actionLabel: string
  conditional?: boolean
}) {
  if (suggestions.length === 0) return null
  return (
    <div className="rounded-xl border border-border/80 bg-muted/20 p-3">
      <p className="text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">{title}</p>
      <div className="mt-2 space-y-2">
        {suggestions.slice(0, 6).map((suggestion, index) => (
          <div key={`${suggestion.requirement}-${index}`} className="rounded-lg border border-border/70 bg-background p-2.5">
            <div className="mb-1 flex items-center justify-between gap-2">
              <p className="text-xs font-semibold text-foreground">{suggestion.requirement}</p>
              <span
                className={cn(
                  "rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.08em]",
                  conditional ? "bg-amber-50 text-amber-700" : "bg-emerald-50 text-emerald-700"
                )}
              >
                {conditional ? "Conditional" : "Grounded"}
              </span>
            </div>
            <p className="text-xs text-muted-foreground">{suggestion.recommendation || suggestion.issue}</p>
            {suggestion.example_bullet && (
              <p className="mt-1 rounded bg-muted/40 px-2 py-1 text-[11px] text-muted-foreground">
                {suggestion.example_bullet}
              </p>
            )}
            <Button size="sm" variant="outline" className="mt-2" onClick={() => onAction(suggestion)}>
              {actionLabel}
            </Button>
          </div>
        ))}
      </div>
    </div>
  )
}

function DiffList({
  title,
  tone,
  items,
}: {
  title: string
  tone: "emerald" | "rose" | "slate"
  items: string[]
}) {
  const classes =
    tone === "emerald"
      ? "border-emerald-200 bg-emerald-50 text-emerald-900"
      : tone === "rose"
        ? "border-rose-200 bg-rose-50 text-rose-900"
        : "border-slate-200 bg-slate-50 text-slate-900"
  return (
    <div className={`rounded-lg border p-2 ${classes}`}>
      <p className="text-[11px] font-semibold uppercase tracking-[0.08em]">{title}</p>
      {items.length === 0 ? (
        <p className="mt-1 text-[11px]">No changes</p>
      ) : (
        <ul className="mt-1 list-disc space-y-1 pl-4 text-[11px]">
          {items.slice(0, 4).map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

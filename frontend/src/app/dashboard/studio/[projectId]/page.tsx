"use client"

import Link from "next/link"
import { useEffect, useMemo, useRef, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import {
  CheckCircle2,
  CopyPlus,
  Download,
  FileJson2,
  Loader2,
  ShieldCheck,
  Sparkles,
  WandSparkles,
} from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import {
  ResumeStudioStructuredResume,
  StudioProjectDetail,
  StudioVersion,
  createStudioVersion,
  getStudioExport,
  getStudioProject,
  makeStudioExportDownloadUrl,
  requestStudioExport,
  tailorStudioVersion,
  updateStudioVersion,
} from "@/lib/api"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/ui/empty-state"
import { Input } from "@/components/ui/input"
import { PageTransition } from "@/components/ui/page-transition"
import { SectionCard } from "@/components/ui/section-card"
import { Skeleton } from "@/components/ui/skeleton"
import { useToast } from "@/components/ui/use-toast"

const STEPS = ["Header", "Summary", "Skills", "Experience", "Projects", "Education", "Review"]

function StudioEditorSkeleton() {
  return (
    <DashboardLayout title="Resume Studio" description="Loading workspace...">
      <div className="mx-auto w-full max-w-7xl space-y-5">
        <Skeleton className="h-10 w-72 rounded-xl" />
        <Skeleton className="h-[520px] w-full rounded-[var(--radius)]" />
      </div>
    </DashboardLayout>
  )
}

function cloneStructuredResume(resume: ResumeStudioStructuredResume): ResumeStudioStructuredResume {
  return JSON.parse(JSON.stringify(resume))
}

function formatDate(value: string) {
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

export default function StudioProjectEditorPage() {
  const params = useParams()
  const projectId = Number(params.projectId)
  const router = useRouter()
  const { token, isAuthenticated, isLoading } = useAuth()
  const { toast } = useToast()

  const [projectDetail, setProjectDetail] = useState<StudioProjectDetail | null>(null)
  const [selectedVersionId, setSelectedVersionId] = useState<number | null>(null)
  const [structured, setStructured] = useState<ResumeStudioStructuredResume | null>(null)
  const [stepIndex, setStepIndex] = useState(0)
  const [jdText, setJdText] = useState("")
  const [strictMode, setStrictMode] = useState(true)
  const [loadingProject, setLoadingProject] = useState(true)
  const [saving, setSaving] = useState(false)
  const [creatingVersion, setCreatingVersion] = useState(false)
  const [tailoring, setTailoring] = useState(false)
  const [exportBusy, setExportBusy] = useState<"pdf" | "docx" | null>(null)
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null)
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastSavedPayloadRef = useRef<string>("")

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login")
    }
  }, [isAuthenticated, isLoading, router])

  const loadProject = async () => {
    if (!token || !projectId) return
    setLoadingProject(true)
    try {
      const detail = await getStudioProject(token, projectId)
      setProjectDetail(detail)
      const initialVersion = detail.versions[0] ?? null
      setSelectedVersionId((current) => current ?? initialVersion?.id ?? null)
    } catch (error) {
      toast({
        title: "Unable to load project",
        description: (error as Error).message,
        variant: "destructive",
      })
    } finally {
      setLoadingProject(false)
    }
  }

  useEffect(() => {
    loadProject()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, projectId])

  const selectedVersion = useMemo(() => {
    if (!projectDetail || selectedVersionId == null) return null
    return projectDetail.versions.find((version) => version.id === selectedVersionId) ?? null
  }, [projectDetail, selectedVersionId])

  const baseVersion = useMemo(() => {
    if (!projectDetail) return null
    return projectDetail.versions.find((version) => version.kind === "base") ?? null
  }, [projectDetail])

  useEffect(() => {
    if (!selectedVersion) return
    setStructured(cloneStructuredResume(selectedVersion.resume_structured_json))
    const currentPayload = JSON.stringify(selectedVersion.resume_structured_json)
    lastSavedPayloadRef.current = currentPayload
    setLastSavedAt(selectedVersion.created_at)
  }, [selectedVersion])

  useEffect(() => {
    if (!token || !selectedVersion || !structured) return
    const payloadText = JSON.stringify(structured)
    if (payloadText === lastSavedPayloadRef.current) return

    if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    saveTimerRef.current = setTimeout(async () => {
      try {
        setSaving(true)
        const updated = await updateStudioVersion(token, selectedVersion.id, {
          resume_structured_json: structured,
          template_name: selectedVersion.template_name,
          template_settings: selectedVersion.template_settings_json ?? undefined,
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
        lastSavedPayloadRef.current = JSON.stringify(updated.resume_structured_json)
        setLastSavedAt(new Date().toISOString())
      } catch {
        return
      } finally {
        setSaving(false)
      }
    }, 850)

    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    }
  }, [selectedVersion, structured, token])

  const scoreSnapshot = selectedVersion?.score_snapshot_json ?? null
  const rewriteSuggestions = (scoreSnapshot?.rewrite_suggestions as Array<{
    requirement?: string
    issue?: string
    recommendation?: string
    example_bullet?: string
  }>) ?? []
  const missingEvidence = (scoreSnapshot?.missing_evidence as string[]) ?? []
  const fastestFixes = (scoreSnapshot?.fastest_fixes as string[]) ?? []

  function updateStructured(next: ResumeStudioStructuredResume) {
    setStructured(next)
  }

  function patchHeader(
    key: "name" | "title" | "email" | "phone" | "location",
    value: string
  ) {
    if (!structured) return
    const next = cloneStructuredResume(structured)
    next.header[key] = value
    updateStructured(next)
  }

  function patchSkillCategory(index: number, key: "name" | "items", value: string) {
    if (!structured) return
    const next = cloneStructuredResume(structured)
    if (key === "items") {
      next.skills.categories[index].items = value
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean)
    } else {
      next.skills.categories[index].name = value
    }
    updateStructured(next)
  }

  function patchExperience(index: number, field: "role" | "company" | "start" | "end", value: string) {
    if (!structured) return
    const next = cloneStructuredResume(structured)
    next.experience.items[index][field] = value
    updateStructured(next)
  }

  function patchExperienceBullets(index: number, value: string) {
    if (!structured) return
    const next = cloneStructuredResume(structured)
    next.experience.items[index].bullets = value
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
    updateStructured(next)
  }

  function patchProjects(index: number, field: "name" | "link", value: string) {
    if (!structured) return
    const next = cloneStructuredResume(structured)
    next.projects.items[index][field] = value
    updateStructured(next)
  }

  function patchProjectBullets(index: number, value: string) {
    if (!structured) return
    const next = cloneStructuredResume(structured)
    next.projects.items[index].bullets = value
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
    updateStructured(next)
  }

  function patchEducation(index: number, field: "school" | "degree" | "start" | "end", value: string) {
    if (!structured) return
    const next = cloneStructuredResume(structured)
    next.education.items[index][field] = value
    updateStructured(next)
  }

  async function handleCreateVersion() {
    if (!token || !projectDetail || !selectedVersion) return
    setCreatingVersion(true)
    try {
      const created = await createStudioVersion(token, projectDetail.project.id, {
        source_version_id: selectedVersion.id,
        kind: "base",
      })
      setProjectDetail((previous) => {
        if (!previous) return previous
        return { ...previous, versions: [created, ...previous.versions] }
      })
      setSelectedVersionId(created.id)
      toast({ title: "Version created", description: "You now have a branchable draft version." })
    } catch (error) {
      toast({
        title: "Unable to create version",
        description: (error as Error).message,
        variant: "destructive",
      })
    } finally {
      setCreatingVersion(false)
    }
  }

  async function handleTailor() {
    if (!token || !selectedVersion || jdText.trim().length < 50) return
    setTailoring(true)
    try {
      const tailored = await tailorStudioVersion(token, selectedVersion.id, {
        jd_text: jdText.trim(),
        strict_mode: strictMode,
      })
      setProjectDetail((previous) => {
        if (!previous) return previous
        return { ...previous, versions: [tailored, ...previous.versions] }
      })
      setSelectedVersionId(tailored.id)
      toast({
        title: "Tailored version ready",
        description: strictMode
          ? "Strict Truth Mode kept every suggestion evidence-grounded."
          : "Draft mode generated flexible rewrite suggestions.",
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

  async function handleExport(format: "pdf" | "docx") {
    if (!token || !selectedVersion) return
    setExportBusy(format)
    try {
      let exportRecord = await requestStudioExport(token, selectedVersion.id, format)
      for (let attempts = 0; attempts < 40; attempts += 1) {
        if (exportRecord.status === "completed") break
        if (exportRecord.status === "failed") {
          throw new Error(exportRecord.error_message || "Export failed")
        }
        await new Promise((resolve) => setTimeout(resolve, 1200))
        exportRecord = await getStudioExport(token, exportRecord.id)
      }

      if (exportRecord.status !== "completed") {
        throw new Error("Export is still processing. Please try again in a moment.")
      }

      const downloadUrl = makeStudioExportDownloadUrl(exportRecord.id)
      window.open(downloadUrl, "_blank")
      toast({ title: `${format.toUpperCase()} export ready` })
    } catch (error) {
      toast({
        title: "Export failed",
        description: (error as Error).message,
        variant: "destructive",
      })
    } finally {
      setExportBusy(null)
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
      title={`Resume Studio · ${projectDetail.project.title}`}
      description="Guided editing, strict tailoring, and production-safe exports."
      actions={
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" asChild>
            <Link href="/dashboard/studio">Studio Home</Link>
          </Button>
          <Button size="sm" variant="outline" onClick={handleCreateVersion} disabled={creatingVersion}>
            {creatingVersion ? <Loader2 className="h-4 w-4 animate-spin" /> : <CopyPlus className="h-4 w-4" />}
            New version
          </Button>
        </div>
      }
    >
      <PageTransition className="mx-auto w-full max-w-7xl space-y-5">
        <section className="surface-card space-y-4 p-4">
          <div className="flex flex-wrap items-center gap-2">
            <label className="text-sm font-medium text-muted-foreground">Version</label>
            <select
              value={selectedVersionId ?? undefined}
              onChange={(event) => setSelectedVersionId(Number(event.target.value))}
              className="rounded-lg border border-border bg-background px-2.5 py-1.5 text-sm"
            >
              {projectDetail.versions.map((version) => (
                <option key={version.id} value={version.id}>
                  #{version.id} · {version.kind} · {formatDate(version.created_at)}
                </option>
              ))}
            </select>
            {saving ? (
              <span className="text-xs text-muted-foreground">Autosaving...</span>
            ) : (
              <span className="text-xs text-muted-foreground">
                {lastSavedAt ? `Saved ${formatDate(lastSavedAt)}` : "Autosave enabled"}
              </span>
            )}
            {selectedVersion.kind === "tailored" && (
              <span className="rounded-full bg-primary-soft px-2 py-0.5 text-xs font-medium text-primary">
                Tailored
              </span>
            )}
          </div>
          <div className="grid gap-2 md:grid-cols-7">
            {STEPS.map((step, index) => (
              <button
                key={step}
                type="button"
                onClick={() => setStepIndex(index)}
                className={`rounded-xl border px-3 py-2 text-sm ${
                  stepIndex === index
                    ? "border-primary/40 bg-primary-soft text-primary"
                    : "border-border bg-background text-muted-foreground hover:text-foreground"
                }`}
              >
                {step}
              </button>
            ))}
          </div>
        </section>

        <div className="grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
          <section className="space-y-4">
            {stepIndex === 0 && (
              <SectionCard title="Header" description="Identity, contact, and profile links.">
                <div className="grid gap-3 md:grid-cols-2">
                  <Input value={structured.header.name} onChange={(event) => patchHeader("name", event.target.value)} placeholder="Full name" />
                  <Input value={structured.header.title} onChange={(event) => patchHeader("title", event.target.value)} placeholder="Professional title" />
                  <Input value={structured.header.email} onChange={(event) => patchHeader("email", event.target.value)} placeholder="Email" />
                  <Input value={structured.header.phone} onChange={(event) => patchHeader("phone", event.target.value)} placeholder="Phone" />
                  <Input value={structured.header.location} onChange={(event) => patchHeader("location", event.target.value)} placeholder="Location" />
                </div>
              </SectionCard>
            )}

            {stepIndex === 1 && (
              <SectionCard title="Summary" description="Keep this concise and role-adaptable.">
                <textarea
                  value={structured.summary}
                  onChange={(event) => {
                    const next = cloneStructuredResume(structured)
                    next.summary = event.target.value
                    updateStructured(next)
                  }}
                  className="min-h-[180px] w-full rounded-xl border border-border bg-background px-3 py-2 text-sm outline-none ring-primary transition focus:ring-2"
                  placeholder="Write a focused summary highlighting impact and role alignment."
                />
              </SectionCard>
            )}

            {stepIndex === 2 && (
              <SectionCard title="Skills" description="Categorize capabilities for ATS and recruiter scan speed.">
                <div className="space-y-4">
                  {structured.skills.categories.map((category, index) => (
                    <div key={`${category.name}-${index}`} className="rounded-xl border border-border/80 p-3">
                      <Input
                        value={category.name}
                        onChange={(event) => patchSkillCategory(index, "name", event.target.value)}
                        placeholder="Category name"
                      />
                      <textarea
                        value={category.items.join(", ")}
                        onChange={(event) => patchSkillCategory(index, "items", event.target.value)}
                        className="mt-2 min-h-[90px] w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none ring-primary transition focus:ring-2"
                        placeholder="Comma-separated skills"
                      />
                    </div>
                  ))}
                  <Button
                    variant="outline"
                    onClick={() => {
                      const next = cloneStructuredResume(structured)
                      next.skills.categories.push({ name: "Category", items: [] })
                      updateStructured(next)
                    }}
                  >
                    Add skill category
                  </Button>
                </div>
              </SectionCard>
            )}

            {stepIndex === 3 && (
              <SectionCard title="Experience" description="Evidence-based bullets drive match precision.">
                <div className="space-y-4">
                  {structured.experience.items.map((item, index) => (
                    <div key={`${item.role}-${item.company}-${index}`} className="rounded-xl border border-border/80 p-3">
                      <div className="grid gap-2 md:grid-cols-2">
                        <Input value={item.role} onChange={(event) => patchExperience(index, "role", event.target.value)} placeholder="Role" />
                        <Input value={item.company} onChange={(event) => patchExperience(index, "company", event.target.value)} placeholder="Company" />
                        <Input value={item.start} onChange={(event) => patchExperience(index, "start", event.target.value)} placeholder="Start date" />
                        <Input value={item.end} onChange={(event) => patchExperience(index, "end", event.target.value)} placeholder="End date" />
                      </div>
                      <textarea
                        value={item.bullets.join("\n")}
                        onChange={(event) => patchExperienceBullets(index, event.target.value)}
                        className="mt-2 min-h-[130px] w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none ring-primary transition focus:ring-2"
                        placeholder="One bullet per line"
                      />
                    </div>
                  ))}
                  <Button
                    variant="outline"
                    onClick={() => {
                      const next = cloneStructuredResume(structured)
                      next.experience.items.push({
                        company: "",
                        role: "",
                        location: "",
                        start: "",
                        end: "",
                        bullets: [],
                        tech: [],
                      })
                      updateStructured(next)
                    }}
                  >
                    Add experience item
                  </Button>
                </div>
              </SectionCard>
            )}

            {stepIndex === 4 && (
              <SectionCard title="Projects" description="Highlight role-relevant impact and tooling.">
                <div className="space-y-4">
                  {structured.projects.items.map((item, index) => (
                    <div key={`${item.name}-${index}`} className="rounded-xl border border-border/80 p-3">
                      <div className="grid gap-2 md:grid-cols-2">
                        <Input value={item.name} onChange={(event) => patchProjects(index, "name", event.target.value)} placeholder="Project name" />
                        <Input value={item.link} onChange={(event) => patchProjects(index, "link", event.target.value)} placeholder="Project link" />
                      </div>
                      <textarea
                        value={item.bullets.join("\n")}
                        onChange={(event) => patchProjectBullets(index, event.target.value)}
                        className="mt-2 min-h-[120px] w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none ring-primary transition focus:ring-2"
                        placeholder="One bullet per line"
                      />
                    </div>
                  ))}
                  <Button
                    variant="outline"
                    onClick={() => {
                      const next = cloneStructuredResume(structured)
                      next.projects.items.push({ name: "", link: "", bullets: [], tech: [] })
                      updateStructured(next)
                    }}
                  >
                    Add project
                  </Button>
                </div>
              </SectionCard>
            )}

            {stepIndex === 5 && (
              <SectionCard title="Education" description="Keep credentials clean, concise, and easy to scan.">
                <div className="space-y-4">
                  {structured.education.items.map((item, index) => (
                    <div key={`${item.school}-${index}`} className="rounded-xl border border-border/80 p-3">
                      <div className="grid gap-2 md:grid-cols-2">
                        <Input value={item.school} onChange={(event) => patchEducation(index, "school", event.target.value)} placeholder="School" />
                        <Input value={item.degree} onChange={(event) => patchEducation(index, "degree", event.target.value)} placeholder="Degree" />
                        <Input value={item.start} onChange={(event) => patchEducation(index, "start", event.target.value)} placeholder="Start date" />
                        <Input value={item.end} onChange={(event) => patchEducation(index, "end", event.target.value)} placeholder="End date" />
                      </div>
                    </div>
                  ))}
                  <Button
                    variant="outline"
                    onClick={() => {
                      const next = cloneStructuredResume(structured)
                      next.education.items.push({
                        school: "",
                        degree: "",
                        start: "",
                        end: "",
                        notes: [],
                      })
                      updateStructured(next)
                    }}
                  >
                    Add education item
                  </Button>
                </div>
              </SectionCard>
            )}

            {stepIndex === 6 && (
              <SectionCard title="Review" description="Final checks before tailoring and export.">
                <div className="space-y-3 text-sm">
                  <p className="inline-flex items-center gap-2 text-muted-foreground">
                    <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                    ATS keywords tracked: {structured.ats_keywords.length}
                  </p>
                  <p className="inline-flex items-center gap-2 text-muted-foreground">
                    <ShieldCheck className="h-4 w-4 text-primary" />
                    Evidence references: {Object.keys(structured.evidence_map).length}
                  </p>
                  {selectedVersion.resume_render_html && (
                    <a
                      href={`data:text/html;charset=utf-8,${encodeURIComponent(selectedVersion.resume_render_html)}`}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-2 text-primary hover:underline"
                    >
                      <Sparkles className="h-4 w-4" />
                      Open rendered HTML preview
                    </a>
                  )}
                </div>
              </SectionCard>
            )}
          </section>

          <aside className="space-y-4">
            <SectionCard title="Tailor to Job Description" description="Generate a role-optimized version from pasted JD text.">
              <div className="space-y-3">
                <textarea
                  value={jdText}
                  onChange={(event) => setJdText(event.target.value)}
                  className="min-h-[170px] w-full rounded-xl border border-border bg-background px-3 py-2 text-sm outline-none ring-primary transition focus:ring-2"
                  placeholder="Paste a full job description..."
                />
                <label className="inline-flex items-center gap-2 text-sm text-muted-foreground">
                  <input
                    type="checkbox"
                    checked={strictMode}
                    onChange={(event) => setStrictMode(event.target.checked)}
                  />
                  Strict Truth Mode (recommended)
                </label>
                <Button onClick={handleTailor} disabled={tailoring || jdText.trim().length < 50} className="w-full">
                  {tailoring ? <Loader2 className="h-4 w-4 animate-spin" /> : <WandSparkles className="h-4 w-4" />}
                  {tailoring ? "Tailoring..." : "Tailor this version"}
                </Button>
              </div>
            </SectionCard>

            <SectionCard title="Exports" description="Queue async generation and download when ready.">
              <div className="grid grid-cols-2 gap-2">
                <Button
                  variant="outline"
                  onClick={() => handleExport("pdf")}
                  disabled={exportBusy !== null}
                >
                  {exportBusy === "pdf" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                  PDF
                </Button>
                <Button
                  variant="outline"
                  onClick={() => handleExport("docx")}
                  disabled={exportBusy !== null}
                >
                  {exportBusy === "docx" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                  DOCX
                </Button>
              </div>
            </SectionCard>

            <SectionCard title="Suggestions" description="Evidence-grounded edits from the latest score snapshot.">
              <div className="space-y-3">
                {scoreSnapshot ? (
                  <>
                    <p className="text-sm text-foreground">
                      {(scoreSnapshot.recruiter_verdict as string) ?? "No recruiter verdict available yet."}
                    </p>
                    {missingEvidence.length > 0 && (
                      <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                        <p className="font-medium">Missing evidence</p>
                        <ul className="mt-1 list-disc space-y-1 pl-5">
                          {missingEvidence.slice(0, 4).map((entry) => (
                            <li key={entry}>{entry}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {fastestFixes.length > 0 && (
                      <div className="rounded-xl border border-border/80 bg-muted/30 p-3 text-sm">
                        <p className="font-medium text-foreground">Fastest fixes</p>
                        <ul className="mt-1 list-disc space-y-1 pl-5 text-muted-foreground">
                          {fastestFixes.slice(0, 4).map((entry) => (
                            <li key={entry}>{entry}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {rewriteSuggestions.length > 0 && (
                      <div className="space-y-2">
                        {rewriteSuggestions.slice(0, 4).map((suggestion, index) => (
                          <div key={`${suggestion.requirement}-${index}`} className="rounded-xl border border-border p-3">
                            <p className="text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                              {suggestion.requirement ?? "Requirement"}
                            </p>
                            <p className="mt-1 text-sm text-foreground">{suggestion.recommendation ?? suggestion.issue}</p>
                            {suggestion.example_bullet && (
                              <p className="mt-2 rounded-md bg-muted/50 px-2 py-1 text-xs text-muted-foreground">
                                {suggestion.example_bullet}
                              </p>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    Tailor this version with a JD to generate recruiter verdicts, missing evidence warnings, and rewrite suggestions.
                  </p>
                )}
              </div>
            </SectionCard>

            {selectedVersion.kind === "tailored" && baseVersion && baseVersion.id !== selectedVersion.id && (
              <SectionCard title="Version Diff" description="Quick compare between base and tailored plain text.">
                <div className="grid gap-3 text-xs md:grid-cols-2">
                  <div className="rounded-lg border border-border bg-muted/20 p-2">
                    <p className="mb-1 font-semibold uppercase tracking-[0.08em] text-muted-foreground">Base</p>
                    <p className="line-clamp-12 whitespace-pre-wrap text-muted-foreground">
                      {baseVersion.resume_plain_text ?? "—"}
                    </p>
                  </div>
                  <div className="rounded-lg border border-primary/25 bg-primary-soft/40 p-2">
                    <p className="mb-1 font-semibold uppercase tracking-[0.08em] text-primary">Tailored</p>
                    <p className="line-clamp-12 whitespace-pre-wrap text-foreground">
                      {selectedVersion.resume_plain_text ?? "—"}
                    </p>
                  </div>
                </div>
              </SectionCard>
            )}
          </aside>
        </div>
      </PageTransition>
    </DashboardLayout>
  )
}

"use client"

import Link from "next/link"
import { useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import {
  ArrowRight,
  Download,
  FileSearch,
  Grid3x3,
  LayoutList,
  Loader2,
  Plus,
  Search,
} from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import {
  StudioExport,
  StudioProject,
  downloadStudioExportBlob,
  getStudioExport,
  listStudioProjects,
  requestStudioExport,
} from "@/lib/api"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/ui/empty-state"
import { Input } from "@/components/ui/input"
import { PageTransition } from "@/components/ui/page-transition"
import { SegmentedControl } from "@/components/ui/segmented-control"
import { Skeleton } from "@/components/ui/skeleton"
import { useToast } from "@/components/ui/use-toast"

type SortMode = "updated_desc" | "created_desc" | "title_asc"
type ViewMode = "grid" | "table"

function StudioSkeleton() {
  return (
    <DashboardLayout title="Resume Studio" description="Build, tailor, and export investor-grade resumes.">
      <div className="mx-auto w-full max-w-6xl space-y-6">
        <Skeleton className="h-12 w-64 rounded-xl" />
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} className="h-44 w-full rounded-[var(--radius)]" />
          ))}
        </div>
      </div>
    </DashboardLayout>
  )
}

function formatDate(value: string | null) {
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

export default function ResumeStudioPage() {
  const { token, isAuthenticated, isLoading } = useAuth()
  const router = useRouter()
  const { toast } = useToast()
  const [projects, setProjects] = useState<StudioProject[]>([])
  const [loaded, setLoaded] = useState(false)
  const [query, setQuery] = useState("")
  const [sortMode, setSortMode] = useState<SortMode>("updated_desc")
  const [viewMode, setViewMode] = useState<ViewMode>("grid")
  const [exportingProjectId, setExportingProjectId] = useState<number | null>(null)

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login")
    }
  }, [isAuthenticated, isLoading, router])

  useEffect(() => {
    if (!token) return
    listStudioProjects(token)
      .then((value) => setProjects(value))
      .catch(() => setProjects([]))
      .finally(() => setLoaded(true))
  }, [token])

  const filteredProjects = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    const filtered = projects.filter((project) => {
      if (!normalizedQuery) return true
      return (
        project.title.toLowerCase().includes(normalizedQuery) ||
        project.source_type.toLowerCase().includes(normalizedQuery) ||
        project.tailored_tags.some((tag) => tag.toLowerCase().includes(normalizedQuery))
      )
    })

    return filtered.sort((left, right) => {
      if (sortMode === "title_asc") {
        return left.title.localeCompare(right.title)
      }
      const leftTime = new Date(
        sortMode === "created_desc" ? left.created_at : left.updated_at
      ).getTime()
      const rightTime = new Date(
        sortMode === "created_desc" ? right.created_at : right.updated_at
      ).getTime()
      return rightTime - leftTime
    })
  }, [projects, query, sortMode])

  async function quickExport(project: StudioProject) {
    if (!token || !project.latest_version_id) return
    setExportingProjectId(project.id)
    try {
      let exportRecord: StudioExport = await requestStudioExport(
        token,
        project.latest_version_id,
        "pdf"
      )
      let attempts = 0
      while (
        exportRecord.status !== "completed" &&
        exportRecord.status !== "failed" &&
        attempts < 30
      ) {
        await new Promise((resolve) => setTimeout(resolve, 1200))
        exportRecord = await getStudioExport(token, exportRecord.id)
        attempts += 1
      }
      if (exportRecord.status === "completed") {
        const blob = await downloadStudioExportBlob(token, exportRecord.id)
        const objectUrl = URL.createObjectURL(blob)
        window.open(objectUrl, "_blank")
        setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000)
        toast({ title: "Latest version exported", description: `${project.title} PDF is ready.` })
      } else if (exportRecord.status === "failed") {
        throw new Error(exportRecord.error_message || "Export failed")
      } else {
        toast({
          title: "Export still processing",
          description: "Open the project to continue tracking export status.",
        })
      }
    } catch (error) {
      toast({
        title: "Quick export failed",
        description: (error as Error).message,
        variant: "destructive",
      })
    } finally {
      setExportingProjectId(null)
    }
  }

  const statusPill = (status: StudioProject["last_export_status"]) => {
    if (!status) return <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">No exports</span>
    const styles =
      status === "completed"
        ? "bg-emerald-50 text-emerald-700"
        : status === "failed"
          ? "bg-rose-50 text-rose-700"
          : "bg-amber-50 text-amber-700"
    return (
      <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium capitalize ${styles}`}>
        {status}
      </span>
    )
  }

  if (isLoading || !isAuthenticated || !loaded) return <StudioSkeleton />

  return (
    <DashboardLayout
      title="Resume Studio"
      description="Projects, tailoring intelligence, and ATS-safe exports in one workspace."
      actions={
        <Button asChild size="sm">
          <Link href="/dashboard/studio/new">
            <Plus className="h-4 w-4" />
            New Project
          </Link>
        </Button>
      }
    >
      <PageTransition className="mx-auto w-full max-w-6xl space-y-5">
        <section className="surface-card space-y-4 p-4">
          <div className="grid gap-3 md:grid-cols-[1fr_auto_auto]">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search projects, tags, or source type"
                className="pl-9"
              />
            </div>
            <select
              value={sortMode}
              onChange={(event) => setSortMode(event.target.value as SortMode)}
              className="rounded-xl border border-border bg-background px-3 py-2 text-sm"
            >
              <option value="updated_desc">Updated (Newest)</option>
              <option value="created_desc">Created (Newest)</option>
              <option value="title_asc">Title (A-Z)</option>
            </select>
            <SegmentedControl
              options={[
                { label: "Grid", value: "grid" },
                { label: "Table", value: "table" },
              ]}
              value={viewMode}
              onChange={setViewMode}
            />
          </div>
        </section>

        {filteredProjects.length === 0 ? (
          <EmptyState
            icon={<FileSearch className="h-5 w-5" />}
            title={projects.length === 0 ? "No projects yet" : "No matching projects"}
            description={
              projects.length === 0
                ? "Create your first resume project and start tailoring with recruiter-grade precision."
                : "Try a different search term or sort order."
            }
            action={
              <Button asChild>
                <Link href="/dashboard/studio/new">Create your first resume</Link>
              </Button>
            }
          />
        ) : viewMode === "grid" ? (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {filteredProjects.map((project) => (
              <article
                key={project.id}
                className="surface-card group space-y-4 p-5 transition hover:-translate-y-0.5 hover:shadow-[var(--shadow-md)]"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-lg font-semibold tracking-tight text-foreground">{project.title}</p>
                    <div className="mt-1 flex flex-wrap items-center gap-2">
                      <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] capitalize text-muted-foreground">
                        {project.source_type.replaceAll("_", " ")}
                      </span>
                      {statusPill(project.last_export_status)}
                    </div>
                  </div>
                  <Grid3x3 className="h-4 w-4 text-muted-foreground" />
                </div>

                <div className="space-y-2 text-sm text-muted-foreground">
                  <p className="text-xs">Updated {formatDate(project.updated_at)}</p>
                  <p className="text-xs">
                    {project.versions_count} version{project.versions_count === 1 ? "" : "s"} · latest{" "}
                    {project.latest_version_kind ?? "base"}
                  </p>
                  {project.tailored_tags.length > 0 && (
                    <p className="line-clamp-1 text-xs">
                      {project.tailored_tags.slice(0, 2).join(" • ")}
                    </p>
                  )}
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <Button asChild size="sm">
                    <Link href={`/dashboard/studio/${project.id}`}>
                      Open
                      <ArrowRight className="h-4 w-4" />
                    </Link>
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => quickExport(project)}
                    disabled={!project.latest_version_id || exportingProjectId === project.id}
                  >
                    {exportingProjectId === project.id ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Download className="h-4 w-4" />
                    )}
                    Export
                  </Button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <section className="surface-card overflow-hidden">
            <div className="grid grid-cols-12 border-b bg-muted/60 px-4 py-3 text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
              <span className="col-span-4">Project</span>
              <span className="col-span-2">Source</span>
              <span className="col-span-2">Updated</span>
              <span className="col-span-2">Versions</span>
              <span className="col-span-2 text-right">Actions</span>
            </div>
            <div className="divide-y divide-border/70">
              {filteredProjects.map((project) => (
                <div key={project.id} className="grid grid-cols-12 items-center px-4 py-3">
                  <div className="col-span-4 space-y-1">
                    <p className="text-sm font-medium text-foreground">{project.title}</p>
                    <div className="flex items-center gap-2">
                      {statusPill(project.last_export_status)}
                    </div>
                  </div>
                  <p className="col-span-2 text-sm capitalize text-muted-foreground">
                    {project.source_type.replaceAll("_", " ")}
                  </p>
                  <p className="col-span-2 text-sm text-muted-foreground">{formatDate(project.updated_at)}</p>
                  <p className="col-span-2 text-sm text-muted-foreground">{project.versions_count}</p>
                  <div className="col-span-2 flex items-center justify-end gap-2">
                    <Button variant="outline" size="sm" asChild>
                      <Link href={`/dashboard/studio/${project.id}`}>
                        <LayoutList className="h-4 w-4" />
                        Open
                      </Link>
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => quickExport(project)}
                      disabled={!project.latest_version_id || exportingProjectId === project.id}
                    >
                      {exportingProjectId === project.id ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Download className="h-4 w-4" />
                      )}
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}
      </PageTransition>
    </DashboardLayout>
  )
}

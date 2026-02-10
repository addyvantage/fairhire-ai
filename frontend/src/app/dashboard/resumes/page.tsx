"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { ColumnDef } from "@tanstack/react-table"
import { AlertCircle, Eye, FileText, Loader2, Play, Upload } from "lucide-react"
import { motion } from "framer-motion"
import { useAuth } from "@/lib/auth-context"
import {
  AnalysisResult,
  JobProfile,
  Resume,
  getAnalysisByResume,
  getLastUsedProfile,
  listJobProfiles,
  listResumes,
  triggerTargetedAnalysis,
  uploadResume,
} from "@/lib/api"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { DataTable } from "@/components/tables/data-table"
import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/ui/empty-state"
import { FileUpload } from "@/components/ui/file-upload"
import { JobProfileSelector } from "@/components/ui/job-profile-selector"
import { PageTransition } from "@/components/ui/page-transition"
import { SegmentedControl } from "@/components/ui/segmented-control"
import { Skeleton } from "@/components/ui/skeleton"
import { StatusPill } from "@/components/ui/status-pill"
import { useToast } from "@/components/ui/use-toast"

type ResumeWithAnalysis = Resume & {
  analysis?: AnalysisResult | null
}

type ViewMode = "table" | "cards"

function formatDate(value: string) {
  const date = new Date(value)
  if (isNaN(date.getTime())) return "—"
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  })
}

function ResumesSkeleton() {
  return (
    <DashboardLayout title="Resumes" description="Upload candidates and run role-specific analysis.">
      <div className="mx-auto w-full max-w-6xl space-y-6">
        <Skeleton className="h-36 w-full rounded-[var(--radius)]" />
        <Skeleton className="h-10 w-48 rounded-xl" />
        <div className="surface-card space-y-4 p-4">
          <Skeleton className="h-8 w-full rounded-lg" />
          <Skeleton className="h-8 w-full rounded-lg" />
          <Skeleton className="h-8 w-full rounded-lg" />
        </div>
      </div>
    </DashboardLayout>
  )
}

export default function ResumesPage() {
  const { token, isAuthenticated, isLoading } = useAuth()
  const { toast } = useToast()
  const router = useRouter()

  const [resumes, setResumes] = useState<ResumeWithAnalysis[]>([])
  const [viewMode, setViewMode] = useState<ViewMode>("table")
  const [uploading, setUploading] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const [analyzingIds, setAnalyzingIds] = useState<Set<number>>(new Set())
  const pollingRef = useRef<Map<number, ReturnType<typeof setInterval>>>(new Map())
  const pollMissesRef = useRef<Map<number, number>>(new Map())

  const [jobProfiles, setJobProfiles] = useState<JobProfile[]>([])
  const [lastUsedProfileId, setLastUsedProfileId] = useState<number | null>(null)
  const [selectorResumeId, setSelectorResumeId] = useState<number | null>(null)
  const tokenRef = useRef<string | null>(token)

  useEffect(() => {
    tokenRef.current = token
  }, [token])

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login")
    }
  }, [isLoading, isAuthenticated, router])

  useEffect(() => {
    if (!token) return
    listJobProfiles(token).then(setJobProfiles).catch(() => undefined)
    getLastUsedProfile(token)
      .then((profile) => setLastUsedProfileId(profile?.id ?? null))
      .catch(() => undefined)
  }, [token])

  const stopPolling = useCallback((resumeId: number) => {
    const interval = pollingRef.current.get(resumeId)
    if (!interval) return
    clearInterval(interval)
    pollingRef.current.delete(resumeId)
    pollMissesRef.current.delete(resumeId)
    setAnalyzingIds((previous) => {
      const next = new Set(previous)
      next.delete(resumeId)
      return next
    })
  }, [])

  const startPolling = useCallback(
    (resumeId: number) => {
      if (pollingRef.current.has(resumeId)) return

      setAnalyzingIds((previous) => new Set(previous).add(resumeId))
      const interval = setInterval(async () => {
        const authToken = tokenRef.current
        if (!authToken) return

        try {
          const analysis = await getAnalysisByResume(authToken, resumeId)
          if (!analysis) {
            const misses = (pollMissesRef.current.get(resumeId) ?? 0) + 1
            pollMissesRef.current.set(resumeId, misses)
            if (misses >= 8) {
              stopPolling(resumeId)
            }
            return
          }
          pollMissesRef.current.set(resumeId, 0)

          setResumes((previous) =>
            previous.map((entry) => (entry.id === resumeId ? { ...entry, analysis } : entry))
          )

          if (analysis.status === "completed" || analysis.status === "failed") {
            stopPolling(resumeId)
            if (analysis.status === "completed") {
              toast({
                title: "Analysis complete",
                description: `Match score ${analysis.match_score ?? 0}%`,
              })
            } else {
              toast({
                title: "Analysis failed",
                description: analysis.error_message ?? "An unexpected error occurred.",
                variant: "destructive",
              })
            }
          }
        } catch {
          return
        }
      }, 2500)

      pollingRef.current.set(resumeId, interval)
    },
    [stopPolling, toast]
  )

  const fetchResumes = useCallback(async () => {
    if (!token) return
    try {
      const records = await listResumes(token)
      const enriched = await Promise.all(
        records.map(async (resume) => {
          try {
            const analysis = await getAnalysisByResume(token, resume.id)
            return { ...resume, analysis }
          } catch {
            return { ...resume, analysis: null }
          }
        })
      )

      setResumes(enriched)
      setLoaded(true)

      enriched.forEach((resume) => {
        if (resume.analysis?.status === "queued" || resume.analysis?.status === "processing") {
          startPolling(resume.id)
        }
      })
    } catch {
      setLoaded(true)
      setResumes([])
    }
  }, [startPolling, token])

  useEffect(() => {
    fetchResumes()
    return () => {
      pollingRef.current.forEach((interval) => clearInterval(interval))
      pollingRef.current.clear()
      pollMissesRef.current.clear()
    }
  }, [fetchResumes])

  const handleAnalyze = useCallback((resumeId: number) => {
    setSelectorResumeId(resumeId)
  }, [])

  const handleProfileSelected = useCallback(
    async (profile: JobProfile) => {
      const resumeId = selectorResumeId
      setSelectorResumeId(null)
      if (!resumeId) return

      const authToken = tokenRef.current
      if (!authToken) return

      try {
        await triggerTargetedAnalysis(authToken, resumeId, profile.id)
        setLastUsedProfileId(profile.id)
        setResumes((previous) =>
          previous.map((resume) =>
            resume.id === resumeId
              ? {
                  ...resume,
                  analysis: {
                    id: 0,
                    resume_id: resumeId,
                    job_profile_id: profile.id,
                    status: "queued",
                    match_score: null,
                    extracted_metadata: null,
                    job_match_result: null,
                    error_message: null,
                    started_at: null,
                    completed_at: null,
                    created_at: new Date().toISOString(),
                  },
                }
              : resume
          )
        )

        toast({
          title: "Analysis queued",
          description: `Scoring against ${profile.title}.`,
        })
        startPolling(resumeId)
      } catch (error) {
        toast({
          title: "Unable to start analysis",
          description: (error as Error).message,
          variant: "destructive",
        })
      }
    },
    [selectorResumeId, startPolling, toast]
  )

  async function handleFileSelect(file: File) {
    if (!token) return
    setUploading(true)
    try {
      await uploadResume(token, file)
      toast({
        title: "Resume uploaded",
        description: `${file.name} is ready for analysis.`,
      })
      fetchResumes()
    } catch (error) {
      toast({
        title: "Upload failed",
        description: (error as Error).message,
        variant: "destructive",
      })
    } finally {
      setUploading(false)
    }
  }

  const columns = useMemo<ColumnDef<ResumeWithAnalysis, unknown>[]>(
    () => [
      {
        accessorKey: "original_filename",
        header: "Resume",
        cell: ({ row }) => (
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted">
              <FileText className="h-4 w-4 text-muted-foreground" />
            </div>
            <p className="truncate font-medium text-foreground">{row.original.original_filename}</p>
          </div>
        ),
      },
      {
        accessorKey: "created_at",
        header: "Uploaded",
        cell: ({ row }) => <span className="text-sm text-muted-foreground">{formatDate(row.original.created_at)}</span>,
      },
      {
        id: "status",
        header: "Status",
        cell: ({ row }) => {
          const status = row.original.analysis?.status
          if (!status) return <span className="text-sm text-muted-foreground">Ready</span>
          return <StatusPill status={status} />
        },
      },
      {
        id: "score",
        header: "Match Score",
        cell: ({ row }) => {
          const score = row.original.analysis?.match_score
          if (score == null) return <span className="text-sm text-muted-foreground">—</span>
          return <span className="text-sm font-semibold tabular-nums text-foreground">{score}%</span>
        },
      },
      {
        id: "actions",
        header: "",
        cell: ({ row }) => <RowAction resume={row.original} onAnalyze={handleAnalyze} router={router} />,
      },
    ],
    [handleAnalyze, router]
  )

  if (isLoading || !isAuthenticated) return <ResumesSkeleton />

  return (
    <DashboardLayout
      title="Resumes"
      description="Upload candidates and run role-specific analysis."
      actions={
        <div className="flex items-center gap-2">
          <SegmentedControl
            options={[
              { label: "Table", value: "table" },
              { label: "Cards", value: "cards" },
            ]}
            value={viewMode}
            onChange={setViewMode}
          />
          <Button size="sm" variant="outline" onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}>
            <Upload className="h-4 w-4" />
            Upload
          </Button>
        </div>
      }
    >
      <PageTransition className="mx-auto w-full max-w-6xl">
        <FileUpload onFileSelect={handleFileSelect} accept=".pdf,.doc,.docx" disabled={uploading} />

        {uploading && (
          <div className="surface-card flex items-center gap-2 px-4 py-3">
            <Loader2 className="h-4 w-4 animate-spin text-primary" />
            <p className="text-sm text-muted-foreground">Uploading resume…</p>
          </div>
        )}

        {loaded && resumes.length > 0 && viewMode === "table" && <DataTable columns={columns} data={resumes} />}

        {loaded && resumes.length > 0 && viewMode === "cards" && (
          <div className="grid gap-4 md:grid-cols-2">
            {resumes.map((resume) => (
              <motion.div
                key={resume.id}
                whileHover={{ y: -2 }}
                className="surface-card flex flex-col justify-between gap-4 p-5"
              >
                <div className="space-y-2">
                  <div className="flex items-start justify-between gap-3">
                    <p className="line-clamp-2 text-base font-medium text-foreground">{resume.original_filename}</p>
                    {resume.analysis?.status ? (
                      <StatusPill status={resume.analysis.status} />
                    ) : (
                      <span className="rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground">
                        Ready
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground">Uploaded {formatDate(resume.created_at)}</p>
                  <p className="text-sm text-foreground">
                    Match score:{" "}
                    <span className="font-semibold tabular-nums">
                      {resume.analysis?.match_score != null ? `${resume.analysis.match_score}%` : "—"}
                    </span>
                  </p>
                </div>
                <div className="flex justify-end">
                  <RowAction resume={resume} onAnalyze={handleAnalyze} router={router} />
                </div>
              </motion.div>
            ))}
          </div>
        )}

        {loaded && resumes.length === 0 && !uploading && (
          <EmptyState
            icon={<FileText className="h-5 w-5" />}
            title="No resumes yet"
            description="Import your first resume to start generating bias-aware candidate insights."
          />
        )}
      </PageTransition>

      {selectorResumeId !== null && (
        <JobProfileSelector
          profiles={jobProfiles}
          lastUsedProfileId={lastUsedProfileId}
          onSelect={handleProfileSelected}
          onClose={() => setSelectorResumeId(null)}
        />
      )}
    </DashboardLayout>
  )
}

function RowAction({
  resume,
  onAnalyze,
  router,
}: {
  resume: ResumeWithAnalysis
  onAnalyze: (resumeId: number) => void
  router: ReturnType<typeof useRouter>
}) {
  const status = resume.analysis?.status

  if (status === "queued" || status === "processing") {
    return (
      <Button size="sm" variant="outline" disabled>
        <Loader2 className="h-4 w-4 animate-spin" />
        Processing
      </Button>
    )
  }

  if (status === "completed") {
    return (
      <Button
        size="sm"
        variant="outline"
        onClick={() => {
          router.push(`/dashboard/resumes/${resume.id}/analysis`)
        }}
      >
        <Eye className="h-4 w-4" />
        View analysis
      </Button>
    )
  }

  if (status === "failed") {
    return (
      <div className="flex items-center gap-2">
        <span className="inline-flex items-center gap-1 text-xs font-medium text-destructive">
          <AlertCircle className="h-3.5 w-3.5" />
          Failed
        </span>
        <Button size="sm" variant="outline" onClick={() => onAnalyze(resume.id)}>
          Retry
        </Button>
      </div>
    )
  }

  return (
    <Button size="sm" onClick={() => onAnalyze(resume.id)}>
      <Play className="h-4 w-4" />
      Analyze
    </Button>
  )
}

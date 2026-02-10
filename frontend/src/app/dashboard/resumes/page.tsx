"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { ColumnDef } from "@tanstack/react-table"
import { FileText, Loader2, Play, Eye, AlertCircle } from "lucide-react"
import { motion } from "framer-motion"
import { useAuth } from "@/lib/auth-context"
import {
  listResumes,
  uploadResume,
  triggerTargetedAnalysis,
  listJobProfiles,
  getLastUsedProfile,
  getAnalysisByResume,
  type Resume,
  type AnalysisResult,
  type JobProfile,
} from "@/lib/api"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { Sidebar } from "@/components/layout/sidebar"
import { FileUpload } from "@/components/ui/file-upload"
import { VirtualizedTable } from "@/components/ui/virtualized-table"
import { Skeleton } from "@/components/ui/skeleton"
import { Button } from "@/components/ui/button"
import { JobProfileSelector } from "@/components/ui/job-profile-selector"
import { useToast } from "@/components/ui/use-toast"

function ResumesSkeleton() {
  return (
    <DashboardLayout sidebar={<Sidebar />}>
      <div className="mx-auto max-w-5xl space-y-8">
        <div className="space-y-2">
          <Skeleton className="h-7 w-28" />
          <Skeleton className="h-4 w-64" />
        </div>
        <Skeleton className="h-32 w-full rounded-xl" />
        <div className="space-y-0 rounded-xl border overflow-hidden">
          <div className="border-b bg-muted/30 px-4 py-2.5 flex gap-16">
            <Skeleton className="h-3 w-12" />
            <Skeleton className="h-3 w-12" />
            <Skeleton className="h-3 w-12" />
          </div>
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="border-b last:border-0 px-4 py-3 flex gap-16">
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-4 w-20" />
            </div>
          ))}
        </div>
      </div>
    </DashboardLayout>
  )
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return "—"
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  })
}

type ResumeWithAnalysis = Resume & {
  analysis?: AnalysisResult | null
}

export default function ResumesPage() {
  const { token, isAuthenticated, isLoading } = useAuth()
  const [resumes, setResumes] = useState<ResumeWithAnalysis[]>([])
  const [uploading, setUploading] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const [analyzingIds, setAnalyzingIds] = useState<Set<number>>(new Set())
  const pollingRef = useRef<Map<number, ReturnType<typeof setInterval>>>(new Map())
  const router = useRouter()
  const { toast } = useToast()

  // Job profile selector state
  const [jobProfiles, setJobProfiles] = useState<JobProfile[]>([])
  const [lastUsedProfileId, setLastUsedProfileId] = useState<number | null>(null)
  const [selectorResumeId, setSelectorResumeId] = useState<number | null>(null)

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login")
    }
  }, [isLoading, isAuthenticated, router])

  // Store token in a ref so polling callbacks always have the latest
  const tokenRef = useRef(token)
  useEffect(() => {
    tokenRef.current = token
  }, [token])

  // Fetch job profiles and last-used profile on mount
  useEffect(() => {
    if (!token) return
    listJobProfiles(token).then(setJobProfiles).catch(() => {})
    getLastUsedProfile(token)
      .then((p) => setLastUsedProfileId(p?.id ?? null))
      .catch(() => {})
  }, [token])

  const startPolling = useCallback((resumeId: number) => {
    if (pollingRef.current.has(resumeId)) return

    setAnalyzingIds((prev) => new Set(prev).add(resumeId))

    const interval = setInterval(async () => {
      const t = tokenRef.current
      if (!t) return
      try {
        const analysis = await getAnalysisByResume(t, resumeId)
        if (!analysis) return

        setResumes((prev) =>
          prev.map((r) => (r.id === resumeId ? { ...r, analysis } : r))
        )

        if (analysis.status === "completed" || analysis.status === "failed") {
          clearInterval(interval)
          pollingRef.current.delete(resumeId)
          setAnalyzingIds((prev) => {
            const next = new Set(prev)
            next.delete(resumeId)
            return next
          })

          if (analysis.status === "completed") {
            toast({
              title: "Analysis complete",
              description: `Score: ${analysis.match_score}%`,
            })
          } else {
            toast({
              title: "Analysis failed",
              description: analysis.error_message || "An error occurred",
              variant: "destructive",
            })
          }
        }
      } catch {
        // Silently retry on network errors
      }
    }, 3000)

    pollingRef.current.set(resumeId, interval)
  }, [toast])

  const fetchResumes = useCallback(async () => {
    if (!token) return
    try {
      const data = await listResumes(token)

      const withAnalysis = await Promise.all(
        data.map(async (resume) => {
          try {
            const analysis = await getAnalysisByResume(token, resume.id)
            return { ...resume, analysis }
          } catch {
            return { ...resume, analysis: null }
          }
        })
      )

      setResumes(withAnalysis)
      setLoaded(true)

      for (const r of withAnalysis) {
        if (
          r.analysis &&
          (r.analysis.status === "queued" || r.analysis.status === "processing")
        ) {
          startPolling(r.id)
        }
      }
    } catch {
      setResumes([])
      setLoaded(true)
    }
  }, [token, startPolling])

  useEffect(() => {
    fetchResumes()
    return () => {
      pollingRef.current.forEach((interval) => clearInterval(interval))
      pollingRef.current.clear()
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

      const t = tokenRef.current
      if (!t) return
      try {
        await triggerTargetedAnalysis(t, resumeId, profile.id)
        setLastUsedProfileId(profile.id)
        toast({
          title: "Analysis started",
          description: `Scoring against ${profile.title}...`,
        })

        setResumes((prev) =>
          prev.map((r) =>
            r.id === resumeId
              ? {
                  ...r,
                  analysis: {
                    id: 0,
                    resume_id: resumeId,
                    job_profile_id: profile.id,
                    status: "queued" as const,
                    match_score: null,
                    extracted_metadata: null,
                    job_match_result: null,
                    error_message: null,
                    started_at: null,
                    completed_at: null,
                    created_at: new Date().toISOString(),
                  },
                }
              : r
          )
        )

        startPolling(resumeId)
      } catch (err) {
        toast({
          title: "Failed to start analysis",
          description: (err as Error).message,
          variant: "destructive",
        })
      }
    },
    [selectorResumeId, toast, startPolling]
  )

  async function handleFileSelect(file: File) {
    if (!token) return
    setUploading(true)
    try {
      await uploadResume(token, file)
      toast({ title: "Resume uploaded", description: file.name })
      fetchResumes()
    } catch (err) {
      toast({
        title: "Upload failed",
        description: (err as Error).message,
        variant: "destructive",
      })
    } finally {
      setUploading(false)
    }
  }

  const columns: ColumnDef<ResumeWithAnalysis, unknown>[] = useMemo(
    () => [
      {
        accessorKey: "original_filename",
        header: "File",
        cell: ({ row }) => (
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted/60">
              <FileText className="h-3.5 w-3.5 text-muted-foreground" />
            </div>
            <span className="font-medium text-foreground truncate">
              {row.original.original_filename}
            </span>
          </div>
        ),
      },
      {
        accessorKey: "created_at",
        header: "Uploaded",
        cell: ({ row }) => (
          <span className="text-muted-foreground tabular-nums">
            {formatDate(row.original.created_at)}
          </span>
        ),
      },
      {
        id: "score",
        header: "Score",
        cell: ({ row }) => {
          const analysis = row.original.analysis
          if (!analysis || analysis.status !== "completed" || analysis.match_score == null) {
            return <span className="text-muted-foreground text-xs">—</span>
          }
          return (
            <span className="font-medium tabular-nums text-foreground">
              {analysis.match_score}%
            </span>
          )
        },
      },
      {
        id: "actions",
        header: "",
        cell: ({ row }) => {
          const resume = row.original
          const analysis = resume.analysis
          const isAnalyzing = analyzingIds.has(resume.id)

          if (isAnalyzing || (analysis && (analysis.status === "queued" || analysis.status === "processing"))) {
            return (
              <div className="flex justify-end">
                <Button size="sm" variant="outline" disabled className="gap-1.5 text-xs">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  Processing...
                </Button>
              </div>
            )
          }

          if (analysis?.status === "completed") {
            return (
              <div className="flex justify-end">
                <Button
                  size="sm"
                  variant="outline"
                  className="gap-1.5 text-xs"
                  onClick={(e) => {
                    e.stopPropagation()
                    router.push(`/dashboard/resumes/${resume.id}/analysis`)
                  }}
                >
                  <Eye className="h-3 w-3" />
                  View Analysis
                </Button>
              </div>
            )
          }

          if (analysis?.status === "failed") {
            return (
              <div className="flex justify-end items-center gap-2">
                <span className="text-xs text-destructive flex items-center gap-1">
                  <AlertCircle className="h-3 w-3" />
                  Failed
                </span>
                <Button
                  size="sm"
                  variant="outline"
                  className="gap-1.5 text-xs"
                  onClick={(e) => {
                    e.stopPropagation()
                    handleAnalyze(resume.id)
                  }}
                >
                  <Play className="h-3 w-3" />
                  Retry
                </Button>
              </div>
            )
          }

          return (
            <div className="flex justify-end">
              <Button
                size="sm"
                variant="default"
                className="gap-1.5 text-xs"
                onClick={(e) => {
                  e.stopPropagation()
                  handleAnalyze(resume.id)
                }}
              >
                <Play className="h-3 w-3" />
                Analyze
              </Button>
            </div>
          )
        },
      },
    ],
    [analyzingIds, router, handleAnalyze]
  )

  if (isLoading || !isAuthenticated) {
    return <ResumesSkeleton />
  }

  return (
    <DashboardLayout sidebar={<Sidebar />}>
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
        className="mx-auto max-w-5xl space-y-8"
      >
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-foreground">
            Resumes
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Upload and manage candidate resumes
          </p>
        </div>

        <FileUpload
          onFileSelect={handleFileSelect}
          accept=".pdf,.doc,.docx"
          disabled={uploading}
        />

        {uploading && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            className="flex items-center gap-2.5 text-sm text-muted-foreground"
          >
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            <span>Uploading...</span>
          </motion.div>
        )}

        {loaded && resumes.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: 0.05 }}
          >
            <VirtualizedTable columns={columns} data={resumes} />
          </motion.div>
        )}

        {loaded && resumes.length === 0 && !uploading && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.1 }}
            className="rounded-xl border border-dashed bg-muted/20 py-16 text-center"
          >
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-muted/60">
              <FileText className="h-5 w-5 text-muted-foreground/60" />
            </div>
            <p className="text-sm font-medium text-foreground/80">
              No resumes yet
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              Upload your first resume to get started
            </p>
          </motion.div>
        )}
      </motion.div>

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

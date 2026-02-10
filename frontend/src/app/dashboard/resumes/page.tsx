"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import { ColumnDef } from "@tanstack/react-table"
import { FileText } from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import { listResumes, uploadResume, type Resume } from "@/lib/api"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { Sidebar } from "@/components/layout/sidebar"
import { FileUpload } from "@/components/ui/file-upload"
import { VirtualizedTable } from "@/components/ui/virtualized-table"
import { Skeleton } from "@/components/ui/skeleton"
import { useToast } from "@/components/ui/use-toast"

const statusStyles: Record<Resume["status"], string> = {
  pending: "bg-secondary text-secondary-foreground",
  processing: "bg-primary/10 text-primary",
  completed: "bg-emerald-50 text-emerald-700",
  failed: "bg-destructive/10 text-destructive",
}

function ResumesSkeleton() {
  return (
    <DashboardLayout sidebar={<Sidebar />}>
      <div className="mx-auto max-w-6xl space-y-8">
        <div className="space-y-2">
          <Skeleton className="h-7 w-28" />
          <Skeleton className="h-4 w-64" />
        </div>
        <div className="rounded-lg border border-dashed bg-background p-8 space-y-3">
          <Skeleton className="mx-auto h-10 w-10 rounded-full" />
          <Skeleton className="mx-auto h-4 w-48" />
          <Skeleton className="mx-auto h-9 w-24" />
        </div>
        <div className="rounded-md border bg-background">
          <div className="border-b px-4 py-3 flex gap-16">
            <Skeleton className="h-4 w-16" />
            <Skeleton className="h-4 w-14" />
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-4 w-18" />
          </div>
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="border-b last:border-0 px-4 py-3 flex gap-16">
              <Skeleton className="h-4 w-36" />
              <Skeleton className="h-4 w-16" />
              <Skeleton className="h-4 w-12" />
              <Skeleton className="h-4 w-24" />
            </div>
          ))}
        </div>
      </div>
    </DashboardLayout>
  )
}

export default function ResumesPage() {
  const { token, isAuthenticated, isLoading } = useAuth()
  const [resumes, setResumes] = useState<Resume[]>([])
  const [uploading, setUploading] = useState(false)
  const router = useRouter()
  const { toast } = useToast()

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login")
    }
  }, [isLoading, isAuthenticated, router])

  const fetchResumes = useCallback(() => {
    if (!token) return
    listResumes(token)
      .then(setResumes)
      .catch(() => {
        setResumes([])
      })
  }, [token])

  useEffect(() => {
    fetchResumes()
  }, [fetchResumes])

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

  const columns: ColumnDef<Resume, any>[] = useMemo(
    () => [
      {
        accessorKey: "filename",
        header: "File",
        cell: ({ row }) => (
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
            <span className="font-medium truncate">{row.original.filename}</span>
          </div>
        ),
      },
      {
        accessorKey: "status",
        header: "Status",
        cell: ({ row }) => (
          <span
            className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${statusStyles[row.original.status]}`}
          >
            {row.original.status}
          </span>
        ),
      },
      {
        accessorKey: "match_score",
        header: "Match Score",
        cell: ({ row }) =>
          row.original.match_score != null ? (
            <span className="tabular-nums">{row.original.match_score}%</span>
          ) : (
            <span className="text-muted-foreground">—</span>
          ),
      },
      {
        accessorKey: "uploaded_at",
        header: "Uploaded",
        cell: ({ row }) => {
          const date = new Date(row.original.uploaded_at)
          return (
            <span className="text-muted-foreground">
              {date.toLocaleDateString("en-US", {
                month: "short",
                day: "numeric",
                year: "numeric",
              })}
            </span>
          )
        },
      },
    ],
    []
  )

  if (isLoading || !isAuthenticated) {
    return <ResumesSkeleton />
  }

  return (
    <DashboardLayout sidebar={<Sidebar />}>
      <div className="mx-auto max-w-6xl space-y-8">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            Resumes
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Upload and manage candidate resumes
          </p>
        </div>

        <FileUpload
          onFileSelect={handleFileSelect}
          accept=".pdf,.doc,.docx"
        />
        {uploading && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <div className="h-3 w-3 animate-pulse rounded-full bg-primary/40" />
            Uploading...
          </div>
        )}

        {resumes.length > 0 ? (
          <VirtualizedTable columns={columns} data={resumes} />
        ) : (
          <div className="rounded-md border border-dashed bg-background py-16 text-center">
            <FileText className="mx-auto h-10 w-10 text-muted-foreground/40" />
            <p className="mt-4 text-sm font-medium text-foreground">
              No resumes yet
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              Upload your first resume to get started
            </p>
          </div>
        )}
      </div>
    </DashboardLayout>
  )
}

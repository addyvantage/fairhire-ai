"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { ColumnDef } from "@tanstack/react-table"
import { FileText } from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import { listResumes, uploadResume, type Resume } from "@/lib/api"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { Sidebar } from "@/components/layout/sidebar"
import { FileUpload } from "@/components/ui/file-upload"
import { VirtualizedTable } from "@/components/ui/virtualized-table"

const statusStyles: Record<Resume["status"], string> = {
  pending: "bg-secondary text-secondary-foreground",
  processing: "bg-primary/10 text-primary",
  completed: "bg-emerald-50 text-emerald-700",
  failed: "bg-destructive/10 text-destructive",
}

export default function ResumesPage() {
  const { token, isAuthenticated, isLoading } = useAuth()
  const [resumes, setResumes] = useState<Resume[]>([])
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState("")

  const fetchResumes = useCallback(() => {
    if (!token) return
    listResumes(token)
      .then(setResumes)
      .catch(() => {
        // API may not be wired yet — show empty state
        setResumes([])
      })
  }, [token])

  useEffect(() => {
    fetchResumes()
  }, [fetchResumes])

  async function handleFileSelect(file: File) {
    if (!token) return
    setUploadError("")
    setUploading(true)
    try {
      await uploadResume(token, file)
      fetchResumes()
    } catch (err) {
      setUploadError((err as Error).message)
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
            <FileText className="h-4 w-4 text-muted-foreground" />
            <span className="font-medium">{row.original.filename}</span>
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
          row.original.match_score != null
            ? `${row.original.match_score}%`
            : "—",
      },
      {
        accessorKey: "uploaded_at",
        header: "Uploaded",
        cell: ({ row }) => {
          const date = new Date(row.original.uploaded_at)
          return date.toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
          })
        },
      },
    ],
    []
  )

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-muted/30">
        <p className="text-sm text-muted-foreground">Loading...</p>
      </div>
    )
  }

  if (!isAuthenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-muted/30">
        <p className="text-sm text-muted-foreground">Redirecting...</p>
      </div>
    )
  }

  return (
    <DashboardLayout sidebar={<Sidebar />}>
      <div className="space-y-8">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            Resumes
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Upload and manage candidate resumes
          </p>
        </div>

        <div className="space-y-2">
          <FileUpload
            onFileSelect={handleFileSelect}
            accept=".pdf,.doc,.docx"
          />
          {uploading && (
            <p className="text-sm text-muted-foreground">Uploading...</p>
          )}
          {uploadError && (
            <p className="text-sm text-destructive">{uploadError}</p>
          )}
        </div>

        {resumes.length > 0 ? (
          <VirtualizedTable columns={columns} data={resumes} />
        ) : (
          <div className="rounded-md border border-dashed bg-background py-16 text-center">
            <FileText className="mx-auto h-10 w-10 text-muted-foreground/50" />
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

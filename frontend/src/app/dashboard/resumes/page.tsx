"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import { ColumnDef } from "@tanstack/react-table"
import { FileText, Loader2 } from "lucide-react"
import { motion } from "framer-motion"
import { useAuth } from "@/lib/auth-context"
import { listResumes, uploadResume, type Resume } from "@/lib/api"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { Sidebar } from "@/components/layout/sidebar"
import { FileUpload } from "@/components/ui/file-upload"
import { VirtualizedTable } from "@/components/ui/virtualized-table"
import { Skeleton } from "@/components/ui/skeleton"
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
          </div>
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="border-b last:border-0 px-4 py-3 flex gap-16">
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-4 w-24" />
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

export default function ResumesPage() {
  const { token, isAuthenticated, isLoading } = useAuth()
  const [resumes, setResumes] = useState<Resume[]>([])
  const [uploading, setUploading] = useState(false)
  const [loaded, setLoaded] = useState(false)
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
      .then((data) => {
        setResumes(data)
        setLoaded(true)
      })
      .catch(() => {
        setResumes([])
        setLoaded(true)
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
    ],
    []
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
    </DashboardLayout>
  )
}

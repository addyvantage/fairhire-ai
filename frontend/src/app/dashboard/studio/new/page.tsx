"use client"

import Link from "next/link"
import { useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import { CheckCircle2, FileUp, ShieldCheck, Sparkles, UploadCloud, WandSparkles, X } from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import { createStudioProject, importStudioProject } from "@/lib/api"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { PageTransition } from "@/components/ui/page-transition"
import { useToast } from "@/components/ui/use-toast"

type Mode = "builder" | "import"

export default function NewStudioProjectPage() {
  const { token, isAuthenticated, isLoading } = useAuth()
  const router = useRouter()
  const { toast } = useToast()

  const [mode, setMode] = useState<Mode>("builder")
  const [title, setTitle] = useState("My Resume Studio")
  const [textImport, setTextImport] = useState("")
  const [fileImport, setFileImport] = useState<File | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [dragActive, setDragActive] = useState(false)
  const [fileError, setFileError] = useState<string | null>(null)
  const [importProgress, setImportProgress] = useState(0)

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login")
    }
  }, [isAuthenticated, isLoading, router])

  const canSubmit = useMemo(() => {
    if (!title.trim()) return false
    if (mode === "builder") return true
    return Boolean(textImport.trim()) || Boolean(fileImport)
  }, [fileImport, mode, textImport, title])

  function validateFile(candidate: File | null): string | null {
    if (!candidate) return null
    const allowedExt = [".pdf", ".docx", ".txt"]
    const lower = candidate.name.toLowerCase()
    const ext = lower.slice(lower.lastIndexOf("."))
    if (!allowedExt.includes(ext)) return "Please upload PDF, DOCX, or TXT only."
    if (candidate.size > 10 * 1024 * 1024) return "File exceeds 10MB limit."
    return null
  }

  function onFileSelected(candidate: File | null) {
    const validation = validateFile(candidate)
    setFileError(validation)
    if (validation) {
      setFileImport(null)
      return
    }
    setFileImport(candidate)
  }

  async function handleCreate() {
    if (!token || !canSubmit) return
    setSubmitting(true)
    setImportProgress(mode === "import" ? 8 : 0)
    let progressInterval: ReturnType<typeof setInterval> | null = null
    try {
      const project = await createStudioProject(token, {
        title: title.trim(),
        source_type: mode === "builder" ? "builder" : "import_text",
      })
      if (mode === "import") {
        progressInterval = setInterval(() => {
          setImportProgress((value) => (value >= 88 ? value : value + 8))
        }, 220)
        await importStudioProject(token, project.id, {
          text: textImport.trim() || undefined,
          file: fileImport,
        })
        clearInterval(progressInterval)
        progressInterval = null
        setImportProgress(100)
      }
      toast({
        title: "Resume Studio created",
        description: "Opening editor workspace.",
      })
      router.push(`/dashboard/studio/${project.id}`)
    } catch (error) {
      toast({
        title: "Unable to create project",
        description: (error as Error).message,
        variant: "destructive",
      })
    } finally {
      if (progressInterval) clearInterval(progressInterval)
      setSubmitting(false)
      setTimeout(() => setImportProgress(0), 800)
    }
  }

  if (isLoading || !isAuthenticated) return null

  return (
    <DashboardLayout
      title="New Resume Studio"
      description="Start from scratch or import an existing resume."
      actions={
        <Button variant="outline" size="sm" asChild>
          <Link href="/dashboard/studio">Back to Studio</Link>
        </Button>
      }
    >
      <PageTransition className="mx-auto w-full max-w-4xl space-y-6">
        <section className="grid gap-4 md:grid-cols-2">
          <button
            type="button"
            onClick={() => setMode("builder")}
            className={`surface-card space-y-3 p-5 text-left transition ${
              mode === "builder"
                ? "border-primary/40 shadow-[var(--shadow-md)]"
                : "hover:border-border"
            }`}
          >
            <WandSparkles className="h-5 w-5 text-primary" />
            <p className="text-base font-semibold text-foreground">Build from scratch</p>
            <p className="text-sm text-muted-foreground">
              Guided step-by-step resume builder with autosave and templates.
            </p>
          </button>
          <button
            type="button"
            onClick={() => setMode("import")}
            className={`surface-card space-y-3 p-5 text-left transition ${
              mode === "import"
                ? "border-primary/40 shadow-[var(--shadow-md)]"
                : "hover:border-border"
            }`}
          >
            <FileUp className="h-5 w-5 text-primary" />
            <p className="text-base font-semibold text-foreground">Improve existing resume</p>
            <p className="text-sm text-muted-foreground">
              Import PDF, DOCX, or paste raw text and convert into structured editing mode.
            </p>
          </button>
        </section>

        <section className="surface-card space-y-5 p-6">
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">Project title</label>
            <Input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Q1 Investor Demo Resume"
            />
          </div>

          {mode === "import" && (
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">Paste resume text</label>
                <textarea
                  value={textImport}
                  onChange={(event) => setTextImport(event.target.value)}
                  className="min-h-[220px] w-full rounded-xl border border-border bg-background px-3 py-2 text-sm outline-none ring-primary transition focus:ring-2"
                  placeholder="Paste resume content to parse into structured sections..."
                />
              </div>
              <div className="space-y-3">
                <label className="text-sm font-medium text-foreground">Or upload file</label>
                <div
                  role="button"
                  tabIndex={0}
                  onDragEnter={(event) => {
                    event.preventDefault()
                    setDragActive(true)
                  }}
                  onDragLeave={(event) => {
                    event.preventDefault()
                    setDragActive(false)
                  }}
                  onDragOver={(event) => {
                    event.preventDefault()
                    setDragActive(true)
                  }}
                  onDrop={(event) => {
                    event.preventDefault()
                    setDragActive(false)
                    const dropped = event.dataTransfer.files?.[0] ?? null
                    onFileSelected(dropped)
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault()
                      const input = document.getElementById("studio-file-input")
                      if (input) input.click()
                    }
                  }}
                  className={`flex min-h-[220px] cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed p-4 text-center transition ${
                    dragActive
                      ? "border-primary bg-primary-soft/40"
                      : "border-border bg-muted/30"
                  }`}
                  onClick={() => {
                    const input = document.getElementById("studio-file-input")
                    if (input) input.click()
                  }}
                >
                  <UploadCloud className="mb-2 h-5 w-5 text-muted-foreground" />
                  <p className="text-sm text-foreground">
                    {fileImport ? fileImport.name : "Drag & drop or click to upload"}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">PDF, DOCX, TXT · Max 10MB</p>
                  <input
                    id="studio-file-input"
                    type="file"
                    accept=".pdf,.docx,.txt"
                    className="hidden"
                    onChange={(event) => onFileSelected(event.target.files?.[0] ?? null)}
                  />
                </div>
                {fileError && (
                  <p className="rounded-lg bg-destructive/10 px-3 py-2 text-xs text-destructive">{fileError}</p>
                )}
                {fileImport && !fileError && (
                  <div className="flex items-center justify-between rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-700">
                    <span className="inline-flex items-center gap-1">
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      File ready for import
                    </span>
                    <button
                      type="button"
                      onClick={() => onFileSelected(null)}
                      className="inline-flex items-center gap-1 text-emerald-700 hover:text-emerald-900"
                    >
                      <X className="h-3.5 w-3.5" />
                      Clear
                    </button>
                  </div>
                )}
                <p className="text-xs text-muted-foreground">
                  Imported bullets stay evidence-grounded. Conditional edits are always labeled “Add only if true.”
                </p>
              </div>
            </div>
          )}

          {mode === "import" && submitting && importProgress > 0 && (
            <div className="space-y-2 rounded-xl border border-border/80 bg-muted/30 p-3">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>Importing and structuring resume...</span>
                <span>{Math.min(importProgress, 100)}%</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-primary transition-all duration-200"
                  style={{ width: `${Math.min(importProgress, 100)}%` }}
                />
              </div>
            </div>
          )}

          <div className="flex items-center justify-between rounded-xl border border-border/80 bg-muted/40 px-4 py-3">
            <p className="inline-flex items-center gap-2 text-sm text-muted-foreground">
              <Sparkles className="h-4 w-4" />
              Deterministic parsing first, optional reasoning second.
            </p>
            <Button onClick={handleCreate} disabled={!canSubmit || submitting}>
              {submitting ? "Creating..." : "Create Resume Studio"}
            </Button>
          </div>
          <p className="inline-flex items-start gap-2 rounded-xl border border-border/80 bg-background px-3 py-2 text-xs text-muted-foreground">
            <ShieldCheck className="mt-0.5 h-3.5 w-3.5 text-primary" />
            Privacy-first by default. Resume content is used only for analysis and export generation within your workspace.
          </p>
        </section>
      </PageTransition>
    </DashboardLayout>
  )
}

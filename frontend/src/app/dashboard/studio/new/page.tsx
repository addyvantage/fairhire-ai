"use client"

import Link from "next/link"
import { useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import { FileUp, FileText, Sparkles, WandSparkles } from "lucide-react"
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

  async function handleCreate() {
    if (!token || !canSubmit) return
    setSubmitting(true)
    try {
      const project = await createStudioProject(token, {
        title: title.trim(),
        source_type: mode === "builder" ? "builder" : "import_text",
      })
      if (mode === "import") {
        await importStudioProject(token, project.id, {
          text: textImport.trim() || undefined,
          file: fileImport,
        })
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
      setSubmitting(false)
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
                <label className="flex min-h-[220px] cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-border bg-muted/30 p-4 text-center">
                  <FileText className="mb-2 h-5 w-5 text-muted-foreground" />
                  <p className="text-sm text-foreground">
                    {fileImport ? fileImport.name : "Choose PDF, DOCX, or TXT"}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">Max 10MB</p>
                  <input
                    type="file"
                    accept=".pdf,.docx,.txt"
                    className="hidden"
                    onChange={(event) => setFileImport(event.target.files?.[0] ?? null)}
                  />
                </label>
                <p className="text-xs text-muted-foreground">
                  Import mode creates a base version and keeps your source grounded for strict truth rewrites.
                </p>
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
        </section>
      </PageTransition>
    </DashboardLayout>
  )
}

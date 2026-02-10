"use client"

import { useEffect } from "react"
import { ReactNode } from "react"
import { useRouter } from "next/navigation"
import { KeyRound, ShieldCheck, UserCircle2 } from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { Button } from "@/components/ui/button"
import { PageTransition } from "@/components/ui/page-transition"
import { SectionCard } from "@/components/ui/section-card"

export default function SettingsPage() {
  const { isAuthenticated, isLoading, logout } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login")
    }
  }, [isAuthenticated, isLoading, router])

  return (
    <DashboardLayout title="Settings" description="Workspace controls, security posture, and account actions.">
      <PageTransition className="mx-auto w-full max-w-4xl">
        <SectionCard title="Account" description="Manage identity and access details for this workspace.">
          <div className="grid gap-3 md:grid-cols-2">
            <SettingTile
              icon={<UserCircle2 className="h-4 w-4" />}
              title="Profile"
              description="Connected through secure email authentication."
            />
            <SettingTile
              icon={<KeyRound className="h-4 w-4" />}
              title="Password"
              description="Update credentials from the authentication provider."
            />
          </div>
        </SectionCard>

        <SectionCard title="Security" description="Bias-aware analysis and API access controls stay enabled by default.">
          <div className="rounded-xl border border-border/80 bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
            <p className="inline-flex items-center gap-2 font-medium text-foreground">
              <ShieldCheck className="h-4 w-4 text-emerald-600" />
              Workspace protection is active
            </p>
            <p className="mt-1">
              Token-based auth and role profile constraints are enforced across all analysis requests.
            </p>
          </div>
        </SectionCard>

        <SectionCard title="Session" description="Sign out of this browser session.">
          <div className="flex justify-end">
            <Button variant="outline" onClick={logout}>
              Sign out
            </Button>
          </div>
        </SectionCard>
      </PageTransition>
    </DashboardLayout>
  )
}

function SettingTile({
  icon,
  title,
  description,
}: {
  icon: ReactNode
  title: string
  description: string
}) {
  return (
    <div className="rounded-xl border border-border/80 bg-muted/30 px-4 py-3">
      <div className="mb-2 inline-flex h-8 w-8 items-center justify-center rounded-lg bg-background text-muted-foreground">
        {icon}
      </div>
      <p className="text-sm font-semibold text-foreground">{title}</p>
      <p className="mt-1 text-sm text-muted-foreground">{description}</p>
    </div>
  )
}

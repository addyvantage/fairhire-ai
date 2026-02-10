import { ReactNode } from "react"
import Link from "next/link"

export function AuthShell({
  title,
  subtitle,
  children,
  footerText,
  footerLinkLabel,
  footerLinkHref,
}: {
  title: string
  subtitle: string
  children: ReactNode
  footerText: string
  footerLinkLabel: string
  footerLinkHref: string
}) {
  return (
    <div className="flex min-h-screen bg-background">
      <div className="hidden flex-1 items-end justify-start bg-slate-950 p-10 text-white lg:flex">
        <div className="max-w-xl space-y-6">
          <p className="inline-flex rounded-full bg-white/10 px-3 py-1 text-xs font-medium uppercase tracking-[0.1em] text-slate-200">
            FairHire
          </p>
          <h2 className="text-4xl font-semibold tracking-tight text-balance">
            Modern, bias-aware resume intelligence for high-performing teams.
          </h2>
          <p className="text-base text-slate-300">
            Evaluate candidates with confidence using role-specific analysis and transparent scoring.
          </p>
        </div>
      </div>

      <div className="flex flex-1 items-center justify-center px-4 py-12 sm:px-8">
        <div className="w-full max-w-[420px] space-y-7">
          <Link href="/" className="inline-flex items-center gap-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-sm font-semibold text-primary-foreground">
              FH
            </div>
            <span className="text-sm font-semibold tracking-tight text-foreground">FairHire AI</span>
          </Link>
          <div>
            <h1 className="text-3xl font-semibold tracking-tight text-foreground">{title}</h1>
            <p className="mt-2 text-sm text-muted-foreground">{subtitle}</p>
          </div>
          <div className="surface-elevated p-6">{children}</div>
          <p className="text-center text-sm text-muted-foreground">
            {footerText}{" "}
            <Link href={footerLinkHref} className="font-medium text-foreground hover:text-primary">
              {footerLinkLabel}
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}

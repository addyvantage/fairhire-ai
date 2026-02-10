"use client"

import { FormEvent, useState } from "react"
import Link from "next/link"
import { Loader2 } from "lucide-react"
import { motion } from "framer-motion"
import { useAuth } from "@/lib/auth-context"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { useToast } from "@/components/ui/use-toast"

export default function LoginPage() {
  const { login } = useAuth()
  const { toast } = useToast()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError("")
    setLoading(true)
    try {
      await login(email, password)
    } catch (err) {
      const msg = (err as Error).message
      setError(msg)
      toast({ title: "Sign in failed", description: msg, variant: "destructive" })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/30 px-4">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
        className="w-full max-w-[360px] space-y-8"
      >
        <div className="text-center">
          <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-foreground text-background text-sm font-bold">
            F
          </div>
          <h1 className="text-lg font-semibold tracking-tight text-foreground">
            Sign in to FairHire
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Enter your credentials to continue
          </p>
        </div>

        <div className="rounded-xl border bg-background p-6 shadow-[var(--shadow-sm)]">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="email" className="text-xs">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="you@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password" className="text-xs">Password</Label>
              <Input
                id="password"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
              />
            </div>

            {error && (
              <p className="rounded-lg bg-destructive/5 px-3 py-2 text-sm text-destructive">
                {error}
              </p>
            )}

            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                  Signing in...
                </>
              ) : (
                "Sign in"
              )}
            </Button>
          </form>
        </div>

        <p className="text-center text-sm text-muted-foreground">
          Don&apos;t have an account?{" "}
          <Link
            href="/register"
            className="font-medium text-foreground underline-offset-4 hover:underline transition-colors"
          >
            Create one
          </Link>
        </p>
      </motion.div>
    </div>
  )
}

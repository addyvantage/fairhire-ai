import type { Metadata } from "next"
import "./globals.css"
import { AuthProvider } from "@/lib/auth-context"
import { ToastProvider } from "@/components/ui/use-toast"
import { Toaster } from "@/components/ui/toaster"

export const metadata: Metadata = {
  title: "FairHire-AI",
  description: "Resume Intelligence and Hiring Bias Analysis",
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>
          <ToastProvider>
            {children}
            <Toaster />
          </ToastProvider>
        </AuthProvider>
      </body>
    </html>
  )
}

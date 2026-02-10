import type { Metadata } from "next"
import "./globals.css"
import { AuthProvider } from "@/lib/auth-context"

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
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  )
}

import type { Metadata } from "next";
import "./styles.css";

export const metadata: Metadata = {
  title: "FairHire-AI",
  description: "Resume Intelligence and Hiring Bias Analysis",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

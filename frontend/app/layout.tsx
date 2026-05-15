import type { Metadata } from "next"

// globals.css (Tailwind base styles) will be added on Day 5

export const metadata: Metadata = {
  title: "revenue-recovery-kit",
  description: "Automated revenue recovery dashboard for service agencies.",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}

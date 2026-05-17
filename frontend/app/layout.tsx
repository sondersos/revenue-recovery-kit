import type { Metadata } from 'next'
import { Inter, Instrument_Serif } from 'next/font/google'
import { Toaster } from 'sonner'
import './globals.css'

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
})

const instrumentSerif = Instrument_Serif({
  subsets: ['latin'],
  weight: '400',
  variable: '--font-instrument-serif',
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'Revenue Recovery Kit',
  description: 'Automated revenue recovery for service agencies',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={`${inter.variable} ${instrumentSerif.variable}`}>
      <body className="bg-gray-50 text-gray-900 antialiased font-sans">
        {children}
        <Toaster richColors position="top-right" />
      </body>
    </html>
  )
}

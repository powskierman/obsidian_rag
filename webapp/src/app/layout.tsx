import type { Metadata } from 'next'
import './globals.css'
import { AppProvider } from '../context/AppContext'

export const metadata: Metadata = {
    title: 'Obsidian RAG',
    description: 'Deep Thinking for your Knowledge Base',
}

export default function RootLayout({
    children,
}: {
    children: React.ReactNode
}) {
    return (
        <html lang="en" suppressHydrationWarning>
            <body>
                <AppProvider>
                    {children}
                </AppProvider>
            </body>
        </html>
    )
}

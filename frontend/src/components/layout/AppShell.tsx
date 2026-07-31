import { type ReactNode } from 'react'

import { SHELL_CONTAINER } from '@/components/layout/container'
import { TopBar } from '@/components/layout/TopBar'
import { cn } from '@/lib/utils'

export interface AppShellProps {
  children: ReactNode
  /** `wide` fills the viewport (tables); `narrow` keeps forms readable. */
  width?: 'wide' | 'narrow'
  className?: string
}

export function AppShell({ children, width = 'wide', className }: AppShellProps) {
  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      <TopBar />
      <main
        className={cn(
          SHELL_CONTAINER,
          'flex-1 py-4 sm:py-5',
          width === 'narrow' && 'max-w-4xl',
          className
        )}
      >
        {children}
      </main>
    </div>
  )
}

import { type ReactNode } from 'react'
import { cn } from '@/lib/utils'

export interface SectionProps {
  title: string
  description?: string
  action?: ReactNode
  children: ReactNode
  className?: string
}

export function Section({ title, description, action, children, className }: SectionProps) {
  return (
    <section
      className={cn('border-b border-slate-100 py-5 first:pt-0 last:border-0 last:pb-0', className)}
    >
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">{title}</h2>
          {description && <p className="mt-1 text-sm text-slate-500">{description}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  )
}

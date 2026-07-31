import { Link } from '@tanstack/react-router'
import { ArrowLeft } from 'lucide-react'
import { type ReactNode } from 'react'
import { cn } from '@/lib/utils'

export interface PageHeaderProps {
  title: string
  description?: string
  backTo?: string
  backLabel?: string
  action?: ReactNode
  className?: string
}

export function PageHeader({
  title,
  description,
  backTo,
  backLabel = 'Quay lại danh sách',
  action,
  className,
}: PageHeaderProps) {
  return (
    <div className={cn('mb-5 flex flex-wrap items-start gap-3 sm:mb-6', className)}>
      {backTo && (
        <Link
          to={backTo}
          aria-label={backLabel}
          title={backLabel}
          className="mt-0.5 inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-slate-300 bg-white text-slate-600 shadow-sm transition-colors hover:bg-slate-50 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 focus-visible:ring-offset-2"
        >
          <ArrowLeft className="h-4 w-4" />
        </Link>
      )}

      <div className="min-w-0 flex-1">
        <h1 className="truncate text-lg font-semibold text-slate-900 sm:text-xl">{title}</h1>
        {description && <p className="mt-0.5 text-sm text-slate-500">{description}</p>}
      </div>

      {action && <div className="flex shrink-0 items-center gap-2">{action}</div>}
    </div>
  )
}

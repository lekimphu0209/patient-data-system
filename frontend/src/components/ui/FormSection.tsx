import { type ReactNode } from 'react'
import { cn } from '@/lib/utils'

export interface FormSectionProps {
  title: string
  description?: string
  icon?: ReactNode
  children: ReactNode
  className?: string
}

export function FormSection({
  title,
  description,
  icon,
  children,
  className,
}: FormSectionProps) {
  return (
    <section className={cn('border-b border-slate-100 py-5 first:pt-0 last:border-0', className)}>
      <div className="mb-4 flex items-center gap-2.5">
        {icon && (
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-700">
            {icon}
          </span>
        )}
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
          {description && <p className="text-xs text-slate-500">{description}</p>}
        </div>
      </div>
      {children}
    </section>
  )
}

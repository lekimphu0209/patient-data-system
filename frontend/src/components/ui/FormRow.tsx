import { type ReactNode } from 'react'
import { cn } from '@/lib/utils'

export interface FormRowProps {
  label: string
  htmlFor?: string
  required?: boolean
  children: ReactNode
  error?: string
  className?: string
}

export function FormRow({ label, htmlFor, required, children, error, className }: FormRowProps) {
  return (
    <div
      className={cn(
        'grid grid-cols-1 items-start gap-2 md:grid-cols-[minmax(160px,auto)_1fr] md:gap-4',
        className
      )}
    >
      <label htmlFor={htmlFor} className="text-sm text-slate-500 md:pt-2.5">
        {label}
        {required && <span className="ml-0.5 text-red-500">*</span>}
      </label>
      <div className="min-w-0">
        {children}
        {error && <p className="mt-1.5 text-xs font-medium text-red-600">{error}</p>}
      </div>
    </div>
  )
}

import { type ReactNode } from 'react'
import { cn } from '@/lib/utils'

export interface FormFieldProps {
  label: string
  htmlFor?: string
  required?: boolean
  hint?: string
  children: ReactNode
  error?: string
  className?: string
}

export function FormField({
  label,
  htmlFor,
  required,
  hint,
  children,
  error,
  className,
}: FormFieldProps) {
  return (
    <div className={cn('w-full', className)}>
      <label htmlFor={htmlFor} className="mb-1.5 block text-sm font-medium text-slate-700">
        {label}
        {required && <span className="ml-0.5 text-red-500">*</span>}
      </label>
      {children}
      {hint && !error && <p className="mt-1.5 text-xs text-slate-500">{hint}</p>}
      {error && <p className="mt-1.5 text-xs font-medium text-red-600">{error}</p>}
    </div>
  )
}

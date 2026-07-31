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
    <div className={cn('grid grid-cols-1 md:grid-cols-[minmax(140px,auto)_1fr] gap-4 items-start', className)}>
      <label htmlFor={htmlFor} className="text-sm text-gray-500 pt-2">
        {label}
        {required && <span className="text-red-500 ml-0.5">*</span>}
      </label>
      <div>
        {children}
        {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
      </div>
    </div>
  )
}

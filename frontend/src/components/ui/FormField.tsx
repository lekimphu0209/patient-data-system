import { type ReactNode } from 'react'
import { cn } from '@/lib/utils'

export interface FormFieldProps {
  label: string
  htmlFor?: string
  required?: boolean
  children: ReactNode
  error?: string
  className?: string
}

export function FormField({ label, htmlFor, required, children, error, className }: FormFieldProps) {
  return (
    <div className={cn('w-full', className)}>
      <label htmlFor={htmlFor} className="block text-sm font-medium text-gray-700 mb-1">
        {label}
        {required && <span className="text-red-500 ml-0.5">*</span>}
      </label>
      {children}
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  )
}

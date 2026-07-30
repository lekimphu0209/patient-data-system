import { type ReactNode } from 'react'
import { cn } from '@/lib/utils'

export interface FormSectionProps {
  title: string
  children: ReactNode
  className?: string
}

export function FormSection({ title, children, className }: FormSectionProps) {
  return (
    <section className={cn('py-6 first:pt-0 border-b border-gray-100 last:border-0', className)}>
      <h3 className="text-sm font-semibold text-gray-900 mb-3">{title}</h3>
      {children}
    </section>
  )
}

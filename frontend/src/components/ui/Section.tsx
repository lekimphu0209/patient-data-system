import { type ReactNode } from 'react'
import { cn } from '@/lib/utils'

export interface SectionProps {
  title: string
  children: ReactNode
  className?: string
}

export function Section({ title, children, className }: SectionProps) {
  return (
    <section className={cn('py-6 first:pt-0 last:pb-0 border-b border-gray-100 last:border-0', className)}>
      <h2 className="text-base font-semibold text-gray-900 mb-4">{title}</h2>
      {children}
    </section>
  )
}

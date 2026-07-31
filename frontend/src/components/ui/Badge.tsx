import { type ReactNode } from 'react'
import { cn } from '@/lib/utils'

export interface BadgeProps {
  children: ReactNode
  variant?: 'brand' | 'success' | 'warning' | 'danger' | 'info' | 'violet' | 'gray'
  className?: string
}

// Tinted background + matching ring keeps chips legible without shouting.
const variants = {
  brand: 'bg-brand-50 text-brand-800 ring-brand-200',
  success: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  warning: 'bg-amber-50 text-amber-700 ring-amber-200',
  danger: 'bg-red-50 text-red-700 ring-red-200',
  info: 'bg-sky-50 text-sky-700 ring-sky-200',
  violet: 'bg-violet-50 text-violet-700 ring-violet-200',
  gray: 'bg-slate-100 text-slate-600 ring-slate-200',
}

export function Badge({ children, variant = 'gray', className }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset',
        variants[variant],
        className
      )}
    >
      {children}
    </span>
  )
}

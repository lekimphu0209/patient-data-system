import { type ReactNode } from 'react'
import { cn } from '@/lib/utils'

export interface CardProps {
  children: ReactNode
  className?: string
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'full'
  padding?: 'none' | 'sm' | 'md'
}

const sizes = {
  xs: 'max-w-md',
  sm: 'max-w-2xl',
  md: 'max-w-3xl',
  lg: 'max-w-5xl',
  full: 'max-w-none',
}

const paddings = {
  none: '',
  sm: 'p-4 sm:p-5',
  md: 'p-5 sm:p-6',
}

export function Card({ children, className, size = 'md', padding = 'md' }: CardProps) {
  return (
    <div
      className={cn(
        'mx-auto rounded-xl border border-slate-200 bg-white shadow-card',
        sizes[size],
        paddings[padding],
        className
      )}
    >
      {children}
    </div>
  )
}

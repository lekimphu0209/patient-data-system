import { type ReactNode } from 'react'
import { cn } from '@/lib/utils'

export interface BadgeProps {
  children: ReactNode
  variant?: 'primary' | 'success' | 'warning' | 'danger' | 'gray'
}

const variants = {
  primary: 'bg-blue-100 text-blue-700',
  success: 'bg-green-100 text-green-700',
  warning: 'bg-yellow-100 text-yellow-700',
  danger: 'bg-red-100 text-red-700',
  gray: 'bg-gray-100 text-gray-600',
}

export function Badge({ children, variant = 'gray' }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center whitespace-nowrap px-2.5 py-0.5 rounded-full text-xs font-medium',
        variants[variant]
      )}
    >
      {children}
    </span>
  )
}

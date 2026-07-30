import { Link } from '@tanstack/react-router'
import { type ReactNode } from 'react'
import { cn } from '@/lib/utils'

export interface PageHeaderProps {
  title: string
  backTo?: string
  backLabel?: string
  action?: ReactNode
}

export function PageHeader({ title, backTo, backLabel = 'Quay lại danh sách', action }: PageHeaderProps) {
  return (
    <div className="mb-6 sm:mb-8">
      {backTo && (
        <Link
          to={backTo}
          className="inline-flex items-center gap-1.5 text-sm font-medium text-gray-600 hover:text-blue-600"
        >
          <span aria-hidden="true">←</span>
          {backLabel}
        </Link>
      )}
      <div className={cn('flex items-center gap-3', backTo && 'mt-4', action ? 'justify-between' : 'justify-center')}> 
        <h1 className="text-center text-xl sm:text-2xl font-bold text-gray-900 truncate">
          {title}
        </h1>
        {action}
      </div>
    </div>
  )
}

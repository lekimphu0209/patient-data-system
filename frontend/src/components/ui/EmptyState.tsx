import { Inbox } from 'lucide-react'
import { type ReactNode } from 'react'

export interface EmptyStateProps {
  message?: string
  description?: string
  icon?: ReactNode
  action?: ReactNode
}

export function EmptyState({
  message = 'Không có dữ liệu',
  description,
  icon,
  action,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
      <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-400">
        {icon ?? <Inbox className="h-6 w-6" />}
      </span>
      <p className="text-sm font-medium text-slate-700">{message}</p>
      {description && <p className="mt-1 max-w-sm text-sm text-slate-500">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

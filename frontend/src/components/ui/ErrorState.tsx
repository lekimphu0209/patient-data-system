import { AlertCircle } from 'lucide-react'
import { type ReactNode } from 'react'

export interface ErrorStateProps {
  message: string
  action?: ReactNode
}

export function ErrorState({ message, action }: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
      <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-red-50 text-red-600">
        <AlertCircle className="h-6 w-6" />
      </span>
      <p className="text-sm font-medium text-slate-700">{message}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

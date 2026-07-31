import { CheckCircle2, X, XCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface ToastProps {
  message: string
  type: 'success' | 'error'
  onClose?: () => void
}

export function Toast({ message, type, onClose }: ToastProps) {
  const isSuccess = type === 'success'
  const Icon = isSuccess ? CheckCircle2 : XCircle

  return (
    <div
      role="status"
      className={cn(
        'fixed bottom-6 right-6 z-[60] flex max-w-md items-start gap-3 rounded-xl border px-4 py-3 shadow-popover animate-slide-up',
        isSuccess ? 'border-emerald-200 bg-white' : 'border-red-200 bg-white'
      )}
    >
      <Icon
        className={cn('mt-0.5 h-5 w-5 shrink-0', isSuccess ? 'text-emerald-600' : 'text-red-600')}
      />
      <p className="min-w-0 flex-1 text-sm font-medium text-slate-800">{message}</p>
      {onClose && (
        <button
          onClick={onClose}
          className="-mr-1 shrink-0 rounded-md p-0.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
          aria-label="Đóng"
        >
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  )
}

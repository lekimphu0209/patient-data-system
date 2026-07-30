import { cn } from '@/lib/utils'

export interface ToastProps {
  message: string
  type: 'success' | 'error'
  onClose?: () => void
}

export function Toast({ message, type, onClose }: ToastProps) {
  return (
    <div
      className={cn(
        'fixed bottom-6 right-6 z-50 px-4 py-3 rounded-lg shadow-lg text-sm font-medium',
        type === 'success' ? 'bg-green-600 text-white' : 'bg-red-600 text-white'
      )}
    >
      {message}
      {onClose && (
        <button
          onClick={onClose}
          className="ml-3 text-white/80 hover:text-white"
          aria-label="Đóng"
        >
          ×
        </button>
      )}
    </div>
  )
}

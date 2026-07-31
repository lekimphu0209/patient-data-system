import { cn } from '@/lib/utils'

export interface LoadingProps {
  text?: string
  size?: 'sm' | 'md'
  className?: string
}

export function Loading({ text = 'Đang tải...', size = 'md', className }: LoadingProps) {
  return (
    <div className={cn('flex items-center justify-center gap-2.5 py-12 text-slate-500', className)}>
      <span
        className={cn(
          'inline-block animate-spin rounded-full border-2 border-brand-600 border-t-transparent',
          size === 'sm' ? 'h-4 w-4' : 'h-5 w-5'
        )}
      />
      <span className={cn('font-medium', size === 'sm' ? 'text-sm' : 'text-[15px]')}>{text}</span>
    </div>
  )
}

import { type TextareaHTMLAttributes, forwardRef } from 'react'
import { cn } from '@/lib/utils'

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  error?: string
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, error, ...props }, ref) => {
    return (
      <div className="w-full">
        <textarea
          ref={ref}
          className={cn(
            'w-full resize-y rounded-lg border bg-white px-3 py-2.5 text-sm text-slate-900 transition-colors',
            'placeholder:text-slate-400',
            'focus:outline-none focus:ring-2 focus:ring-offset-0',
            'disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-500',
            error
              ? 'border-red-400 bg-red-50/40 focus:border-red-500 focus:ring-red-500/30'
              : 'border-slate-300 hover:border-slate-400 focus:border-brand-600 focus:ring-brand-600/25',
            className
          )}
          {...props}
        />
        {error && <p className="mt-1.5 text-xs font-medium text-red-600">{error}</p>}
      </div>
    )
  }
)

Textarea.displayName = 'Textarea'

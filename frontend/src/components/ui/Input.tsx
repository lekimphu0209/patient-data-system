import { type InputHTMLAttributes, forwardRef } from 'react'
import { cn } from '@/lib/utils'

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  error?: string
  inputSize?: 'md' | 'lg'
  leftIcon?: React.ReactNode
  rightSlot?: React.ReactNode
}

const inputSizes = {
  md: 'h-10 text-sm',
  lg: 'h-11 text-[15px]',
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, error, inputSize = 'md', leftIcon, rightSlot, ...props }, ref) => {
    return (
      <div className="w-full">
        <div className="relative">
          {leftIcon && (
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">
              {leftIcon}
            </span>
          )}
          <input
            ref={ref}
            className={cn(
              'w-full rounded-lg border bg-white px-3 text-slate-900 transition-colors',
              'placeholder:text-slate-400',
              'focus:outline-none focus:ring-2 focus:ring-offset-0',
              'disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-500',
              'read-only:bg-slate-50 read-only:text-slate-600',
              error
                ? 'border-red-400 bg-red-50/40 focus:border-red-500 focus:ring-red-500/30'
                : 'border-slate-300 hover:border-slate-400 focus:border-brand-600 focus:ring-brand-600/25',
              inputSizes[inputSize],
              leftIcon && 'pl-9',
              rightSlot && 'pr-9',
              className
            )}
            {...props}
          />
          {rightSlot && (
            <span className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400">
              {rightSlot}
            </span>
          )}
        </div>
        {error && <p className="mt-1.5 text-xs font-medium text-red-600">{error}</p>}
      </div>
    )
  }
)

Input.displayName = 'Input'

import { type InputHTMLAttributes, forwardRef } from 'react'
import { cn } from '@/lib/utils'

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  error?: string
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, error, ...props }, ref) => {
    return (
      <div className="w-full">
        <input
          ref={ref}
          className={cn(
            'w-full border rounded-lg px-3 text-sm transition focus:outline-none focus:ring-2 disabled:bg-gray-100 disabled:text-gray-500',
            error
              ? 'border-red-500 focus:ring-red-500 bg-red-50'
              : 'border-gray-300 focus:ring-gray-400 focus:border-gray-400 bg-white',
            props.type === 'date' ? 'h-10 pr-10' : 'h-10',
            className
          )}
          {...props}
        />
        {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
      </div>
    )
  }
)

Input.displayName = 'Input'

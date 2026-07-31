import { type SelectHTMLAttributes, forwardRef } from 'react'
import { ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface SelectOption {
  value: string
  label: string
}

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  options: SelectOption[]
  error?: string
  selectSize?: 'sm' | 'md' | 'lg'
}

const selectSizes = {
  sm: 'h-9 text-[13px]',
  md: 'h-10 text-sm',
  lg: 'h-11 text-[15px]',
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, options, error, children, selectSize = 'md', ...props }, ref) => {
    return (
      <div className="relative w-full">
        <select
          ref={ref}
          className={cn(
            'w-full appearance-none rounded-lg border bg-white px-3 pr-9 text-slate-900 transition-colors',
            'focus:outline-none focus:ring-2 focus:ring-offset-0',
            'disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-500',
            error
              ? 'border-red-400 bg-red-50/40 focus:border-red-500 focus:ring-red-500/30'
              : 'border-slate-300 hover:border-slate-400 focus:border-brand-600 focus:ring-brand-600/25',
            selectSizes[selectSize],
            className
          )}
          {...props}
        >
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
          {children}
        </select>
        <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        {error && <p className="mt-1.5 text-xs font-medium text-red-600">{error}</p>}
      </div>
    )
  }
)

Select.displayName = 'Select'

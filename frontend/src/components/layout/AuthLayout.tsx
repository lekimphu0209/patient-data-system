import { type ReactNode } from 'react'

export interface AuthLayoutProps {
  title: string
  subtitle: string
  children: ReactNode
  footer?: ReactNode
}

export function AuthLayout({ title, subtitle, children, footer }: AuthLayoutProps) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-white px-4 py-10 sm:py-14">
      <div className="w-full max-w-lg">
        <div className="mb-8">
          <h2 className="text-2xl font-semibold text-slate-900 sm:text-[28px]">{title}</h2>
          <p className="mt-1 text-sm text-slate-500">{subtitle}</p>
        </div>
        {children}

        {footer && <div className="mt-6 text-center text-sm text-slate-600">{footer}</div>}
      </div>
    </div>
  )
}

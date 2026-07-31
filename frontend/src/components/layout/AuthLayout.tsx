import { Stethoscope } from 'lucide-react'
import { type ReactNode } from 'react'

export interface AuthLayoutProps {
  title: string
  subtitle: string
  children: ReactNode
  footer?: ReactNode
}

export function AuthLayout({ title, subtitle, children, footer }: AuthLayoutProps) {
  return (
    <div className="flex min-h-screen flex-col bg-slate-100">
      {/* Subtle brand band so the card has something to sit against. */}
      <div className="pointer-events-none absolute inset-x-0 top-0 h-64 bg-gradient-to-b from-brand-800 to-brand-700" />

      <div className="relative flex flex-1 items-center justify-center px-4 py-10 sm:py-14">
        <div className="w-full max-w-lg">
          <div className="mb-7 flex flex-col items-center text-center">
            <span className="mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-white/15 text-white ring-1 ring-white/25">
              <Stethoscope className="h-7 w-7" />
            </span>
            <h1 className="text-xl font-semibold text-white sm:text-2xl">Hồ sơ bệnh nhân</h1>
            <p className="mt-1 text-sm text-brand-100">Hệ thống quản lý dữ liệu y tế</p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-popover sm:p-8">
            <div className="mb-6">
              <h2 className="text-xl font-semibold text-slate-900 sm:text-[22px]">{title}</h2>
              <p className="mt-1 text-sm text-slate-500">{subtitle}</p>
            </div>
            {children}
          </div>

          {footer && <div className="mt-5 text-center text-sm text-slate-600">{footer}</div>}
        </div>
      </div>
    </div>
  )
}

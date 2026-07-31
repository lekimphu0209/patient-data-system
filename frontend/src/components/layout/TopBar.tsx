import { Link, useNavigate } from '@tanstack/react-router'
import { ChevronRight, LogOut, Stethoscope } from 'lucide-react'

import { useAuth } from '@/app/auth-context'
import { SHELL_CONTAINER } from '@/components/layout/container'
import { roleLabel } from '@/constants'
import { cn, initialsOf } from '@/lib/utils'

export function TopBar() {
  const navigate = useNavigate()
  const { user, logout } = useAuth()

  const handleLogout = () => {
    logout()
    navigate({ to: '/login' })
  }

  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className={cn(SHELL_CONTAINER, 'flex h-14 items-center justify-between gap-3')}>
        <Link
          to="/patients"
          search={{ page: 1, limit: 10, q: '', diagnosis: '' }}
          className="flex min-w-0 items-center gap-2.5"
        >
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-700 text-white">
            <Stethoscope className="h-5 w-5" />
          </span>
          <span className="flex min-w-0 flex-col leading-tight">
            <span className="truncate text-[15px] font-semibold text-slate-900">
              Hồ sơ bệnh nhân
            </span>
            <span className="hidden truncate text-[11px] text-slate-500 sm:block">
              Hệ thống quản lý dữ liệu y tế
            </span>
          </span>
        </Link>

        <div className="flex shrink-0 items-center gap-1.5">
          <button
            type="button"
            onClick={() => navigate({ to: '/profile' })}
            title="Xem trang tài khoản"
            className="group flex items-center gap-2.5 rounded-lg border border-transparent py-1.5 pl-1.5 pr-2 transition-colors hover:border-slate-200 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 focus-visible:ring-offset-2"
          >
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-100 text-[13px] font-semibold text-brand-800">
              {initialsOf(user?.full_name)}
            </span>
            <span className="hidden min-w-0 flex-col items-start leading-tight sm:flex">
              <span className="max-w-[11rem] truncate text-[13px] font-semibold text-slate-900">
                {user?.full_name || 'Người dùng'}
              </span>
              <span className="text-[11px] text-slate-500">{roleLabel(user?.role)}</span>
            </span>
            <ChevronRight className="hidden h-4 w-4 text-slate-400 transition-colors group-hover:text-slate-600 sm:block" />
          </button>

          <span className="mx-1 hidden h-6 w-px bg-slate-200 sm:block" />

          <button
            type="button"
            onClick={handleLogout}
            title="Đăng xuất"
            className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-2 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 focus-visible:ring-offset-2"
          >
            <LogOut className="h-4 w-4" />
            <span className="hidden sm:inline">Đăng xuất</span>
          </button>
        </div>
      </div>
    </header>
  )
}

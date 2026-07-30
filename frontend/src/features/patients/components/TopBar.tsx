import { useNavigate } from '@tanstack/react-router'

import { LockIcon, LogoutIcon } from './icons'

interface TopBarProps {
  user: { full_name: string; role: string } | null
  onLogout: () => void
}

export function TopBar({ user, onLogout }: TopBarProps) {
  const navigate = useNavigate()

  return (
    <header className="bg-white border-b border-gray-200 sticky top-0 z-30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center gap-2">
            <span className="text-teal-700 font-bold text-lg">Hồ sơ bệnh nhân</span>
          </div>

          <div className="flex items-center gap-3 sm:gap-4">
            <div className="hidden sm:flex flex-col items-end leading-tight">
              <span className="text-sm font-semibold text-gray-900">
                {user?.full_name || 'Người dùng'}
              </span>
              <span className="text-xs text-gray-500 capitalize">{user?.role || ''}</span>
            </div>
            <button
              onClick={() => navigate({ to: '/profile' })}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50 text-sm font-medium transition"
              title="Quản lý mật khẩu"
            >
              <LockIcon className="w-4 h-4" />
              <span className="hidden sm:inline">Mật khẩu</span>
            </button>
            <button
              onClick={onLogout}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50 text-sm font-medium transition"
            >
              <LogoutIcon className="w-4 h-4" />
              <span className="hidden sm:inline">Đăng xuất</span>
            </button>
          </div>
        </div>
      </div>
    </header>
  )
}

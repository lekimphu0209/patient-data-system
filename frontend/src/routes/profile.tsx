import { createRoute } from '@tanstack/react-router'
import { CheckCircle2, Eye, EyeOff, KeyRound, Mail, ShieldCheck, UserCog } from 'lucide-react'
import { useState } from 'react'

import { useAuth } from '@/app/auth-context'
import { AppShell } from '@/components/layout/AppShell'
import {
  Badge,
  Button,
  Card,
  FormField,
  Input,
  Loading,
  PageHeader,
  Toast,
} from '@/components/ui'
import { roleLabel, VALIDATION_MESSAGES } from '@/constants'
import { changePassword, updateProfile, type AuthUser } from '@/features/auth/api'
import { useToast } from '@/hooks/useToast'
import { errorMessage, formatDateTime, initialsOf } from '@/lib/utils'
import { requireAuth } from '@/lib/auth-guard'
import { rootRoute } from '@/routes/__root'

export const profileRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/profile',
  component: ProfilePage,
  beforeLoad: requireAuth,
})

function ProfilePage() {
  const { user, setUser } = useAuth()
  const { toast, showToast, clearToast } = useToast()

  if (!user) {
    return (
      <AppShell width="narrow">
        <Loading text="Đang tải thông tin tài khoản..." />
      </AppShell>
    )
  }

  return (
    <AppShell width="narrow">
      <PageHeader
        title="Tài khoản của tôi"
        description="Xem thông tin đăng nhập và đổi mật khẩu."
        backTo="/patients"
      />

      <div className="space-y-4">
        <IdentityCard user={user} />
        <ProfileForm
          key={user.full_name}
          initialName={user.full_name}
          email={user.email}
          onSaved={(updated) => {
            setUser(updated)
            showToast('Đã cập nhật thông tin tài khoản')
          }}
          onError={(message) => showToast(message, 'error')}
        />
        <PasswordForm
          onSaved={(message) => showToast(message)}
          onError={(message) => showToast(message, 'error')}
        />
      </div>

      {toast && <Toast message={toast.message} type={toast.type} onClose={clearToast} />}
    </AppShell>
  )
}

function IdentityCard({ user }: { user: AuthUser }) {
  return (
    <Card size="full">
      <div className="flex flex-wrap items-center gap-4">
        <span className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-brand-100 text-xl font-semibold text-brand-800">
          {initialsOf(user.full_name)}
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-lg font-semibold text-slate-900">{user.full_name}</h2>
          <p className="mt-0.5 flex items-center gap-1.5 truncate text-sm text-slate-500">
            <Mail className="h-3.5 w-3.5 shrink-0" />
            {user.email}
          </p>
          <div className="mt-2.5 flex flex-wrap items-center gap-2">
            <Badge variant="brand">
              <ShieldCheck className="h-3.5 w-3.5" />
              {roleLabel(user.role)}
            </Badge>
            <Badge variant={user.is_active ? 'success' : 'gray'}>
              {user.is_active ? 'Đang hoạt động' : 'Ngừng hoạt động'}
            </Badge>
          </div>
        </div>
      </div>

      <dl className="mt-5 grid grid-cols-1 gap-x-6 gap-y-3 border-t border-slate-100 pt-5 sm:grid-cols-2">
        <InfoRow label="Mã tài khoản" value={`#${user.id}`} />
        <InfoRow label="Email đăng nhập" value={user.email} />
        <InfoRow label="Vai trò" value={roleLabel(user.role)} />
        <InfoRow label="Ngày tạo" value={formatDateTime(user.created_at)} />
      </dl>
    </Card>
  )
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 sm:block">
      <dt className="text-xs uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-0.5 truncate text-sm font-medium text-slate-900">{value}</dd>
    </div>
  )
}

function ProfileForm({
  initialName,
  email,
  onSaved,
  onError,
}: {
  initialName: string
  email: string
  onSaved: (user: AuthUser) => void
  onError: (message: string) => void
}) {
  const [fullName, setFullName] = useState(initialName)
  const [loading, setLoading] = useState(false)

  const dirty = fullName.trim() !== initialName && fullName.trim().length > 0

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!dirty) return
    setLoading(true)
    try {
      onSaved(await updateProfile({ full_name: fullName.trim() }))
    } catch (err) {
      onError(errorMessage(err, 'Cập nhật thông tin thất bại.'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card size="full">
      <SectionTitle
        icon={<UserCog className="h-4 w-4" />}
        title="Thông tin cá nhân"
        description="Tên hiển thị trên thanh điều hướng và trong file xuất dữ liệu."
      />

      <form onSubmit={handleSubmit} className="mt-4 space-y-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <FormField label="Họ và tên" htmlFor="profile_name" required>
            <Input
              id="profile_name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Nhập họ và tên"
              required
            />
          </FormField>

          <FormField
            label="Email đăng nhập"
            htmlFor="profile_email"
            hint="Email là định danh đăng nhập nên không thể tự thay đổi."
          >
            <Input id="profile_email" value={email} readOnly disabled />
          </FormField>
        </div>

        <div className="flex justify-end">
          <Button type="submit" isLoading={loading} disabled={!dirty}>
            Lưu thay đổi
          </Button>
        </div>
      </form>
    </Card>
  )
}

function PasswordForm({
  onSaved,
  onError,
}: {
  onSaved: (message: string) => void
  onError: (message: string) => void
}) {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [show, setShow] = useState(false)
  const [loading, setLoading] = useState(false)
  const [fieldError, setFieldError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setFieldError(null)

    if (next.length < 6) {
      setFieldError(VALIDATION_MESSAGES.passwordTooShort)
      return
    }
    if (next !== confirm) {
      setFieldError(VALIDATION_MESSAGES.passwordMismatch)
      return
    }

    setLoading(true)
    try {
      await changePassword({
        current_password: current,
        new_password: next,
        confirm_password: confirm,
      })
      setCurrent('')
      setNext('')
      setConfirm('')
      onSaved('Đổi mật khẩu thành công')
    } catch (err) {
      onError(errorMessage(err, 'Đổi mật khẩu thất bại.'))
    } finally {
      setLoading(false)
    }
  }

  const toggle = (
    <button
      type="button"
      onClick={() => setShow((v) => !v)}
      aria-label={show ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
      className="pointer-events-auto rounded p-1 transition-colors hover:text-slate-600"
    >
      {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
    </button>
  )

  return (
    <Card size="full">
      <SectionTitle
        icon={<KeyRound className="h-4 w-4" />}
        title="Đổi mật khẩu"
        description="Mật khẩu mới cần tối thiểu 6 ký tự."
      />

      <form onSubmit={handleSubmit} className="mt-4 space-y-4" autoComplete="off">
        <FormField label="Mật khẩu hiện tại" htmlFor="current_password" required>
          <Input
            id="current_password"
            type={show ? 'text' : 'password'}
            autoComplete="current-password"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
            rightSlot={toggle}
            required
          />
        </FormField>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <FormField label="Mật khẩu mới" htmlFor="new_password" required>
            <Input
              id="new_password"
              type={show ? 'text' : 'password'}
              autoComplete="new-password"
              value={next}
              onChange={(e) => setNext(e.target.value)}
              minLength={6}
              required
            />
          </FormField>

          <FormField
            label="Xác nhận mật khẩu mới"
            htmlFor="confirm_password"
            required
            error={fieldError ?? undefined}
          >
            <Input
              id="confirm_password"
              type={show ? 'text' : 'password'}
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
            />
          </FormField>
        </div>

        <div className="flex justify-end">
          <Button
            type="submit"
            isLoading={loading}
            disabled={!current || !next || !confirm}
            leftIcon={<CheckCircle2 className="h-4 w-4" />}
          >
            Đổi mật khẩu
          </Button>
        </div>
      </form>
    </Card>
  )
}

function SectionTitle({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode
  title: string
  description: string
}) {
  return (
    <div className="flex items-start gap-3">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-700">
        {icon}
      </span>
      <div className="min-w-0">
        <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
        <p className="mt-0.5 text-sm text-slate-500">{description}</p>
      </div>
    </div>
  )
}

import { createRoute } from '@tanstack/react-router'
import { useState } from 'react'

import { useAuth } from '@/app/auth-context'
import { Button, Card, FormRow, Input, PageHeader, Section, SectionHeader } from '@/components/ui'
import { VALIDATION_MESSAGES } from '@/constants'
import { changePassword } from '@/features/auth/api'
import { rootRoute } from '@/routes/__root'
import { requireAuth } from '@/lib/auth-guard'

export const profileRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/profile',
  component: ProfilePage,
  beforeLoad: requireAuth,
})

function ProfilePage() {
  const { user } = useAuth()
  const [current, setCurrent] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setMessage(null)

    if (newPassword !== confirm) {
      setError(VALIDATION_MESSAGES.passwordMismatch)
      return
    }

    setLoading(true)
    try {
      const res = await changePassword({
        current_password: current,
        new_password: newPassword,
        confirm_password: confirm,
      })
      setMessage(res.message || 'Đổi mật khẩu thành công')
      setCurrent('')
      setNewPassword('')
      setConfirm('')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Đổi mật khẩu thất bại')
    } finally {
      setLoading(false)
    }
  }

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center text-gray-500">
        Đang tải...
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 p-4 sm:p-6">
      <Card size="sm">
        <PageHeader title="Quản lý mật khẩu" backTo="/patients" />

        <Section title="Thông tin tài khoản">
          <FormRow label="Gmail">
            <span className="text-sm font-medium text-gray-900 break-words pt-2">
              {user.email}
            </span>
          </FormRow>
        </Section>

        <form onSubmit={handleSubmit} className="py-6 space-y-4">
          <SectionHeader title="Đổi mật khẩu" />

          <FormRow label="Mật khẩu hiện tại" htmlFor="current">
            <Input
              id="current"
              type="password"
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
              required
            />
          </FormRow>

          <FormRow label="Mật khẩu mới" htmlFor="new">
            <Input
              id="new"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
            />
          </FormRow>

          <FormRow label="Xác nhận mật khẩu mới" htmlFor="confirm">
            <Input
              id="confirm"
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
            />
          </FormRow>

          {error && <p className="text-sm text-red-600">{error}</p>}
          {message && <p className="text-sm text-green-600">{message}</p>}

          <div className="pt-2 flex justify-end">
            <Button type="submit" isLoading={loading} variant="secondary">
              Đổi mật khẩu
            </Button>
          </div>
        </form>
      </Card>
    </div>
  )
}

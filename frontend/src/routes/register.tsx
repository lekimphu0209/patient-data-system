import { createRoute, Link, useNavigate } from '@tanstack/react-router'
import { AlertCircle, Eye, EyeOff, Lock, Mail, User } from 'lucide-react'
import { useState } from 'react'

import { useAuth } from '@/app/auth-context'
import { AuthLayout } from '@/components/layout/AuthLayout'
import { Button, FormField, Input, Select } from '@/components/ui'
import { ROLE_LABELS, VALIDATION_MESSAGES } from '@/constants'
import { register } from '@/features/auth/api'
import { errorMessage } from '@/lib/utils'
import { rootRoute } from '@/routes/__root'

export const registerRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/register',
  component: RegisterPage,
})

const ROLE_OPTIONS = Object.entries(ROLE_LABELS)
  .filter(([value]) => value !== 'admin')
  .map(([value, label]) => ({ value, label }))

function RegisterPage() {
  const navigate = useNavigate()
  const { login: setAuth } = useAuth()
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [role, setRole] = useState('doctor')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (password.length < 6) {
      setError(VALIDATION_MESSAGES.passwordTooShort)
      return
    }
    if (password !== confirmPassword) {
      setError('Mật khẩu xác nhận không khớp')
      return
    }

    setLoading(true)
    try {
      const result = await register({
        email: email.trim(),
        full_name: fullName.trim(),
        password,
        role,
      })
      setAuth(result.access_token, result.user)
      navigate({ to: '/patients', search: { page: 1, limit: 10, q: '', diagnosis: '' } })
    } catch (err) {
      setError(errorMessage(err, 'Đăng ký thất bại, vui lòng thử lại.'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthLayout
      title="Đăng ký tài khoản"
      subtitle="Tạo tài khoản để bắt đầu quản lý hồ sơ bệnh nhân."
      footer={
        <>
          Đã có tài khoản?{' '}
          <Link to="/login" className="font-medium text-brand-700 hover:underline">
            Đăng nhập
          </Link>
        </>
      }
    >
      {error && (
        <div className="mb-5 flex items-start gap-2.5 rounded-lg border border-red-200 bg-red-50 px-3.5 py-3 text-sm text-red-700">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-5" autoComplete="off">
        <FormField label="Họ và tên" htmlFor="full_name" required>
          <Input
            id="full_name"
            type="text"
            inputSize="lg"
            autoComplete="off"
            placeholder="VD: Nguyễn Văn An"
            leftIcon={<User className="h-4 w-4" />}
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            required
            autoFocus
          />
        </FormField>

        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
          <FormField label="Email" htmlFor="email" required className="sm:col-span-2">
            <Input
              id="email"
              type="email"
              inputSize="lg"
              autoComplete="off"
              placeholder="Nhập địa chỉ email"
              leftIcon={<Mail className="h-4 w-4" />}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </FormField>

          <FormField label="Vai trò" htmlFor="role" className="sm:col-span-2">
            <Select
              id="role"
              selectSize="lg"
              options={ROLE_OPTIONS}
              value={role}
              onChange={(e) => setRole(e.target.value)}
            />
          </FormField>

          <FormField label="Mật khẩu" htmlFor="password" required>
            <Input
              id="password"
              type={showPassword ? 'text' : 'password'}
              inputSize="lg"
              autoComplete="new-password"
              placeholder="Tối thiểu 6 ký tự"
              leftIcon={<Lock className="h-4 w-4" />}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
              rightSlot={
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                  className="pointer-events-auto rounded p-1 transition-colors hover:text-slate-600"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              }
            />
          </FormField>

          <FormField label="Xác nhận mật khẩu" htmlFor="confirm_password" required>
            <Input
              id="confirm_password"
              type={showPassword ? 'text' : 'password'}
              inputSize="lg"
              autoComplete="new-password"
              placeholder="Nhập lại mật khẩu"
              leftIcon={<Lock className="h-4 w-4" />}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
            />
          </FormField>
        </div>

        <Button type="submit" isLoading={loading} size="lg" className="w-full">
          {loading ? 'Đang tạo tài khoản...' : 'Đăng ký'}
        </Button>
      </form>
    </AuthLayout>
  )
}

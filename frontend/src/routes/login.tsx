import { createRoute, Link, useNavigate } from '@tanstack/react-router'
import { AlertCircle, Eye, EyeOff, Lock, Mail } from 'lucide-react'
import { useState } from 'react'

import { useAuth } from '@/app/auth-context'
import { AuthLayout } from '@/components/layout/AuthLayout'
import { Button, FormField, Input } from '@/components/ui'
import { login } from '@/features/auth/api'
import { errorMessage } from '@/lib/utils'
import { rootRoute } from '@/routes/__root'

export const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/login',
  component: LoginPage,
})

function LoginPage() {
  const navigate = useNavigate()
  const { login: setAuth } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const result = await login(email.trim(), password)
      setAuth(result.access_token, result.user)
      navigate({ to: '/patients', search: { page: 1, limit: 10, q: '', diagnosis: '' } })
    } catch (err) {
      setError(errorMessage(err, 'Email hoặc mật khẩu không đúng.'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthLayout
      title="Đăng nhập"
      subtitle="Nhập thông tin tài khoản để truy cập hệ thống."
      footer={
        <>
          Chưa có tài khoản?{' '}
          <Link to="/register" className="font-medium text-brand-700 hover:underline">
            Đăng ký ngay
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
        <FormField label="Email" htmlFor="email" required>
          <Input
            id="email"
            name="email"
            type="email"
            inputSize="lg"
            autoComplete="off"
            placeholder="Nhập địa chỉ email"
            leftIcon={<Mail className="h-4 w-4" />}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoFocus
          />
        </FormField>

        <FormField label="Mật khẩu" htmlFor="password" required>
          <Input
            id="password"
            name="password"
            type={showPassword ? 'text' : 'password'}
            inputSize="lg"
            autoComplete="new-password"
            placeholder="Nhập mật khẩu"
            leftIcon={<Lock className="h-4 w-4" />}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
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

        <Button type="submit" isLoading={loading} size="lg" className="w-full">
          {loading ? 'Đang đăng nhập...' : 'Đăng nhập'}
        </Button>
      </form>
    </AuthLayout>
  )
}

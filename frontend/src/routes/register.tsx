import { createRoute, Link, useNavigate } from '@tanstack/react-router'
import { useState } from 'react'

import { useAuth } from '@/app/auth-context'
import { Button, Card, Input } from '@/components/ui'
import { register } from '@/features/auth/api'
import { rootRoute } from '@/routes/__root'

export const registerRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/register',
  component: RegisterPage,
})

function RegisterPage() {
  const navigate = useNavigate()
  const { login: setAuth } = useAuth()
  const [email, setEmail] = useState('')
  const [fullName, setFullName] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (password !== confirmPassword) {
      setError('Mật khẩu xác nhận không khớp')
      return
    }

    setLoading(true)
    try {
      const result = await register({
        email,
        full_name: fullName,
        password,
        role: 'doctor',
      })
      setAuth(result.access_token, result.user)
      navigate({ to: '/patients' })
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Đăng ký thất bại')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100">
      <Card size="xs" className="shadow-md">
        <h1 className="text-2xl font-bold mb-6 text-center text-gray-900">Đăng ký</h1>
        {error && <div className="mb-4 text-red-600 text-sm">{error}</div>}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Họ và tên</label>
            <Input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Mật khẩu</label>
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Xác nhận mật khẩu</label>
            <Input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
            />
          </div>
          <Button type="submit" isLoading={loading} variant="secondary" className="w-full">
            Đăng ký
          </Button>
        </form>
        <p className="mt-4 text-sm text-center text-gray-600">
          Đã có tài khoản?{' '}
          <Link to="/login" className="text-teal-700 hover:underline">
            Đăng nhập
          </Link>
        </p>
      </Card>
    </div>
  )
}

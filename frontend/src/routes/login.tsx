import { createRoute, Link, useNavigate } from '@tanstack/react-router'
import { useState } from 'react'

import { useAuth } from '@/app/auth-context'
import { Button, Card, Input } from '@/components/ui'
import { rootRoute } from '@/routes/__root'
import { login } from '@/features/auth/api'

export const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/login',
  component: LoginPage,
})

function LoginPage() {
  const navigate = useNavigate()
  const { login: setAuth } = useAuth()
  const [email, setEmail] = useState('doctor@example.com')
  const [password, setPassword] = useState('password123')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const result = await login(email, password)
      setAuth(result.access_token, result.user)
      navigate({ to: '/patients' })
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100">
      <Card size="xs" className="shadow-md">
        <h1 className="text-2xl font-bold mb-6 text-center text-gray-900">Đăng nhập</h1>
        {error && (
          <div className="mb-4 text-red-600 text-sm">{error}</div>
        )}
        <form onSubmit={handleSubmit} className="space-y-4">
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
          <Button type="submit" isLoading={loading} variant="secondary" className="w-full">
            Đăng nhập
          </Button>
        </form>
        <p className="mt-4 text-sm text-center text-gray-600">
          Chưa có tài khoản?{' '}
          <Link to="/register" className="text-teal-700 hover:underline">
            Đăng ký
          </Link>
        </p>
      </Card>
    </div>
  )
}

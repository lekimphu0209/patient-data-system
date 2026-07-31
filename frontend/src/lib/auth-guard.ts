import { redirect } from '@tanstack/react-router'

import { getMe } from '@/features/auth/api'

export async function requireAuth() {
  const token = sessionStorage.getItem('token')
  if (!token) throw redirect({ to: '/login' })
  try {
    await getMe()
  } catch {
    sessionStorage.removeItem('token')
    sessionStorage.removeItem('user')
    throw redirect({ to: '/login' })
  }
}

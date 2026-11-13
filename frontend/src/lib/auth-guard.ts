import { redirect } from '@tanstack/react-router'

export function requireAuth() {
  if (!sessionStorage.getItem('token')) {
    throw redirect({ to: '/login', hash: window.location.hash.slice(1), replace: true })
  }
}

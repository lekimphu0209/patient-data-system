import { createRoute, Navigate } from '@tanstack/react-router'

import { rootRoute } from '@/routes/__root'

export const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: IndexRedirect,
})

function IndexRedirect() {
  return <Navigate to="/login" />
}

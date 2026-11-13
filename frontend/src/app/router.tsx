import { createRoute, createRouter, redirect } from '@tanstack/react-router'
import { rootRoute } from '@/routes/__root'
import { indexRoute } from '@/routes/index'
import { loginRoute } from '@/routes/login'

const legacyRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '$',
  beforeLoad: () => { throw redirect({ to: '/', replace: true }) },
})

const routeTree = rootRoute.addChildren([indexRoute, loginRoute, legacyRoute])
export const router = createRouter({ routeTree })

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

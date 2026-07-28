import { createRootRoute, Outlet } from '@tanstack/react-router'

import { AuthProvider } from '@/app/auth-context'
import { Providers } from '@/app/providers'

export const rootRoute = createRootRoute({
  component: RootComponent,
})

function RootComponent() {
  return (
    <Providers>
      <AuthProvider>
        <Outlet />
      </AuthProvider>
    </Providers>
  )
}

import { createRouter } from '@tanstack/react-router'
import { rootRoute } from '@/routes/__root'
import { indexRoute } from '@/routes/index'
import { loginRoute } from '@/routes/login'
import { patientsRoute } from '@/routes/patients'
import { newPatientRoute } from '@/routes/patients.new'

const routeTree = rootRoute.addChildren([
  indexRoute,
  loginRoute,
  patientsRoute,
  newPatientRoute,
])

export const router = createRouter({ routeTree })

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

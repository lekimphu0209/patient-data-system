import { createRouter } from '@tanstack/react-router'
import { rootRoute } from '@/routes/__root'
import { indexRoute } from '@/routes/index'
import { loginRoute } from '@/routes/login'
import { registerRoute } from '@/routes/register'
import { patientsRoute } from '@/routes/patients'
import { newPatientRoute } from '@/routes/patients.new'
import { patientDetailRoute } from '@/routes/patients.$id'
import { patientEditRoute } from '@/routes/patients.$id.edit'
import { profileRoute } from '@/routes/profile'

const routeTree = rootRoute.addChildren([
  indexRoute,
  loginRoute,
  registerRoute,
  patientsRoute,
  newPatientRoute,
  patientDetailRoute,
  patientEditRoute,
  profileRoute,
])

export const router = createRouter({ routeTree })

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

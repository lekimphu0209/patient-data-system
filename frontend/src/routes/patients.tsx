import { createRoute } from '@tanstack/react-router'
import { rootRoute } from '@/routes/__root'
import { requireAuth } from '@/lib/auth-guard'
import { PatientList } from '@/features/patients/components/PatientList'

export const patientsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/patients',
  component: PatientList,
  beforeLoad: requireAuth,
})

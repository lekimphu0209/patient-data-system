import { createRoute } from '@tanstack/react-router'

import { ALLOWED_PAGE_SIZES, PAGINATION_DEFAULTS } from '@/constants'
import { PatientList } from '@/features/patients/components/PatientList'
import { requireAuth } from '@/lib/auth-guard'
import { rootRoute } from '@/routes/__root'

export interface PatientSearch {
  page: number
  limit: number
  q: string
  diagnosis: string
}

/**
 * List state lives in the URL so a filtered view stays shareable and survives
 * a refresh or a trip to the detail page and back.
 */
function validateSearch(search: Record<string, unknown>): PatientSearch {
  const page = Number(search.page)
  const limit = Number(search.limit)

  return {
    page: Number.isFinite(page) && page >= 1 ? Math.floor(page) : PAGINATION_DEFAULTS.page,
    limit: ALLOWED_PAGE_SIZES.includes(limit) ? limit : PAGINATION_DEFAULTS.limit,
    q: typeof search.q === 'string' ? search.q : '',
    diagnosis: typeof search.diagnosis === 'string' ? search.diagnosis : '',
  }
}

export const patientsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/patients',
  component: PatientList,
  beforeLoad: requireAuth,
  validateSearch,
})

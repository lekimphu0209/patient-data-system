import { createRoute, lazyRouteComponent } from '@tanstack/react-router'
import { requireAuth } from '@/lib/auth-guard'
import { rootRoute } from '@/routes/__root'

export const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  beforeLoad: requireAuth,
  component: lazyRouteComponent(() => import('@/features/surveys/SurveyWorkspace'), 'SurveyWorkspace'),
})

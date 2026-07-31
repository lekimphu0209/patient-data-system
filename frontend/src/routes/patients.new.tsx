import { useMutation, useQueryClient } from '@tanstack/react-query'
import { createRoute, useNavigate } from '@tanstack/react-router'
import { useState } from 'react'

import { AppShell } from '@/components/layout/AppShell'
import { PageHeader } from '@/components/ui'
import { createPatient } from '@/features/patients/api'
import type { PatientCreateRequest } from '@/features/patients/api'
import { PatientForm } from '@/features/patients/components/PatientForm'
import { requireAuth } from '@/lib/auth-guard'
import { errorMessage } from '@/lib/utils'
import { rootRoute } from '@/routes/__root'

export const newPatientRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/patients/new',
  component: NewPatientPage,
  beforeLoad: requireAuth,
})

function NewPatientPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [saveError, setSaveError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: createPatient,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patients'] })
      navigate({ to: '/patients', search: { page: 1, limit: 10, q: '', diagnosis: '' } })
    },
    onError: (err) => {
      setSaveError(errorMessage(err, 'Có lỗi xảy ra khi lưu bệnh nhân.'))
    },
  })

  const handleSubmit = (data: PatientCreateRequest) => {
    setSaveError(null)
    mutation.mutate(data)
  }

  return (
    <AppShell width="narrow">
      <PageHeader
        title="Thêm bệnh nhân"
        description="Nhập thông tin để tạo hồ sơ bệnh nhân mới."
        backTo="/patients"
      />
      <PatientForm
        mode="new"
        loading={mutation.isPending}
        onSubmit={handleSubmit}
        onCancel={() => navigate({ to: '/patients', search: { page: 1, limit: 10, q: '', diagnosis: '' } })}
        error={saveError}
      />
    </AppShell>
  )
}

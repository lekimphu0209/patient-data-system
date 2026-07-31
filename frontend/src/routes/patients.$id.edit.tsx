import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createRoute, useNavigate, useParams } from '@tanstack/react-router'
import { useState } from 'react'

import { AppShell } from '@/components/layout/AppShell'
import { ErrorState, Loading, PageHeader } from '@/components/ui'
import { getPatient, updatePatient } from '@/features/patients/api'
import type { PatientCreateRequest } from '@/features/patients/api'
import { PatientForm } from '@/features/patients/components/PatientForm'
import { requireAuth } from '@/lib/auth-guard'
import { errorMessage } from '@/lib/utils'
import { rootRoute } from '@/routes/__root'

export const patientEditRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/patients/$id/edit',
  component: PatientEditPage,
  beforeLoad: requireAuth,
})

function PatientEditPage() {
  const { id } = useParams({ from: patientEditRoute.id })
  const patientId = Number(id)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [saveError, setSaveError] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['patient', patientId],
    queryFn: async () => (await getPatient(patientId)).data,
    enabled: !Number.isNaN(patientId),
  })

  const mutation = useMutation({
    mutationFn: (payload: PatientCreateRequest) => updatePatient(patientId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patients'] })
      queryClient.invalidateQueries({ queryKey: ['patient', patientId] })
      navigate({ to: '/patients', search: { page: 1, limit: 10, q: '', diagnosis: '' } })
    },
    onError: (err) => {
      setSaveError(errorMessage(err, 'Có lỗi xảy ra khi cập nhật bệnh nhân.'))
    },
  })

  const handleSubmit = (payload: PatientCreateRequest) => {
    setSaveError(null)
    mutation.mutate(payload)
  }

  return (
    <AppShell width="narrow">
      <PageHeader
        title="Chỉnh sửa bệnh nhân"
        description={data ? `Mã hồ sơ ${data.patient_code}` : undefined}
        backTo="/patients"
      />

      {isLoading ? (
        <Loading text="Đang tải thông tin bệnh nhân..." />
      ) : !data ? (
        <ErrorState message="Không tìm thấy bệnh nhân." />
      ) : (
        <PatientForm
          mode="edit"
          patient={data}
          loading={mutation.isPending}
          onSubmit={handleSubmit}
          onCancel={() => navigate({ to: '/patients', search: { page: 1, limit: 10, q: '', diagnosis: '' } })}
          error={saveError}
        />
      )}
    </AppShell>
  )
}

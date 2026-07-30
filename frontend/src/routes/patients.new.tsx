import { createRoute, useNavigate } from '@tanstack/react-router'
import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'

import { rootRoute } from '@/routes/__root'
import { requireAuth } from '@/lib/auth-guard'
import { createPatient } from '@/features/patients/api'
import type { PatientCreateRequest } from '@/features/patients/api'
import { PatientForm } from '@/features/patients/components/PatientForm'

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
      navigate({ to: '/patients' })
    },
    onError: (err: any) => {
      setSaveError(err.message || 'Có lỗi xảy ra khi lưu bệnh nhân.')
    },
  })

  const handleSubmit = async (data: PatientCreateRequest) => {
    setSaveError(null)
    try {
      await mutation.mutateAsync(data)
    } catch {}
  }

  const handleCancel = () => {
    navigate({ to: '/patients' })
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <PatientForm
        mode="new"
        loading={mutation.isPending}
        onSubmit={handleSubmit}
        onCancel={handleCancel}
        error={saveError}
      />
    </div>
  )
}

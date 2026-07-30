import { createRoute, useNavigate, useParams } from '@tanstack/react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { rootRoute } from '@/routes/__root'
import { requireAuth } from '@/lib/auth-guard'
import { getPatient, updatePatient } from '@/features/patients/api'
import type { PatientCreateRequest } from '@/features/patients/api'
import { PatientForm } from '@/features/patients/components/PatientForm'

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
    queryFn: async () => {
      const res = await getPatient(patientId)
      return res.data
    },
    enabled: !isNaN(patientId),
  })

  const mutation = useMutation({
    mutationFn: (data: PatientCreateRequest) => updatePatient(patientId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patients'] })
      queryClient.invalidateQueries({ queryKey: ['patient', patientId] })
      navigate({ to: '/patients' })
    },
    onError: (err: any) => {
      setSaveError(err.message || 'Có lỗi xảy ra khi cập nhật bệnh nhân.')
    },
  })

  const handleSubmit = async (payload: PatientCreateRequest) => {
    setSaveError(null)
    try {
      await mutation.mutateAsync(payload)
    } catch {}
  }

  const handleCancel = () => {
    navigate({ to: '/patients' })
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 p-6">
        <div className="max-w-4xl mx-auto text-center text-gray-500 py-12">
          Đang tải thông tin bệnh nhân...
        </div>
      </div>
    )
  }

  if (!data && !isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 p-6">
        <div className="max-w-4xl mx-auto text-center text-red-600 py-12">
          Không tìm thấy bệnh nhân.
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <PatientForm
        mode="edit"
        patient={data}
        loading={mutation.isPending}
        onSubmit={handleSubmit}
        onCancel={handleCancel}
        error={saveError}
      />
    </div>
  )
}

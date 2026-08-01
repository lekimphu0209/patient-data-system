import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createRoute, useNavigate, useParams } from '@tanstack/react-router'
import { AlertCircle, Save } from 'lucide-react'
import { useState } from 'react'

import { AppShell } from '@/components/layout/AppShell'
import { Button, Card, ErrorState, Loading, PageHeader } from '@/components/ui'
import {
  createExamination,
  getPatient,
  getPatientFormSchema,
  type FormNode,
  type FormValues,
} from '@/features/patients/api'
import { DynamicForm } from '@/features/patients/components/DynamicForm'
import { requireAuth } from '@/lib/auth-guard'
import { errorMessage } from '@/lib/utils'
import { rootRoute } from '@/routes/__root'

export const newExamRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/patients/$id/exams/new',
  component: NewExamPage,
  beforeLoad: requireAuth,
})

const todayISO = () => new Date().toISOString().slice(0, 10)

function NewExamPage() {
  const { id } = useParams({ from: newExamRoute.id })
  const patientId = Number(id)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [error, setError] = useState('')
  const [values, setValues] = useState<FormValues>({ exam_info: { exam_date: todayISO() } })

  const { data: patient, isLoading: patientLoading } = useQuery({
    queryKey: ['patient', patientId],
    queryFn: async () => (await getPatient(patientId)).data,
  })

  const { data: schema, isLoading: schemaLoading } = useQuery({
    queryKey: ['form-schema', patientId],
    queryFn: () => getPatientFormSchema(patientId),
  })

  const block: FormNode | undefined = schema?.blocks.find((b) => b.id === 'examination')

  const mutation = useMutation({
    mutationFn: () => createExamination(patientId, { data: values }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['exams', patientId] })
      navigate({ to: '/patients/$id', params: { id: String(patientId) } })
    },
    onError: (err) => setError(errorMessage(err, 'Lưu lần khám thất bại')),
  })

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    if (!values.exam_info?.exam_date) {
      setError('Vui lòng nhập ngày khám')
      return
    }
    setError('')
    mutation.mutate()
  }

  if (patientLoading || schemaLoading) {
    return (
      <AppShell>
        <Card size="full">
          <Loading text="Đang tải biểu mẫu khám bệnh..." />
        </Card>
      </AppShell>
    )
  }

  if (!patient || !block) {
    return (
      <AppShell>
        <Card size="full">
          <ErrorState message="Không tìm thấy bệnh nhân hoặc biểu mẫu khám bệnh." />
        </Card>
      </AppShell>
    )
  }

  return (
    <AppShell>
      <PageHeader
        title="Nhập lần khám mới"
        description={`${patient.full_name}${schema ? ` · ${schema.disease_label}` : ''}`}
        backTo={`/patients/${patientId}`}
        backLabel="Quay lại chi tiết bệnh nhân"
      />

      <Card size="full">
        <form onSubmit={handleSubmit} className="space-y-6">
          {error && (
            <div className="flex items-start gap-2.5 rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-700">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <DynamicForm block={block} values={values} onChange={setValues} mode="edit" />

          <div className="flex gap-2.5 border-t border-slate-100 pt-6">
            <Button
              type="button"
              variant="outline"
              onClick={() => navigate({ to: '/patients/$id', params: { id: String(patientId) } })}
              disabled={mutation.isPending}
            >
              Hủy
            </Button>
            <Button
              type="submit"
              isLoading={mutation.isPending}
              leftIcon={!mutation.isPending ? <Save className="h-4 w-4" /> : undefined}
            >
              Lưu lần khám
            </Button>
          </div>
        </form>
      </Card>
    </AppShell>
  )
}

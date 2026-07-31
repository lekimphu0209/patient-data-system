import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createRoute, useNavigate, useParams } from '@tanstack/react-router'
import { AlertCircle, Save } from 'lucide-react'
import { useState } from 'react'

import { AppShell } from '@/components/layout/AppShell'
import { Button, Card, ErrorState, FormField, FormSection, Input, Loading, PageHeader, Textarea } from '@/components/ui'
import { createExamination, getPatient, type Examination } from '@/features/patients/api'
import { requireAuth } from '@/lib/auth-guard'
import { errorMessage } from '@/lib/utils'
import { rootRoute } from '@/routes/__root'

export const newExamRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/patients/$id/exams/new',
  component: NewExamPage,
  beforeLoad: requireAuth,
})

function NewExamPage() {
  const { id } = useParams({ from: newExamRoute.id })
  const patientId = Number(id)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [error, setError] = useState('')

  const { data: patient, isLoading } = useQuery({
    queryKey: ['patient', patientId],
    queryFn: async () => (await getPatient(patientId)).data,
  })

  const [formData, setFormData] = useState<Partial<Examination>>({
    exam_date: new Date().toISOString().split('T')[0],
  })

  const mutation = useMutation({
    mutationFn: (data: Partial<Examination>) => createExamination(patientId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['exams', patientId] })
      navigate({ to: '/patients/$id', params: { id: String(patientId) } })
    },
    onError: (err) => {
      setError(errorMessage(err, 'Lưu lần khám thất bại'))
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!formData.exam_date) {
      setError('Vui lòng nhập ngày khám')
      return
    }
    mutation.mutate(formData)
  }

  if (isLoading) {
    return (
      <AppShell width="narrow">
        <Loading text="Đang tải thông tin bệnh nhân..." />
      </AppShell>
    )
  }

  if (!patient) {
    return (
      <AppShell width="narrow">
        <ErrorState message="Không tìm thấy bệnh nhân" />
      </AppShell>
    )
  }

  return (
    <AppShell width="narrow">
      <PageHeader
        title="Nhập lần khám mới"
        description={`Bệnh nhân: ${patient.full_name}`}
        backTo="/patients"
      />

      <Card size="full">
        <form onSubmit={handleSubmit} className="space-y-6">
          {error && (
            <div className="flex items-start gap-2.5 rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-700">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <FormSection title="Ngày khám">
            <FormField label="Ngày khám" htmlFor="exam_date" required>
              <Input
                id="exam_date"
                type="date"
                value={formData.exam_date || ''}
                onChange={(e) => setFormData({ ...formData, exam_date: e.target.value })}
                required
              />
            </FormField>
          </FormSection>

          <FormSection title="Khám thực thể">
            <div className="space-y-4">
              <FormField label="Toàn thân" htmlFor="general_condition">
                <Textarea
                  id="general_condition"
                  rows={3}
                  value={formData.general_condition || ''}
                  onChange={(e) => setFormData({ ...formData, general_condition: e.target.value })}
                  placeholder="Mô tả tình trạng toàn thân"
                />
              </FormField>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <FormField label="Tuần hoàn" htmlFor="cardiovascular">
                  <Textarea
                    id="cardiovascular"
                    rows={2}
                    value={formData.cardiovascular || ''}
                    onChange={(e) => setFormData({ ...formData, cardiovascular: e.target.value })}
                  />
                </FormField>

                <FormField label="Hô hấp" htmlFor="respiratory">
                  <Textarea
                    id="respiratory"
                    rows={2}
                    value={formData.respiratory || ''}
                    onChange={(e) => setFormData({ ...formData, respiratory: e.target.value })}
                  />
                </FormField>
              </div>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <FormField label="Tiêu hóa" htmlFor="digestive">
                  <Textarea
                    id="digestive"
                    rows={2}
                    value={formData.digestive || ''}
                    onChange={(e) => setFormData({ ...formData, digestive: e.target.value })}
                  />
                </FormField>

                <FormField label="Tiết niệu" htmlFor="urinary">
                  <Textarea
                    id="urinary"
                    rows={2}
                    value={formData.urinary || ''}
                    onChange={(e) => setFormData({ ...formData, urinary: e.target.value })}
                  />
                </FormField>
              </div>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <FormField label="Khám thần kinh" htmlFor="neurological">
                  <Textarea
                    id="neurological"
                    rows={2}
                    value={formData.neurological || ''}
                    onChange={(e) => setFormData({ ...formData, neurological: e.target.value })}
                  />
                </FormField>

                <FormField label="Khám các bộ phận khác" htmlFor="other_body_parts">
                  <Textarea
                    id="other_body_parts"
                    rows={2}
                    value={formData.other_body_parts || ''}
                    onChange={(e) => setFormData({ ...formData, other_body_parts: e.target.value })}
                  />
                </FormField>
              </div>
            </div>
          </FormSection>

          <FormSection title="Chẩn đoán & Điều trị">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <FormField label="Chẩn đoán" htmlFor="diagnosis">
                <Textarea
                  id="diagnosis"
                  rows={2}
                  value={formData.diagnosis || ''}
                  onChange={(e) => setFormData({ ...formData, diagnosis: e.target.value })}
                />
              </FormField>

              <FormField label="Điều trị" htmlFor="treatment">
                <Textarea
                  id="treatment"
                  rows={2}
                  value={formData.treatment || ''}
                  onChange={(e) => setFormData({ ...formData, treatment: e.target.value })}
                />
              </FormField>
            </div>
          </FormSection>

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

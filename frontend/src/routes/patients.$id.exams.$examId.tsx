/**
 * Xem và sửa một lần khám. Hai route dùng chung một component, khác nhau ở chế
 * độ render của DynamicForm — biểu mẫu vẫn lấy từ schema của backend nên luôn
 * khớp với template ứng với loại bệnh của bệnh nhân.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createRoute, useNavigate, useParams } from '@tanstack/react-router'
import { AlertCircle, Edit2, Save } from 'lucide-react'
import { useEffect, useState } from 'react'

import { AppShell } from '@/components/layout/AppShell'
import { Button, Card, ErrorState, Loading, PageHeader } from '@/components/ui'
import {
  getExamination,
  getPatient,
  getPatientFormSchema,
  updateExamination,
  type FormValues,
} from '@/features/patients/api'
import { DynamicForm } from '@/features/patients/components/DynamicForm'
import { requireAuth } from '@/lib/auth-guard'
import { errorMessage } from '@/lib/utils'
import { rootRoute } from '@/routes/__root'

export const examDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/patients/$id/exams/$examId',
  component: () => <ExamPage mode="view" />,
  beforeLoad: requireAuth,
})

export const examEditRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/patients/$id/exams/$examId/edit',
  component: () => <ExamPage mode="edit" />,
  beforeLoad: requireAuth,
})

function ExamPage({ mode }: { mode: 'view' | 'edit' }) {
  const routeId = mode === 'view' ? examDetailRoute.id : examEditRoute.id
  const { id, examId } = useParams({ from: routeId })
  const patientId = Number(id)
  const examIdNum = Number(examId)
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [values, setValues] = useState<FormValues>({})
  const [error, setError] = useState('')

  const { data: patient } = useQuery({
    queryKey: ['patient', patientId],
    queryFn: async () => (await getPatient(patientId)).data,
  })

  const { data: schema, isLoading: schemaLoading } = useQuery({
    queryKey: ['form-schema', patientId],
    queryFn: () => getPatientFormSchema(patientId),
  })

  const { data: exam, isLoading: examLoading } = useQuery({
    queryKey: ['exam', patientId, examIdNum],
    queryFn: async () => (await getExamination(patientId, examIdNum)).data,
  })

  // Chỉ nạp giá trị một lần cho mỗi lần khám: refetch (ví dụ khi quay lại tab)
  // mà gán đè thì mọi chỉnh sửa dở dang sẽ mất.
  const [loadedExamId, setLoadedExamId] = useState<number | null>(null)
  useEffect(() => {
    if (exam && loadedExamId !== exam.id) {
      setValues(exam.data ?? {})
      setLoadedExamId(exam.id)
    }
  }, [exam, loadedExamId])

  const block = schema?.blocks.find((b) => b.id === 'examination')
  const backToPatient = `/patients/${patientId}`

  const saveMutation = useMutation({
    mutationFn: () => updateExamination(patientId, examIdNum, { data: values }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['exams', patientId] })
      queryClient.invalidateQueries({ queryKey: ['exam', patientId, examIdNum] })
      navigate({ to: backToPatient })
    },
    onError: (err) => setError(errorMessage(err, 'Cập nhật lần khám thất bại')),
  })

  if (schemaLoading || examLoading) {
    return (
      <AppShell>
        <Card size="full">
          <Loading text="Đang tải lần khám..." />
        </Card>
      </AppShell>
    )
  }

  if (!exam || !block) {
    return (
      <AppShell>
        <Card size="full">
          <ErrorState message="Không tìm thấy lần khám." />
        </Card>
      </AppShell>
    )
  }

  const examDate = exam.exam_date ? new Date(exam.exam_date).toLocaleDateString('vi-VN') : ''

  return (
    <AppShell>
      <PageHeader
        title={mode === 'view' ? 'Chi tiết lần khám' : 'Sửa lần khám'}
        description={[patient?.full_name, examDate && `Ngày khám ${examDate}`]
          .filter(Boolean)
          .join(' · ')}
        backTo={backToPatient}
        backLabel="Quay lại chi tiết bệnh nhân"
        action={
          mode === 'view' ? (
            <Button
              size="sm"
              leftIcon={<Edit2 className="h-4 w-4" />}
              onClick={() =>
                navigate({
                  to: '/patients/$id/exams/$examId/edit',
                  params: { id: String(patientId), examId: String(examIdNum) },
                })
              }
            >
              Sửa
            </Button>
          ) : undefined
        }
      />

      <Card size="full">
        {error && (
          <div className="mb-4 flex items-start gap-2.5 rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-700">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <DynamicForm block={block} values={values} onChange={setValues} mode={mode} />

        {mode === 'edit' && (
          <div className="mt-6 flex gap-2.5 border-t border-slate-100 pt-6">
            <Button
              variant="outline"
              onClick={() =>
                navigate({
                  to: '/patients/$id/exams/$examId',
                  params: { id: String(patientId), examId: String(examIdNum) },
                })
              }
              disabled={saveMutation.isPending}
            >
              Hủy
            </Button>
            <Button
              isLoading={saveMutation.isPending}
              onClick={() => saveMutation.mutate()}
              leftIcon={!saveMutation.isPending ? <Save className="h-4 w-4" /> : undefined}
            >
              Lưu thay đổi
            </Button>
          </div>
        )}
      </Card>
    </AppShell>
  )
}

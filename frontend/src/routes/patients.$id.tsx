import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createRoute, useNavigate, useParams } from '@tanstack/react-router'
import { AlertCircle, Edit2 } from 'lucide-react'
import { useEffect, useState } from 'react'

import { AppShell } from '@/components/layout/AppShell'
import { Button, Card, ErrorState, Loading, PageHeader } from '@/components/ui'
import {
  getPatient,
  getPatientFormSchema,
  updatePatient,
  type FormNode,
  type FormValues,
  type Patient,
} from '@/features/patients/api'
import {
  ExaminationsSection,
  MedicalHistorySection,
} from '@/features/patients/components/PatientDetailSections'
import { ExamMetricsSection } from '@/features/patients/components/ExamMetricsSection'
import { DynamicForm } from '@/features/patients/components/DynamicForm'
import { requireAuth } from '@/lib/auth-guard'
import { errorMessage } from '@/lib/utils'
import { rootRoute } from '@/routes/__root'

export const patientDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/patients/$id',
  component: PatientDetailPage,
  beforeLoad: requireAuth,
})

// Khối hành chính lấy dữ liệu thẳng từ bảng patients, nên mỗi field khai báo
// `source` để biết đọc/ghi vào đâu.
const METADATA_PREFIX = 'patient.metadata.'

function readSource(patient: Patient, source: string | undefined): unknown {
  if (!source) return undefined
  if (source.startsWith(METADATA_PREFIX)) {
    return patient.patient_metadata?.[source.slice(METADATA_PREFIX.length)]
  }
  return (patient as unknown as Record<string, unknown>)[source.replace('patient.', '')]
}

function adminValuesFrom(block: FormNode | undefined, patient: Patient): FormValues {
  const values: FormValues = {}
  for (const node of block?.children ?? []) {
    values[node.id] = readSource(patient, node.source) ?? undefined
  }
  return values
}

function adminPayloadFrom(
  block: FormNode | undefined,
  values: FormValues,
  patient: Patient,
): Record<string, unknown> {
  const payload: Record<string, unknown> = {}
  const metadata: Record<string, unknown> = { ...(patient.patient_metadata ?? {}) }

  for (const node of block?.children ?? []) {
    if (node.readonly || !node.source) continue
    const value = values[node.id] === '' ? null : values[node.id]
    if (node.source.startsWith(METADATA_PREFIX)) {
      metadata[node.source.slice(METADATA_PREFIX.length)] = value
    } else {
      payload[node.source.replace('patient.', '')] = value
    }
  }
  payload.patient_metadata = metadata
  return payload
}

function PatientDetailPage() {
  const { id } = useParams({ from: patientDetailRoute.id })
  const patientId = Number(id)
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data: patient, isLoading } = useQuery({
    queryKey: ['patient', patientId],
    queryFn: async () => (await getPatient(patientId)).data as Patient,
    enabled: !Number.isNaN(patientId),
  })

  const { data: schema } = useQuery({
    queryKey: ['form-schema', patientId],
    queryFn: () => getPatientFormSchema(patientId),
    enabled: !Number.isNaN(patientId),
  })

  const adminBlock = schema?.blocks.find((block) => block.id === 'administrative')

  const [editingAdmin, setEditingAdmin] = useState(false)
  const [adminValues, setAdminValues] = useState<FormValues>({})
  const [error, setError] = useState('')

  useEffect(() => {
    if (patient && adminBlock && !editingAdmin) {
      setAdminValues(adminValuesFrom(adminBlock, patient))
    }
  }, [patient, adminBlock, editingAdmin])

  const updateMutation = useMutation({
    mutationFn: (values: FormValues) =>
      updatePatient(patientId, adminPayloadFrom(adminBlock, values, patient!) as never),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patient', patientId] })
      setEditingAdmin(false)
      setError('')
    },
    onError: (err) => setError(errorMessage(err, 'Cập nhật thất bại')),
  })

  if (isLoading) {
    return (
      <AppShell>
        <Card size="full">
          <Loading text="Đang tải thông tin bệnh nhân..." />
        </Card>
      </AppShell>
    )
  }

  if (!patient) {
    return (
      <AppShell>
        <Card size="full">
          <ErrorState message="Không tìm thấy bệnh nhân." />
        </Card>
      </AppShell>
    )
  }

  return (
    <AppShell>
      <PageHeader
        title="Chi tiết bệnh nhân"
        description={`Mã hồ sơ ${patient.patient_code}${
          schema ? ` · ${schema.disease_label}` : ''
        }`}
        backTo="/patients"
      />

      <div className="space-y-6">
        {/* Khối 1 — THỦ TỤC HÀNH CHÍNH */}
        <Card size="full">
          <div className="mb-6 flex items-start justify-between gap-4">
            <h3 className="text-lg font-semibold text-slate-900">
              {adminBlock?.label ?? 'THỦ TỤC HÀNH CHÍNH'}
            </h3>
            {!editingAdmin && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setEditingAdmin(true)}
                leftIcon={<Edit2 className="h-4 w-4" />}
              >
                Sửa
              </Button>
            )}
          </div>

          {error && (
            <div className="mb-4 flex items-start gap-2.5 rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-700">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {adminBlock ? (
            <>
              <DynamicForm
                block={adminBlock}
                values={adminValues}
                onChange={setAdminValues}
                mode={editingAdmin ? 'edit' : 'view'}
              />
              {editingAdmin && (
                <div className="mt-6 flex gap-2.5 border-t border-slate-100 pt-4">
                  <Button
                    variant="outline"
                    onClick={() => {
                      setAdminValues(adminValuesFrom(adminBlock, patient))
                      setEditingAdmin(false)
                      setError('')
                    }}
                    disabled={updateMutation.isPending}
                  >
                    Hủy
                  </Button>
                  <Button
                    isLoading={updateMutation.isPending}
                    onClick={() => updateMutation.mutate(adminValues)}
                  >
                    Lưu
                  </Button>
                </div>
              )}
            </>
          ) : (
            <Loading text="Đang tải biểu mẫu..." />
          )}
        </Card>

        {/* Khối 2 — HỎI BỆNH (ẩn với bệnh nhân bình thường) */}
        <MedicalHistorySection patientId={patientId} schema={schema} />

        {/* Khối 3 — KHÁM BỆNH */}
        <ExaminationsSection
          patientId={patientId}
          schema={schema}
          onCreateExam={() =>
            navigate({ to: '/patients/$id/exams/new', params: { id: String(patientId) } })
          }
          onViewExam={(examId) =>
            navigate({
              to: '/patients/$id/exams/$examId',
              params: { id: String(patientId), examId: String(examId) },
            })
          }
          onEditExam={(examId) =>
            navigate({
              to: '/patients/$id/exams/$examId/edit',
              params: { id: String(patientId), examId: String(examId) },
            })
          }
          onReviewExtraction={(extractionId) =>
            navigate({
              to: '/patients/$id/exams/review/$extractionId',
              params: { id: String(patientId), extractionId: String(extractionId) },
            })
          }
        />

        {/* Diễn biến các chỉ số dạng số theo trục thời gian khám */}
        <ExamMetricsSection patientId={patientId} />
      </div>
    </AppShell>
  )
}

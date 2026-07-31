import { AlertCircle, Edit2, Trash2, Eye } from 'lucide-react'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

import { Badge, Button, Card, FormField, Input, Select } from '@/components/ui'
import { GENDER_OPTIONS } from '@/constants'
import type { Patient, Examination } from '../api'
import { detectCondition, CONDITION_META } from '../constants'
import { listExaminations, deleteExamination } from '../api'

// ==================== Section 1: Administrative Info ====================

export function AdministrativeSection({ patient, onSave, loading }: {
  patient: Patient
  onSave: (data: Record<string, unknown>) => Promise<void>
  loading?: boolean
}) {
  const [editing, setEditing] = useState(false)
  const [formData, setFormData] = useState({
    full_name: patient.full_name || '',
    birth_date: patient.birth_date || '',
    hometown: patient.hometown || '',
    gender: patient.patient_metadata?.gender || '',
  })
  const [error, setError] = useState('')

  const handleSave = async () => {
    try {
      setError('')
      await onSave({
        full_name: formData.full_name,
        birth_date: formData.birth_date || undefined,
        hometown: formData.hometown || undefined,
        patient_metadata: {
          ...patient.patient_metadata,
          gender: formData.gender || undefined,
        },
      })
      setEditing(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Có lỗi xảy ra')
    }
  }

  return (
    <Card size="full">
      <div className="mb-6 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-slate-900">THỦ TỤC HÀNH CHÍNH</h3>
        {!editing && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setEditing(true)}
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

      {!editing ? (
        <div className="space-y-3">
          <DetailRow label="Mã hồ sơ" value={patient.patient_code} />
          <DetailRow label="Họ và tên" value={patient.full_name} />
          <DetailRow label="Ngày sinh" value={patient.birth_date} />
          <DetailRow label="Giới tính" value={patient.patient_metadata?.gender || '—'} />
          <DetailRow label="Quê quán" value={patient.hometown || '—'} />
        </div>
      ) : (
        <div className="space-y-4">
          <FormField label="Họ và tên" htmlFor="full_name">
            <Input
              id="full_name"
              value={formData.full_name}
              onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
            />
          </FormField>
          <FormField label="Ngày sinh" htmlFor="birth_date">
            <Input
              id="birth_date"
              type="date"
              value={formData.birth_date}
              onChange={(e) => setFormData({ ...formData, birth_date: e.target.value })}
            />
          </FormField>
          <FormField label="Giới tính" htmlFor="gender">
            <Select
              id="gender"
              value={formData.gender}
              onChange={(e) => setFormData({ ...formData, gender: e.target.value })}
              options={GENDER_OPTIONS}
            />
          </FormField>
          <FormField label="Quê quán" htmlFor="hometown">
            <Input
              id="hometown"
              value={formData.hometown}
              onChange={(e) => setFormData({ ...formData, hometown: e.target.value })}
            />
          </FormField>
          <div className="flex gap-2.5 border-t border-slate-100 pt-4">
            <Button
              variant="outline"
              onClick={() => {
                setEditing(false)
                setError('')
              }}
              disabled={loading}
            >
              Hủy
            </Button>
            <Button
              isLoading={loading}
              onClick={handleSave}
              leftIcon={!loading ? <Edit2 className="h-4 w-4" /> : undefined}
            >
              Lưu
            </Button>
          </div>
        </div>
      )}
    </Card>
  )
}

// ==================== Section 2: Medical History ====================

export function MedicalHistorySection({ patient, medicalHistory }: {
  patient: Patient
  medicalHistory: Record<string, unknown> | null | undefined
}) {
  const condition = detectCondition(patient)

  // Don't show for normal patients
  if (condition === 'normal') {
    return null
  }

  const conditionMeta = CONDITION_META[condition]

  return (
    <Card size="full">
      <div className="mb-6">
        <h3 className="text-lg font-semibold text-slate-900">HỎI BỆNH</h3>
        <p className="mt-1 text-sm text-slate-500">Thông tin ít thay đổi, theo lần khám gần nhất</p>
      </div>

      <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
        <div className="flex items-center gap-2.5">
          <Badge variant={conditionMeta.variant}>{conditionMeta.label}</Badge>
          <p className="text-sm text-slate-600">
            {medicalHistory ? 'Có thông tin' : 'Chưa có thông tin'}
          </p>
        </div>
        {medicalHistory && (
          <div className="mt-3 space-y-2 text-sm text-slate-700">
            {typeof medicalHistory.presenting_symptoms === 'object' && medicalHistory.presenting_symptoms && (
              <p>
                <strong>Triệu chứng:</strong> {String(JSON.stringify(medicalHistory.presenting_symptoms) ?? '—')}
              </p>
            )}
            {medicalHistory.onset_age !== undefined && (
              <p>
                <strong>Tuổi khởi phát:</strong> {String(medicalHistory.onset_age) ?? '—'} tuổi
              </p>
            )}
          </div>
        )}
      </div>

      <div className="mt-4">
        <Button variant="outline" size="sm" onClick={() => {}}>
          Sửa thông tin
        </Button>
      </div>
    </Card>
  )
}

// ==================== Section 3: Examinations ====================

export function ExaminationsSection({ patientId, onCreateExam }: {
  patientId?: number
  onCreateExam?: () => void
}) {
  const queryClient = useQueryClient()
  const limit = 10

  const { data: examsResponse, isLoading } = useQuery({
    queryKey: ['exams', patientId],
    queryFn: () => patientId ? listExaminations(patientId, 1, limit) : Promise.resolve(null),
    enabled: !!patientId,
  })

  const deleteMutation = useMutation({
    mutationFn: (examId: number) => patientId ? deleteExamination(patientId, examId) : Promise.reject(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['exams', patientId] })
    },
  })

  const exams = examsResponse?.data || []
  const total = examsResponse?.pagination?.total || 0

  return (
    <Card size="full">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h3 className="text-lg font-semibold text-slate-900">KHÁM BỆNH</h3>
          <p className="mt-1 text-sm text-slate-500">
            {total > 0 ? `Tổng cộng ${total} lần khám` : 'Bệnh nhân có nhiều lần đi khám, dữ liệu sẽ hiển thị dưới dạng bảng'}
          </p>
        </div>
        <div className="flex gap-2.5">
          <Button variant="outline" size="sm" disabled>
            OCR
          </Button>
          <Button variant="outline" size="sm" disabled>
            Upload phiếu khác
          </Button>
          <Button size="sm" onClick={onCreateExam}>
            Nhập bằng tay
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="py-8 text-center text-sm text-slate-500">
          <p>Đang tải...</p>
        </div>
      ) : exams.length === 0 ? (
        <div className="py-8 text-center text-sm text-slate-500">
          <p>Chưa có lần khám nào</p>
        </div>
      ) : (
        <div className="scrollbar-slim overflow-x-auto">
          <table className="w-full min-w-[800px] text-sm">
            <thead className="border-b border-slate-200 bg-slate-50">
              <tr>
                <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
                  Ngày khám
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
                  Toàn thân
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
                  Chẩn đoán
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
                  Điều trị
                </th>
                <th className="px-4 py-2.5 text-center text-xs font-semibold uppercase tracking-wide text-slate-600">
                  Thao tác
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {exams.map((exam: Examination) => (
                <tr key={exam.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 text-slate-900 font-medium">
                    {new Date(exam.exam_date).toLocaleDateString('vi-VN')}
                  </td>
                  <td className="px-4 py-3 text-slate-700 line-clamp-1">
                    {exam.general_condition || '—'}
                  </td>
                  <td className="px-4 py-3 text-slate-700 line-clamp-1">
                    {exam.diagnosis || '—'}
                  </td>
                  <td className="px-4 py-3 text-slate-700 line-clamp-1">
                    {exam.treatment || '—'}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <div className="flex items-center justify-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled
                        title="Chi tiết"
                        className="h-8 w-8 p-0"
                      >
                        <Eye className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => deleteMutation.mutate(exam.id)}
                        disabled={deleteMutation.isPending}
                        title="Xóa"
                        className="h-8 w-8 p-0 text-red-600 hover:text-red-700"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}

// ==================== Helper Components ====================

function DetailRow({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="grid grid-cols-[140px_1fr] items-baseline gap-4">
      <dt className="text-sm font-medium text-slate-600">{label}</dt>
      <dd className="text-sm text-slate-900">{value || '—'}</dd>
    </div>
  )
}

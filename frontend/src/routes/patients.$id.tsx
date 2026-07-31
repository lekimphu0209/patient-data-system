import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createRoute, useNavigate, useParams } from '@tanstack/react-router'
import { useState } from 'react'

import { AppShell } from '@/components/layout/AppShell'
import { Button, Card, ErrorState, FormField, Input, Loading, PageHeader, Select } from '@/components/ui'
import { getPatient, getMedicalHistory, updatePatient } from '@/features/patients/api'
import { detectCondition } from '@/features/patients/constants'
import { ExaminationsSection, MedicalHistorySection } from '@/features/patients/components/PatientDetailSections'
import { requireAuth } from '@/lib/auth-guard'
import { calculateAge, errorMessage, genderLabel } from '@/lib/utils'
import { rootRoute } from '@/routes/__root'
import { AlertCircle, Edit2 } from 'lucide-react'
import { GENDER_OPTIONS } from '@/constants'

export const patientDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/patients/$id',
  component: PatientDetailPage,
  beforeLoad: requireAuth,
})

function PatientDetailPage() {
  const { id } = useParams({ from: patientDetailRoute.id })
  const patientId = Number(id)
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data: patient, isLoading: patientLoading } = useQuery({
    queryKey: ['patient', patientId],
    queryFn: async () => (await getPatient(patientId)).data,
    enabled: !Number.isNaN(patientId),
  })

  const { data: medicalHistoryResponse } = useQuery({
    queryKey: ['medical-history', patientId],
    queryFn: async () => (await getMedicalHistory(patientId)).data,
    enabled: !Number.isNaN(patientId),
  })

  const [editing, setEditing] = useState(false)
  const [formData, setFormData] = useState({
    full_name: patient?.full_name || '',
    birth_date: patient?.birth_date || '',
    hometown: patient?.hometown || '',
    gender: patient?.patient_metadata?.gender || '',
    ethnicity: patient?.patient_metadata?.ethnicity || '',
    education_level: patient?.patient_metadata?.education_level || '',
    occupation: patient?.patient_metadata?.occupation || '',
    residence: patient?.patient_metadata?.residence || '',
    marital_status: patient?.patient_metadata?.marital_status || '',
  })
  const [error, setError] = useState('')

  const updateMutation = useMutation({
    mutationFn: async (data: Record<string, unknown>) => {
      const payload: Record<string, unknown> = {}
      if (typeof data.full_name === 'string') payload.full_name = data.full_name
      if (typeof data.birth_date === 'string') payload.birth_date = data.birth_date
      if (typeof data.hometown === 'string') payload.hometown = data.hometown
      const metadata = {
        ...patient?.patient_metadata,
        gender: data.gender,
        ethnicity: data.ethnicity,
        education_level: data.education_level,
        occupation: data.occupation,
        residence: data.residence,
        marital_status: data.marital_status,
      }
      payload.patient_metadata = metadata
      return await updatePatient(patientId, payload as any)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patient', patientId] })
      setEditing(false)
    },
    onError: (err) => {
      setError(errorMessage(err, 'Cập nhật thất bại'))
    },
  })

  const handleSave = async () => {
    try {
      setError('')
      await updateMutation.mutateAsync(formData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Có lỗi xảy ra')
    }
  }

  if (patientLoading) {
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
        description={`Mã hồ sơ ${patient.patient_code}`}
        backTo="/patients"
      />

      {/* Section 1: Administrative Information */}
      <Card size="full" className="mb-6">
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
            <DetailRow label="Tuổi" value={calculateAge(patient.birth_date) ?? patient.age ?? '—'} />
            <DetailRow label="Giới tính" value={genderLabel(patient.patient_metadata?.gender) || '—'} />
            <DetailRow label="Quê quán/Đơn vị" value={patient.hometown || '—'} />
            <DetailRow label="Ngày vào viện" value={patient.birth_date || '—'} />
            <DetailRow label="Dân tộc" value={patient.patient_metadata?.ethnicity || '—'} />
            <DetailRow label="Trình độ học vấn" value={patient.patient_metadata?.education_level || '—'} />
            <DetailRow label="Nghề nghiệp" value={patient.patient_metadata?.occupation || '—'} />
            <DetailRow label="Nơi thường trú" value={patient.patient_metadata?.residence || '—'} />
            <DetailRow label="Tình trạng hôn nhân" value={patient.patient_metadata?.marital_status || '—'} />
          </div>
        ) : (
          <div className="space-y-4">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <FormField label="Họ và tên" htmlFor="full_name">
                <Input
                  id="full_name"
                  value={formData.full_name}
                  onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                />
              </FormField>
              <FormField label="Tuổi" htmlFor="age">
                <Input type="number" id="age" value={calculateAge(formData.birth_date) ?? ''} disabled />
              </FormField>
            </div>

            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
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
            </div>

            <FormField label="Quê quán/Đơn vị" htmlFor="hometown">
              <Input
                id="hometown"
                value={formData.hometown}
                onChange={(e) => setFormData({ ...formData, hometown: e.target.value })}
              />
            </FormField>

            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <FormField label="Dân tộc" htmlFor="ethnicity">
                <Input
                  id="ethnicity"
                  value={formData.ethnicity}
                  onChange={(e) => setFormData({ ...formData, ethnicity: e.target.value })}
                />
              </FormField>
              <FormField label="Trình độ học vấn" htmlFor="education_level">
                <Input
                  id="education_level"
                  value={formData.education_level}
                  onChange={(e) => setFormData({ ...formData, education_level: e.target.value })}
                />
              </FormField>
            </div>

            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <FormField label="Nghề nghiệp" htmlFor="occupation">
                <Input
                  id="occupation"
                  value={formData.occupation}
                  onChange={(e) => setFormData({ ...formData, occupation: e.target.value })}
                />
              </FormField>
              <FormField label="Nơi thường trú" htmlFor="residence">
                <Input
                  id="residence"
                  value={formData.residence}
                  onChange={(e) => setFormData({ ...formData, residence: e.target.value })}
                />
              </FormField>
            </div>

            <FormField label="Tình trạng hôn nhân" htmlFor="marital_status">
              <Input
                id="marital_status"
                value={formData.marital_status}
                onChange={(e) => setFormData({ ...formData, marital_status: e.target.value })}
              />
            </FormField>

            <div className="flex gap-2.5 border-t border-slate-100 pt-4">
              <Button
                variant="outline"
                onClick={() => {
                  setEditing(false)
                  setError('')
                }}
                disabled={updateMutation.isPending}
              >
                Hủy
              </Button>
              <Button
                isLoading={updateMutation.isPending}
                onClick={handleSave}
              >
                Lưu
              </Button>
            </div>
          </div>
        )}
      </Card>

      {/* Section 2: Medical History */}
      {detectCondition(patient) !== 'normal' && (
        <div className="mb-6">
          <MedicalHistorySection
            patient={patient}
            medicalHistory={medicalHistoryResponse as Record<string, unknown>}
          />
        </div>
      )}

      {/* Section 3: Examinations */}
      <div className="mb-6">
        <ExaminationsSection
          patientId={patientId}
          onCreateExam={() => navigate({ to: '/patients/$id/exams/new', params: { id: String(patientId) } })}
        />
      </div>
    </AppShell>
  )
}

function DetailRow({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div className="grid grid-cols-[140px_1fr] items-baseline gap-4">
      <dt className="text-sm font-medium text-slate-600">{label}</dt>
      <dd className="text-sm text-slate-900">{value || '—'}</dd>
    </div>
  )
}

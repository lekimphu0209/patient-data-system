import { createRoute, useParams } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { type ReactNode } from 'react'
import { Badge, Card, ErrorState, Loading, PageHeader, Section } from '@/components/ui'
import { rootRoute } from '@/routes/__root'
import { requireAuth } from '@/lib/auth-guard'
import { getPatient } from '@/features/patients/api'
import { calculateAge, formatBirthDate, genderLabel } from '@/lib/utils'

export const patientDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/patients/$id',
  component: PatientDetailPage,
  beforeLoad: requireAuth,
})

function displayValue(value: ReactNode) {
  if (value === null || value === undefined || value === '') {
    return '—'
  }
  return value
}

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="grid grid-cols-[minmax(140px,auto)_1fr] gap-4 items-baseline">
      <dt className="text-sm text-gray-500">{label}</dt>
      <dd className="text-sm font-medium text-gray-900 break-words whitespace-pre-wrap">
        {displayValue(value)}
      </dd>
    </div>
  )
}

function PatientDetailPage() {
  const { id } = useParams({ from: patientDetailRoute.id })
  const patientId = Number(id)

  const { data, isLoading } = useQuery({
    queryKey: ['patient', patientId],
    queryFn: async () => {
      const res = await getPatient(patientId)
      return res.data
    },
    enabled: !isNaN(patientId),
  })
  const patient = data

  return (
    <div className="min-h-screen bg-gray-50 p-4 sm:p-6">
      <Card size="md">
        <PageHeader title="Chi tiết bệnh nhân" backTo="/patients" />

        {isLoading ? (
          <Loading text="Đang tải thông tin bệnh nhân..." />
        ) : !patient ? (
          <ErrorState message="Không tìm thấy bệnh nhân." />
        ) : (
          <>
            <Section title="Thông tin cơ bản">
              <DetailRow
                label="Mã bệnh nhân"
                value={patient.patient_code}
              />
              <DetailRow
                label="Họ và tên"
                value={patient.full_name}
              />
              <DetailRow
                label="Ngày sinh"
                value={formatBirthDate(patient.birth_date)}
              />
              <DetailRow
                label="Tuổi"
                value={calculateAge(patient.birth_date) ?? patient.age}
              />
              <DetailRow
                label="Giới tính"
                value={genderLabel(patient.patient_metadata?.gender)}
              />
              <DetailRow
                label="Quê quán"
                value={patient.hometown}
              />
              <DetailRow
                label="Trạng thái"
                value={
                  <Badge variant={patient.status === 'active' ? 'primary' : 'gray'}>
                    {patient.status === 'active' ? 'Hoạt động' : 'Không hoạt động'}
                  </Badge>
                }
              />
            </Section>

            <Section title="Thông tin liên hệ">
              <DetailRow
                label="Số điện thoại"
                value={patient.contact_info?.phone}
              />
              <DetailRow
                label="Người liên hệ"
                value={patient.contact_info?.contact_person}
              />
            </Section>

            <Section title="Thông tin y tế">
              <DetailRow
                label="Chẩn đoán hiện tại"
                value={patient.diagnosis}
              />
              <DetailRow
                label="Ghi chú"
                value={patient.patient_metadata?.notes}
              />
            </Section>
          </>
        )}
      </Card>
    </div>
  )
}

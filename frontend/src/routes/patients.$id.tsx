import { useQuery } from '@tanstack/react-query'
import { createRoute, Link, useParams } from '@tanstack/react-router'
import { Pencil } from 'lucide-react'
import { type ReactNode } from 'react'

import { AppShell } from '@/components/layout/AppShell'
import { Badge, Button, Card, ErrorState, Loading, PageHeader, Section } from '@/components/ui'
import { getPatient } from '@/features/patients/api'
import { CONDITION_META, detectCondition } from '@/features/patients/constants'
import { requireAuth } from '@/lib/auth-guard'
import { calculateAge, formatBirthDate, formatDate, genderLabel, initialsOf } from '@/lib/utils'
import { rootRoute } from '@/routes/__root'

export const patientDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/patients/$id',
  component: PatientDetailPage,
  beforeLoad: requireAuth,
})

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  const empty = value === null || value === undefined || value === ''
  return (
    <div className="grid grid-cols-[minmax(140px,auto)_1fr] items-baseline gap-4">
      <dt className="text-sm text-slate-500">{label}</dt>
      <dd className="whitespace-pre-wrap break-words text-sm font-medium text-slate-900">
        {empty ? '—' : value}
      </dd>
    </div>
  )
}

function PatientDetailPage() {
  const { id } = useParams({ from: patientDetailRoute.id })
  const patientId = Number(id)

  const { data: patient, isLoading } = useQuery({
    queryKey: ['patient', patientId],
    queryFn: async () => (await getPatient(patientId)).data,
    enabled: !Number.isNaN(patientId),
  })

  const condition = patient ? CONDITION_META[detectCondition(patient)] : null

  return (
    <AppShell width="narrow">
      <PageHeader
        title="Chi tiết bệnh nhân"
        description={patient ? `Mã hồ sơ ${patient.patient_code}` : undefined}
        backTo="/patients"
        action={
          patient && (
            <Link to="/patients/$id/edit" params={{ id: String(patient.id) }}>
              <Button leftIcon={<Pencil className="h-4 w-4" />}>Chỉnh sửa</Button>
            </Link>
          )
        }
      />

      {isLoading ? (
        <Card size="full">
          <Loading text="Đang tải thông tin bệnh nhân..." />
        </Card>
      ) : !patient ? (
        <Card size="full">
          <ErrorState message="Không tìm thấy bệnh nhân." />
        </Card>
      ) : (
        <div className="space-y-4">
          <Card size="full">
            <div className="flex flex-wrap items-center gap-4">
              <span className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-brand-100 text-xl font-semibold text-brand-800">
                {initialsOf(patient.full_name)}
              </span>
              <div className="min-w-0 flex-1">
                <h2 className="truncate text-lg font-semibold text-slate-900">
                  {patient.full_name}
                </h2>
                <p className="mt-0.5 text-sm text-slate-500">
                  {patient.patient_code} · {genderLabel(patient.patient_metadata?.gender) ?? '—'} ·{' '}
                  {calculateAge(patient.birth_date) ?? patient.age ?? '—'} tuổi
                </p>
                <div className="mt-2.5 flex flex-wrap items-center gap-2">
                  {condition && (
                    <Badge variant={condition.variant}>{patient.diagnosis || condition.label}</Badge>
                  )}
                  <Badge variant={patient.status === 'active' ? 'success' : 'gray'}>
                    {patient.status === 'active' ? 'Đang hoạt động' : 'Ngừng hoạt động'}
                  </Badge>
                </div>
              </div>
            </div>
          </Card>

          <Card size="full">
            <Section title="Thông tin cơ bản">
              <div className="space-y-3">
                <DetailRow label="Mã bệnh nhân" value={patient.patient_code} />
                <DetailRow label="Họ và tên" value={patient.full_name} />
                <DetailRow label="Ngày sinh" value={formatDate(formatBirthDate(patient.birth_date))} />
                <DetailRow
                  label="Tuổi"
                  value={calculateAge(patient.birth_date) ?? patient.age}
                />
                <DetailRow
                  label="Giới tính"
                  value={genderLabel(patient.patient_metadata?.gender)}
                />
                <DetailRow label="Quê quán" value={patient.hometown} />
              </div>
            </Section>

            <Section title="Thông tin liên hệ">
              <div className="space-y-3">
                <DetailRow label="Số điện thoại" value={patient.contact_info?.phone} />
                <DetailRow label="Người liên hệ" value={patient.contact_info?.contact_person} />
              </div>
            </Section>

            <Section title="Thông tin y tế">
              <div className="space-y-3">
                <DetailRow label="Chẩn đoán hiện tại" value={patient.diagnosis} />
                <DetailRow label="Ghi chú" value={patient.patient_metadata?.notes} />
              </div>
            </Section>
          </Card>
        </div>
      )}
    </AppShell>
  )
}

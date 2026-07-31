import { Link } from '@tanstack/react-router'
import { Eye, Pencil, Trash2, UserPlus, Users } from 'lucide-react'
import { useEffect, useRef } from 'react'

import { Badge, Button, EmptyState } from '@/components/ui'
import { cn } from '@/lib/utils'
import type { Patient } from '../api'
import { CONDITION_META, detectCondition, formatDate } from '../constants'

interface PatientTableProps {
  patients: Patient[]
  isLoading: boolean
  hasFilters: boolean
  selectedIds: Set<number>
  onToggle: (id: number) => void
  onToggleAll: () => void
  onDelete: (patient: Patient) => void
  onCreate: () => void
}

const CHECKBOX_CLASS =
  'h-4 w-4 cursor-pointer rounded border-slate-300 text-brand-700 accent-brand-700 focus:ring-2 focus:ring-brand-600 focus:ring-offset-1'

const TH_CLASS =
  'whitespace-nowrap px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500'

export function PatientTable({
  patients,
  isLoading,
  hasFilters,
  selectedIds,
  onToggle,
  onToggleAll,
  onDelete,
  onCreate,
}: PatientTableProps) {
  const selectedOnPage = patients.filter((p) => selectedIds.has(p.id)).length
  const allSelected = patients.length > 0 && selectedOnPage === patients.length
  const headerCheckbox = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (headerCheckbox.current) {
      headerCheckbox.current.indeterminate = selectedOnPage > 0 && !allSelected
    }
  }, [selectedOnPage, allSelected])

  if (!isLoading && patients.length === 0) {
    return (
      <EmptyState
        icon={<Users className="h-6 w-6" />}
        message={hasFilters ? 'Không tìm thấy bệnh nhân phù hợp' : 'Chưa có bệnh nhân nào'}
        description={
          hasFilters
            ? 'Thử đổi từ khóa tìm kiếm hoặc bỏ bớt bộ lọc chẩn đoán.'
            : 'Thêm bệnh nhân đầu tiên hoặc tải lên danh sách từ file Excel.'
        }
        action={
          hasFilters ? undefined : (
            <Button onClick={onCreate} leftIcon={<UserPlus className="h-4 w-4" />}>
              Thêm bệnh nhân
            </Button>
          )
        }
      />
    )
  }

  return (
    <div className="scrollbar-slim overflow-x-auto">
      <table className="w-full min-w-[900px] border-collapse text-sm">
        <thead className="border-b border-slate-200 bg-slate-50">
          <tr>
            <th scope="col" className="w-12 px-4 py-3 text-center">
              <input
                ref={headerCheckbox}
                type="checkbox"
                checked={allSelected}
                onChange={onToggleAll}
                aria-label="Chọn tất cả bệnh nhân trên trang"
                className={CHECKBOX_CLASS}
              />
            </th>
            <th scope="col" className={cn(TH_CLASS, 'w-40')}>
              Mã bệnh nhân
            </th>
            <th scope="col" className={TH_CLASS}>
              Họ và tên
            </th>
            <th scope="col" className={TH_CLASS}>
              Quê quán
            </th>
            <th scope="col" className={cn(TH_CLASS, 'w-32')}>
              Ngày sinh
            </th>
            <th scope="col" className={TH_CLASS}>
              Chẩn đoán
            </th>
            <th scope="col" className={cn(TH_CLASS, 'w-32 text-center')}>
              Thao tác
            </th>
          </tr>
        </thead>

        <tbody className="divide-y divide-slate-100">
          {isLoading
            ? Array.from({ length: 5 }, (_, i) => (
                <tr key={i}>
                  <td colSpan={7} className="px-4 py-3.5">
                    <div className="h-5 w-full animate-pulse rounded bg-slate-100" />
                  </td>
                </tr>
              ))
            : patients.map((patient) => (
                <PatientRow
                  key={patient.id}
                  patient={patient}
                  selected={selectedIds.has(patient.id)}
                  onToggle={() => onToggle(patient.id)}
                  onDelete={() => onDelete(patient)}
                />
              ))}
        </tbody>
      </table>
    </div>
  )
}

interface PatientRowProps {
  patient: Patient
  selected: boolean
  onToggle: () => void
  onDelete: () => void
}

function PatientRow({ patient, selected, onToggle, onDelete }: PatientRowProps) {
  const condition = detectCondition(patient)
  const meta = CONDITION_META[condition]

  const rowBgClass =
    condition === 'depression'
      ? 'bg-yellow-50'
      : condition === 'schizophrenia'
        ? 'bg-violet-50'
        : ''

  return (
    <tr className={cn('transition-colors hover:opacity-90', rowBgClass, selected && 'ring-2 ring-inset ring-brand-700')}>
      <td className="px-4 py-3 text-center">
        <input
          type="checkbox"
          checked={selected}
          onChange={onToggle}
          aria-label={`Chọn bệnh nhân ${patient.full_name}`}
          className={CHECKBOX_CLASS}
        />
      </td>
      <td className="px-4 py-3">
        <Link
          to="/patients/$id"
          params={{ id: String(patient.id) }}
          className="font-medium text-slate-900 hover:text-brand-700 hover:underline"
        >
          {patient.patient_code}
        </Link>
      </td>
      <td className="px-4 py-3 font-medium text-slate-800">{patient.full_name}</td>
      <td className="px-4 py-3 text-slate-600">{patient.hometown || '—'}</td>
      <td className="px-4 py-3 tabular-nums text-slate-600">{formatDate(patient.birth_date)}</td>
      <td className="px-4 py-3">
        <Badge variant={meta.variant}>{patient.diagnosis || meta.label}</Badge>
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center justify-center gap-1">
          <Link
            to="/patients/$id"
            params={{ id: String(patient.id) }}
            title="Xem chi tiết"
            aria-label={`Xem chi tiết ${patient.full_name}`}
            className="rounded-lg p-2 text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900"
          >
            <Eye className="h-4 w-4" />
          </Link>
          <Link
            to="/patients/$id/edit"
            params={{ id: String(patient.id) }}
            title="Chỉnh sửa"
            aria-label={`Chỉnh sửa ${patient.full_name}`}
            className="rounded-lg p-2 text-slate-500 transition-colors hover:bg-brand-50 hover:text-brand-700"
          >
            <Pencil className="h-4 w-4" />
          </Link>
          <button
            onClick={onDelete}
            title="Xóa"
            aria-label={`Xóa ${patient.full_name}`}
            className="rounded-lg p-2 text-slate-500 transition-colors hover:bg-red-50 hover:text-red-600"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </td>
    </tr>
  )
}

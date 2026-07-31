import { Link } from '@tanstack/react-router'
import { EyeIcon, PencilIcon, TrashIcon } from './icons'
import { CONDITION_META, detectCondition, formatDate } from '../constants'
import type { Patient } from '../api'

interface PatientTableProps {
  patients: Patient[]
  isLoading: boolean
  selectedIds: Set<number>
  onToggle: (id: number) => void
  onToggleAll: () => void
  onDelete: (id: number) => void
}

export function PatientTable({
  patients,
  isLoading,
  selectedIds,
  onToggle,
  onToggleAll,
  onDelete,
}: PatientTableProps) {
  const allSelected = patients.length > 0 && selectedIds.size === patients.length

  return (
    <table className="w-full text-left border-collapse min-w-[800px]">
      <thead>
        <tr className="bg-gray-100 text-sm text-gray-700 font-semibold">
          <th className="p-3 border-b w-14 text-center">
            <input
              type="checkbox"
              checked={allSelected}
              onChange={onToggleAll}
              className="w-5 h-5 accent-teal-600 rounded cursor-pointer"
            />
          </th>
          <th className="p-3 border-b">Mã BN</th>
          <th className="p-3 border-b">Họ và tên</th>
          <th className="p-3 border-b">Quê quán</th>
          <th className="p-3 border-b">Ngày sinh</th>
          <th className="p-3 border-b">Chẩn đoán</th>
          <th className="p-3 border-b">Màu trạng thái</th>
          <th className="p-3 border-b text-center w-40">Thao tác</th>
        </tr>
      </thead>
      <tbody className="text-sm">
        {isLoading ? (
          <>
            {[1, 2, 3].map((n) => (
              <tr key={n}>
                <td colSpan={8} className="p-3 border-b">
                  <div className="h-6 w-full bg-gray-200 rounded animate-pulse" />
                </td>
              </tr>
            ))}
          </>
        ) : patients.length === 0 ? (
          <tr>
            <td colSpan={8} className="p-8 text-center text-gray-500 border-b">
              Không có dữ liệu
            </td>
          </tr>
        ) : (
          patients.map((patient) => (
            <PatientRow
              key={patient.id}
              patient={patient}
              selected={selectedIds.has(patient.id)}
              onToggle={() => onToggle(patient.id)}
              onDelete={() => onDelete(patient.id)}
            />
          ))
        )}
      </tbody>
    </table>
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
  const rowBg = meta.bg || 'bg-white'

  return (
    <tr className={`${rowBg} border-b hover:opacity-90 transition`}>
      <td className="p-3 text-center border-b">
        <input
          type="checkbox"
          checked={selected}
          onChange={onToggle}
          className="w-5 h-5 accent-teal-600 rounded cursor-pointer"
        />
      </td>
      <td className="p-3 font-medium text-gray-900 border-b">{patient.patient_code}</td>
      <td className="p-3 border-b">{patient.full_name}</td>
      <td className="p-3 border-b">{patient.hometown || '-'}</td>
      <td className="p-3 border-b">{formatDate(patient.birth_date)}</td>
      <td className="p-3 border-b">{patient.diagnosis || '-'}</td>
      <td className="p-3 border-b">
        <div className="flex items-center gap-2">
          {condition !== 'normal' && (
            <span className={`inline-block w-3 h-3 rounded-full ${meta.dot}`} />
          )}
          <span className={`text-xs font-medium ${meta.textColor}`}>{meta.text}</span>
        </div>
      </td>
      <td className="p-3 border-b">
        <div className="flex items-center justify-center gap-2">
          <Link
            to="/patients/$id"
            params={{ id: String(patient.id) }}
            title="Xem"
            className="p-1.5 rounded-lg text-gray-600 hover:bg-gray-100 hover:text-blue-600 transition"
          >
            <EyeIcon className="w-5 h-5" />
          </Link>
          <Link
            to="/patients/$id/edit"
            params={{ id: String(patient.id) }}
            title="Sửa"
            className="p-1.5 rounded-lg text-gray-600 hover:bg-gray-100 hover:text-teal-600 transition"
          >
            <PencilIcon className="w-5 h-5" />
          </Link>
          <button
            onClick={onDelete}
            title="Xóa"
            className="p-1.5 rounded-lg text-gray-600 hover:bg-gray-100 hover:text-red-600 transition"
          >
            <TrashIcon className="w-5 h-5" />
          </button>
        </div>
      </td>
    </tr>
  )
}

import { Button, Input, Select } from '@/components/ui'
import { SearchIcon, ExportIcon, TrashIcon } from './icons'
import { DIAGNOSIS_OPTIONS } from '../constants'

interface PatientToolbarProps {
  search: string
  onSearchChange: (value: string) => void
  diagnosis: string
  onDiagnosisChange: (value: string) => void
  birthDateFrom: string
  onBirthDateFromChange: (value: string) => void
  birthDateTo: string
  onBirthDateToChange: (value: string) => void
  onSearch: () => void
  selectedCount: number
  onExport: () => void
  onDelete: () => void
}

export function PatientToolbar({
  search,
  onSearchChange,
  diagnosis,
  onDiagnosisChange,
  birthDateFrom,
  onBirthDateFromChange,
  birthDateTo,
  onBirthDateToChange,
  onSearch,
  selectedCount,
  onExport,
  onDelete,
}: PatientToolbarProps) {
  return (
    <div className="mt-4 bg-white border border-gray-200 rounded-xl shadow-sm p-4 flex flex-col md:flex-row md:items-stretch md:justify-between gap-4">
      <div className="flex flex-1 flex-wrap items-stretch gap-4">
        <div className="flex flex-col justify-between flex-1 min-w-[220px]">
          <label className="text-xs font-medium text-gray-600">Từ khóa</label>
          <Input
            type="text"
            placeholder="Nhập mã, tên hoặc chẩn đoán..."
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
          />
        </div>

        <div className="flex flex-col justify-between w-40">
          <label className="text-xs font-medium text-gray-600">Chẩn đoán</label>
          <Select
            value={diagnosis}
            onChange={(e) => onDiagnosisChange(e.target.value)}
            options={DIAGNOSIS_OPTIONS}
          />
        </div>

        <div className="flex flex-col justify-between w-80 min-w-[18rem]">
          <label className="text-xs font-medium text-gray-600">Khoảng ngày sinh</label>
          <div className="flex items-center gap-2 min-w-0">
            <div className="flex-1 min-w-[120px]">
              <Input
                type="date"
                value={birthDateFrom}
                onChange={(e) => onBirthDateFromChange(e.target.value)}
                title="Từ ngày (dd/MM/yyyy)"
              />
            </div>
            <span className="text-gray-400">-</span>
            <div className="flex-1 min-w-[120px]">
              <Input
                type="date"
                value={birthDateTo}
                onChange={(e) => onBirthDateToChange(e.target.value)}
                title="Đến ngày (dd/MM/yyyy)"
              />
            </div>
          </div>
        </div>

        <div className="flex flex-col justify-end min-w-[100px]">
          <Button onClick={onSearch} leftIcon={<SearchIcon className="w-4 h-4" />}>
            Tìm kiếm
          </Button>
        </div>
      </div>

      <div className="flex items-end justify-end gap-3 shrink-0">
        <Button
          onClick={onExport}
          disabled={selectedCount === 0}
          variant="secondary"
          leftIcon={<ExportIcon className="w-4 h-4" />}
        >
          Xuất dữ liệu
        </Button>
        <Button
          onClick={onDelete}
          disabled={selectedCount === 0}
          variant="danger"
          leftIcon={<TrashIcon className="w-4 h-4" />}
        >
          Xóa dữ liệu
        </Button>
      </div>
    </div>
  )
}

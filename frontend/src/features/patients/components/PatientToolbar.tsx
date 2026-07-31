import { Download, Search, Trash2, X } from 'lucide-react'

import { Button, Input, Select } from '@/components/ui'
import { DIAGNOSIS_OPTIONS } from '../constants'

interface PatientToolbarProps {
  search: string
  onSearchChange: (value: string) => void
  diagnosis: string
  onDiagnosisChange: (value: string) => void
  selectedCount: number
  exporting: boolean
  onExport: () => void
  onDelete: () => void
}

export function PatientToolbar({
  search,
  onSearchChange,
  diagnosis,
  onDiagnosisChange,
  selectedCount,
  exporting,
  onExport,
  onDelete,
}: PatientToolbarProps) {
  const hasSelection = selectedCount > 0

  return (
    <div className="flex flex-col gap-3 border-b border-slate-200 px-4 py-3 lg:flex-row lg:items-center lg:justify-between">
      {/* Filters apply as you type / pick — there is no separate search button. */}
      <div className="flex flex-1 flex-wrap items-center gap-2.5">
        <div className="min-w-[240px] flex-1 sm:max-w-md">
          <Input
            type="search"
            placeholder="Tìm theo mã, họ tên hoặc chẩn đoán..."
            aria-label="Tìm kiếm bệnh nhân"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            leftIcon={<Search className="h-4 w-4" />}
            rightSlot={
              search ? (
                <button
                  type="button"
                  onClick={() => onSearchChange('')}
                  aria-label="Xóa từ khóa"
                  className="pointer-events-auto rounded p-1 transition-colors hover:text-slate-600"
                >
                  <X className="h-4 w-4" />
                </button>
              ) : undefined
            }
          />
        </div>

        <div className="w-full sm:w-56">
          <Select
            aria-label="Lọc theo chẩn đoán"
            value={diagnosis}
            onChange={(e) => onDiagnosisChange(e.target.value)}
            options={DIAGNOSIS_OPTIONS}
          />
        </div>
      </div>

      <div className="flex items-center gap-2.5">
        {/* Only meaningful with a selection, so it stays out of the way until then. */}
        {hasSelection && (
          <>
            <span className="hidden text-sm text-slate-500 sm:inline">
              Đã chọn <span className="font-semibold text-slate-900">{selectedCount}</span>
            </span>
            <Button
              onClick={onDelete}
              variant="danger"
              leftIcon={<Trash2 className="h-4 w-4" />}
            >
              Xóa dữ liệu
            </Button>
          </>
        )}

        <Button
          onClick={onExport}
          variant="outline"
          isLoading={exporting}
          leftIcon={<Download className="h-4 w-4" />}
          title={
            hasSelection
              ? `Xuất ${selectedCount} bệnh nhân đã chọn`
              : 'Xuất toàn bộ dữ liệu theo bộ lọc hiện tại'
          }
        >
          Xuất dữ liệu
        </Button>
      </div>
    </div>
  )
}

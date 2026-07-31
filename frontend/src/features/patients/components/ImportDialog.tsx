import {
  AlertCircle,
  CheckCircle2,
  Download,
  FileSpreadsheet,
  Upload,
  XCircle,
} from 'lucide-react'
import { useRef, useState } from 'react'

import { Button, Modal } from '@/components/ui'
import { cn } from '@/lib/utils'
import type { ImportPreviewResponse } from '../api'

interface ImportDialogProps {
  loading: boolean
  error: string
  successMessage: string
  fileName: string
  preview: ImportPreviewResponse | null
  onClose: () => void
  onFileSelected: (file: File) => void
  onCommit: () => void
  onReset: () => void
  onDownloadTemplate: () => void
  templateLoading: boolean
}

const TEMPLATE_COLUMNS = [
  'Mã bệnh nhân *',
  'Họ và tên *',
  'Ngày sinh',
  'Giới tính',
  'Quê quán',
  'Số điện thoại',
  'Người liên hệ',
  'Chẩn đoán',
  'Ghi chú',
]

export function ImportDialog({
  loading,
  error,
  successMessage,
  fileName,
  preview,
  onClose,
  onFileSelected,
  onCommit,
  onReset,
  onDownloadTemplate,
  templateLoading,
}: ImportDialogProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  const pickFile = (file: File | undefined | null) => {
    if (file) onFileSelected(file)
  }

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title="Tải dữ liệu bệnh nhân từ file"
      description="Hỗ trợ file Excel (.xlsx) và CSV. Hệ thống sẽ kiểm tra dữ liệu trước khi lưu."
      footer={
        preview ? (
          <>
            <Button variant="outline" onClick={onReset} disabled={loading}>
              Chọn file khác
            </Button>
            <Button
              onClick={onCommit}
              isLoading={loading}
              disabled={preview.valid_count === 0}
              leftIcon={<CheckCircle2 className="h-4 w-4" />}
            >
              Nhập {preview.valid_count} dòng hợp lệ
            </Button>
          </>
        ) : (
          <Button variant="outline" onClick={onClose}>
            Đóng
          </Button>
        )
      }
    >
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-brand-100 bg-brand-50/60 px-4 py-3">
          <div className="flex min-w-0 items-start gap-2.5">
            <FileSpreadsheet className="mt-0.5 h-5 w-5 shrink-0 text-brand-700" />
            <div className="min-w-0">
              <p className="text-sm font-medium text-slate-900">Chưa có file mẫu?</p>
              <p className="text-sm text-slate-600">
                Tải file mẫu tiếng Việt kèm hướng dẫn và ví dụ điền sẵn.
              </p>
            </div>
          </div>
          <Button
            variant="subtle"
            onClick={onDownloadTemplate}
            isLoading={templateLoading}
            leftIcon={<Download className="h-4 w-4" />}
          >
            Tải file mẫu
          </Button>
        </div>

        {!preview && (
          <>
            <div
              onDragOver={(e) => {
                e.preventDefault()
                setDragging(true)
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault()
                setDragging(false)
                pickFile(e.dataTransfer.files?.[0])
              }}
              className={cn(
                'flex flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors',
                dragging ? 'border-brand-500 bg-brand-50' : 'border-slate-300 bg-slate-50'
              )}
            >
              <span className="mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-white text-slate-500 shadow-sm">
                <Upload className="h-5 w-5" />
              </span>
              <p className="text-sm font-medium text-slate-800">
                Kéo thả file vào đây hoặc chọn từ máy tính
              </p>
              <p className="mt-1 text-sm text-slate-500">Định dạng .xlsx hoặc .csv, tối đa 5MB</p>

              <input
                ref={inputRef}
                type="file"
                accept=".xlsx,.csv"
                className="hidden"
                onChange={(e) => {
                  pickFile(e.target.files?.[0])
                  e.target.value = ''
                }}
              />
              <Button
                className="mt-4"
                variant="outline"
                onClick={() => inputRef.current?.click()}
                isLoading={loading}
              >
                Chọn file
              </Button>
              {fileName && !loading && (
                <p className="mt-3 text-sm text-slate-600">
                  Đã chọn: <span className="font-medium text-slate-900">{fileName}</span>
                </p>
              )}
            </div>

            <div className="rounded-lg border border-slate-200 bg-white px-4 py-3">
              <p className="text-sm font-medium text-slate-800">Các cột trong file</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {TEMPLATE_COLUMNS.map((column) => (
                  <span
                    key={column}
                    className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600"
                  >
                    {column}
                  </span>
                ))}
              </div>
              <p className="mt-2.5 text-xs text-slate-500">
                Cột đánh dấu <span className="font-medium text-red-600">*</span> là bắt buộc. Các cột
                còn lại có thể bỏ trống.
              </p>
            </div>
          </>
        )}

        {error && (
          <div className="flex items-start gap-2.5 rounded-lg border border-red-200 bg-red-50 px-3.5 py-3 text-sm text-red-700">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {successMessage && (
          <div className="flex items-start gap-2.5 rounded-lg border border-emerald-200 bg-emerald-50 px-3.5 py-3 text-sm text-emerald-700">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{successMessage}</span>
          </div>
        )}

        {preview && <ImportPreviewPanel preview={preview} fileName={fileName} />}
      </div>
    </Modal>
  )
}

function ImportPreviewPanel({
  preview,
  fileName,
}: {
  preview: ImportPreviewResponse
  fileName: string
}) {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
        <SummaryTile label="Tổng số dòng" value={preview.rows.length} tone="neutral" />
        <SummaryTile label="Hợp lệ" value={preview.valid_count} tone="success" />
        <SummaryTile label="Có lỗi" value={preview.invalid_count} tone="danger" />
      </div>

      {fileName && (
        <p className="text-sm text-slate-500">
          Kết quả kiểm tra file <span className="font-medium text-slate-800">{fileName}</span>. Chỉ
          các dòng hợp lệ được ghi vào hệ thống.
        </p>
      )}

      <div className="scrollbar-slim max-h-72 overflow-auto rounded-lg border border-slate-200">
        <table className="w-full min-w-[640px] text-sm">
          <thead className="sticky top-0 bg-slate-50">
            <tr className="border-b border-slate-200">
              <th className="w-16 px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                Dòng
              </th>
              <th className="px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                Mã bệnh nhân
              </th>
              <th className="px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                Họ và tên
              </th>
              <th className="px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                Trạng thái
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {preview.rows.map((row) => (
              <tr key={row.row} className={row.valid ? undefined : 'bg-red-50/50'}>
                <td className="px-3 py-2.5 tabular-nums text-slate-500">{row.row}</td>
                <td className="px-3 py-2.5 font-medium text-slate-800">
                  {String(row.data.patient_code || '—')}
                </td>
                <td className="px-3 py-2.5 text-slate-700">
                  {String(row.data.full_name || '—')}
                </td>
                <td className="px-3 py-2.5">
                  {row.valid ? (
                    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-emerald-700">
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      Hợp lệ
                    </span>
                  ) : (
                    <span className="inline-flex items-start gap-1.5 text-xs font-medium text-red-700">
                      <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                      <span>{row.errors.join('; ')}</span>
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function SummaryTile({
  label,
  value,
  tone,
}: {
  label: string
  value: number
  tone: 'neutral' | 'success' | 'danger'
}) {
  const tones = {
    neutral: 'border-slate-200 bg-slate-50 text-slate-900',
    success: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    danger: 'border-red-200 bg-red-50 text-red-700',
  }

  return (
    <div className={cn('rounded-lg border px-3.5 py-2.5', tones[tone])}>
      <p className="text-xs font-medium opacity-80">{label}</p>
      <p className="mt-0.5 text-xl font-semibold tabular-nums">{value}</p>
    </div>
  )
}

import { Button, Modal } from '@/components/ui'
import { cn } from '@/lib/utils'
import type { ImportPreviewResponse } from '../api'

interface ImportDialogProps {
  loading: boolean
  message: string
  preview: ImportPreviewResponse | null
  onClose: () => void
  onFileChange: (e: React.ChangeEvent<HTMLInputElement>) => void
  onCommit: () => void
  onDownloadTemplate?: () => void
}

export function ImportDialog({
  loading,
  message,
  preview,
  onClose,
  onFileChange,
  onCommit,
  onDownloadTemplate,
}: ImportDialogProps) {
  return (
    <Modal
      open={true}
      title={preview ? 'Kết quả nhập dữ liệu' : 'Nhập bệnh nhân từ file'}
      onClose={onClose}
      size="md"
    >
      <div className="mb-4">
        <div className="flex items-center justify-between mb-1">
          <label className="block text-sm font-medium">Chọn file Excel/CSV</label>
          {onDownloadTemplate && (
            <Button
              type="button"
              onClick={onDownloadTemplate}
              disabled={loading}
              variant="ghost"
              size="sm"
            >
              Tải file mẫu
            </Button>
          )}
        </div>
        <input
          type="file"
          accept=".xlsx,.csv"
          onChange={onFileChange}
          disabled={loading}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
        />
        <p className="text-xs text-gray-500 mt-1">
          File phải có các cột: patient_code, full_name. Các cột tùy chọn: birth_date, hometown, age, gender, disease_type, diagnosis, status, phone, contact_person, notes.
        </p>
      </div>

      {loading && (
        <div className="flex items-center gap-2 text-blue-600 mb-4">
          <span className="inline-block w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
          Đang xử lý...
        </div>
      )}

      {message && (
        <div
          className={cn(
            'mb-4 p-3 rounded-lg text-sm',
            message.includes('thành công')
              ? 'bg-green-100 text-green-800'
              : 'bg-red-100 text-red-800'
          )}
        >
          {message}
        </div>
      )}

      {preview && (
        <>
          <div className="flex gap-4 mb-3 text-sm">
            <span className="text-green-700 font-medium">Hợp lệ: {preview.valid_count}</span>
            <span className="text-red-700 font-medium">Lỗi: {preview.invalid_count}</span>
          </div>

          {preview.rows.length > 0 && (
            <div className="overflow-x-auto border rounded-lg mb-4 max-h-64">
              <table className="w-full text-sm text-left">
                <thead className="bg-gray-100 sticky top-0">
                  <tr>
                    <th className="p-2">Dòng</th>
                    <th className="p-2">Mã BN</th>
                    <th className="p-2">Họ tên</th>
                    <th className="p-2">Quê quán</th>
                    <th className="p-2">Lỗi</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.rows.map((row) => (
                    <tr key={row.row} className="border-b">
                      <td className="p-2">{row.row}</td>
                      <td className="p-2">{String(row.data.patient_code || '-')}</td>
                      <td className="p-2">{String(row.data.full_name || '-')}</td>
                      <td className="p-2">{String(row.data.hometown || '-')}</td>
                      <td className="p-2 text-red-600 text-xs">
                        {row.errors.length > 0 ? row.errors.join(', ') : 'OK'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="flex justify-end gap-3">
            <Button onClick={onClose} variant="outline">
              Hủy
            </Button>
            <Button
              onClick={onCommit}
              disabled={loading || preview.valid_count === 0}
              isLoading={loading}
              variant="secondary"
            >
              Nhập dữ liệu
            </Button>
          </div>
        </>
      )}
    </Modal>
  )
}

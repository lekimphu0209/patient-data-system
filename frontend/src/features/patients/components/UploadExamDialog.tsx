import { useMutation } from '@tanstack/react-query'
import { AlertCircle, FileText, Loader2, ScanLine, Upload } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { Button, Modal } from '@/components/ui'
import { errorMessage } from '@/lib/utils'
import { extractExamDocument, type ExtractionDraft, type ExtractionMode } from '../api'

const MODE_META: Record<
  ExtractionMode,
  { title: string; description: string; accept: string; hint: string; icon: typeof ScanLine }
> = {
  ocr: {
    title: 'OCR phiếu khám',
    description: 'Dành cho ảnh chụp hoặc bản scan — AI đọc chữ và các ô đã tích trên giấy.',
    accept: '.jpg,.jpeg,.png,.webp,.tif,.tiff,.pdf',
    hint: 'Ảnh JPG/PNG/TIFF hoặc PDF scan. Ảnh càng rõ nét thì đọc càng chính xác.',
    icon: ScanLine,
  },
  upload: {
    title: 'Upload phiếu khám',
    description: 'Dành cho file văn bản — đọc trực tiếp nội dung, nhanh và chính xác hơn OCR.',
    accept: '.docx,.pdf',
    hint: 'File Word (.docx) hoặc PDF xuất từ văn bản.',
    icon: FileText,
  },
}

export function UploadExamDialog({
  open,
  mode,
  patientId,
  onClose,
  onExtracted,
}: {
  open: boolean
  mode: ExtractionMode
  patientId: number
  onClose: () => void
  onExtracted: (draft: ExtractionDraft) => void
}) {
  const meta = MODE_META[mode]
  const Icon = meta.icon
  const [file, setFile] = useState<File | null>(null)
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!open) {
      setFile(null)
      setError('')
      setDragging(false)
    }
  }, [open])

  const mutation = useMutation({
    mutationFn: () => extractExamDocument(patientId, file!, mode),
    onSuccess: onExtracted,
    onError: (err) => setError(errorMessage(err, 'Bóc tách thất bại')),
  })

  const busy = mutation.isPending

  return (
    <Modal
      open={open}
      onClose={busy ? () => {} : onClose}
      title={meta.title}
      description={meta.description}
      footer={
        <div className="flex justify-end gap-2.5">
          <Button variant="outline" onClick={onClose} disabled={busy}>
            Hủy
          </Button>
          <Button onClick={() => mutation.mutate()} disabled={!file || busy} isLoading={busy}>
            {busy ? 'Đang xử lý...' : 'Bóc tách'}
          </Button>
        </div>
      }
    >
      {busy ? (
        <div className="flex flex-col items-center gap-3 py-10 text-center">
          <Loader2 className="h-8 w-8 animate-spin text-brand-600" />
          <p className="text-sm font-medium text-slate-900">AI đang đọc phiếu khám...</p>
          <p className="max-w-sm text-sm text-slate-500">
            Việc này có thể mất từ vài giây đến vài phút tùy độ dài tài liệu. Đừng đóng cửa sổ.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {error && (
            <div className="flex items-start gap-2.5 rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-700">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault()
              setDragging(true)
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault()
              setDragging(false)
              const dropped = e.dataTransfer.files?.[0]
              if (dropped) {
                setFile(dropped)
                setError('')
              }
            }}
            className={`flex w-full flex-col items-center gap-2 rounded-xl border-2 border-dashed px-6 py-10 transition-colors ${
              dragging
                ? 'border-brand-500 bg-brand-50'
                : 'border-slate-300 bg-slate-50 hover:border-brand-400 hover:bg-brand-50/40'
            }`}
          >
            <Icon className="h-8 w-8 text-slate-400" />
            {file ? (
              <>
                <span className="text-sm font-medium text-slate-900">{file.name}</span>
                <span className="text-xs text-slate-500">
                  {(file.size / 1024 / 1024).toFixed(2)} MB — bấm để chọn file khác
                </span>
              </>
            ) : (
              <>
                <span className="text-sm font-medium text-slate-900">
                  Kéo thả file vào đây hoặc bấm để chọn
                </span>
                <span className="text-xs text-slate-500">{meta.hint}</span>
              </>
            )}
          </button>

          <input
            ref={inputRef}
            type="file"
            accept={meta.accept}
            className="hidden"
            onChange={(e) => {
              const picked = e.target.files?.[0]
              if (picked) {
                setFile(picked)
                setError('')
              }
              e.target.value = ''
            }}
          />

          <p className="flex items-start gap-2 text-xs text-slate-500">
            <Upload className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            Sau khi xử lý xong bạn sẽ được đưa sang màn hình soát lại để đối chiếu với bản gốc
            trước khi lưu. Chưa có gì được ghi vào hồ sơ ở bước này.
          </p>
        </div>
      )}
    </Modal>
  )
}

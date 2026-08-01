/**
 * Khung xem file gốc ở màn hình soát.
 *
 * File tải qua axios (kèm token) rồi dựng object URL, vì thẻ <img>/<iframe>
 * không gửi được header Authorization.
 *
 * Trình duyệt không render được .docx, nên file Word được chuyển sang HTML bằng
 * mammoth ngay tại client — giữ chữ, bảng, đậm/nghiêng; mất bố cục chính xác.
 */

import { useQuery } from '@tanstack/react-query'
import { AlertCircle, Download, Maximize2, ZoomIn, ZoomOut } from 'lucide-react'
import { useEffect, useState } from 'react'

import { Loading } from '@/components/ui'
import { downloadBlob, errorMessage } from '@/lib/utils'
import { fetchDocumentBlob } from '../api'

type PreviewKind = 'image' | 'pdf' | 'docx' | 'unknown'

function detectKind(fileName: string, mimeType: string): PreviewKind {
  const name = fileName.toLowerCase()
  if (mimeType.startsWith('image/') || /\.(jpe?g|png|webp|gif|bmp|tiff?)$/.test(name)) {
    return 'image'
  }
  if (mimeType === 'application/pdf' || name.endsWith('.pdf')) return 'pdf'
  if (name.endsWith('.docx') || mimeType.includes('wordprocessingml')) return 'docx'
  return 'unknown'
}

export function DocumentPreview({
  patientId,
  documentId,
  fileName,
  mimeType,
}: {
  patientId: number
  documentId: number
  fileName: string
  mimeType: string
}) {
  const kind = detectKind(fileName, mimeType)
  const [objectUrl, setObjectUrl] = useState<string>('')
  const [docxHtml, setDocxHtml] = useState<string>('')
  const [convertError, setConvertError] = useState('')
  // Ảnh scan bệnh án chữ nhỏ, vừa khung thì không đọc nổi -> cần phóng to.
  const [zoom, setZoom] = useState(1)

  const { data: blob, isLoading, error } = useQuery({
    queryKey: ['document-blob', patientId, documentId],
    queryFn: () => fetchDocumentBlob(patientId, documentId),
    staleTime: Infinity,
  })

  useEffect(() => {
    if (!blob || kind === 'docx') return
    const url = URL.createObjectURL(blob)
    setObjectUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [blob, kind])

  useEffect(() => {
    if (!blob || kind !== 'docx') return
    let cancelled = false
    blob
      .arrayBuffer()
      .then((buffer) => import('mammoth').then((mammoth) => mammoth.convertToHtml({ arrayBuffer: buffer })))
      .then((result) => {
        if (!cancelled) setDocxHtml(result.value)
      })
      .catch((err) => {
        if (!cancelled) setConvertError(errorMessage(err, 'Không hiển thị được nội dung file Word'))
      })
    return () => {
      cancelled = true
    }
  }, [blob, kind])

  if (isLoading) return <Loading text="Đang tải file gốc..." />

  if (error || !blob) {
    return (
      <div className="flex items-start gap-2.5 rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-700">
        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
        <span>{errorMessage(error, 'Không tải được file gốc')}</span>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="min-w-0 truncate text-sm font-medium text-slate-700" title={fileName}>
          {fileName}
        </p>

        <div className="flex shrink-0 items-center gap-1">
          {kind === 'image' && (
            <>
              <IconButton
                label="Thu nhỏ"
                onClick={() => setZoom((z) => Math.max(0.5, z - 0.25))}
                disabled={zoom <= 0.5}
              >
                <ZoomOut className="h-3.5 w-3.5" />
              </IconButton>
              <span className="w-10 text-center text-xs tabular-nums text-slate-500">
                {Math.round(zoom * 100)}%
              </span>
              <IconButton
                label="Phóng to"
                onClick={() => setZoom((z) => Math.min(4, z + 0.25))}
                disabled={zoom >= 4}
              >
                <ZoomIn className="h-3.5 w-3.5" />
              </IconButton>
              <IconButton label="Vừa khung" onClick={() => setZoom(1)}>
                <Maximize2 className="h-3.5 w-3.5" />
              </IconButton>
            </>
          )}
          <IconButton label="Tải về" onClick={() => downloadBlob(blob, fileName)}>
            <Download className="h-3.5 w-3.5" />
          </IconButton>
        </div>
      </div>

      <div className="scrollbar-slim min-h-0 flex-1 overflow-auto rounded-lg border border-slate-200 bg-slate-100">
        {kind === 'image' && objectUrl && (
          <img
            src={objectUrl}
            alt={fileName}
            className="max-w-none"
            style={{ width: `${zoom * 100}%` }}
          />
        )}

        {kind === 'pdf' && objectUrl && (
          <iframe src={objectUrl} title={fileName} className="h-full min-h-full w-full" />
        )}

        {kind === 'docx' &&
          (convertError ? (
            <p className="p-4 text-sm text-red-700">{convertError}</p>
          ) : docxHtml ? (
            <div
              className="docx-preview space-y-2 bg-white p-4 text-sm leading-relaxed text-slate-800"
              dangerouslySetInnerHTML={{ __html: docxHtml }}
            />
          ) : (
            <Loading text="Đang dựng nội dung file Word..." />
          ))}

        {kind === 'unknown' && (
          <p className="p-4 text-sm text-slate-500">
            Không xem trước được định dạng này. Bấm “Tải về” để mở bằng ứng dụng ngoài.
          </p>
        )}
      </div>
    </div>
  )
}

function IconButton({
  children,
  label,
  onClick,
  disabled,
}: {
  children: React.ReactNode
  label: string
  onClick: () => void
  disabled?: boolean
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={label}
      aria-label={label}
      className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-600 transition-colors hover:bg-slate-50 hover:text-slate-900 disabled:pointer-events-none disabled:opacity-40"
    >
      {children}
    </button>
  )
}

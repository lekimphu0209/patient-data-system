import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertCircle, Download, Edit2, Eye, FileText, ScanLine, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'

import { Badge, Button, Card, Loading } from '@/components/ui'
import { errorMessage } from '@/lib/utils'
import {
  deleteExamination,
  exportExaminations,
  getMedicalHistory,
  listExaminations,
  updateMedicalHistory,
  type Examination,
  type ExtractionMode,
  type FormNode,
  type FormSchema,
  type FormValues,
} from '../api'
import { DynamicForm, summarizeGroup } from './DynamicForm'
import { Pagination } from './Pagination'
import { UploadExamDialog } from './UploadExamDialog'

const findBlock = (schema: FormSchema | undefined, id: string) =>
  schema?.blocks.find((block) => block.id === id)

// ==================== Khối 2: HỎI BỆNH ====================

export function MedicalHistorySection({
  patientId,
  schema,
}: {
  patientId: number
  schema: FormSchema | undefined
}) {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [values, setValues] = useState<FormValues>({})
  const [error, setError] = useState('')

  const block = findBlock(schema, 'medical_history')

  const { data: history, isLoading } = useQuery({
    queryKey: ['medical-history', patientId],
    queryFn: async () => (await getMedicalHistory(patientId)).data,
    enabled: !!block,
  })

  // Đồng bộ giá trị đã lưu vào state khi tải xong / khi mở lại chế độ sửa.
  useEffect(() => {
    if (!editing) setValues(history?.data ?? {})
  }, [history, editing])

  const saveMutation = useMutation({
    mutationFn: (next: FormValues) => updateMedicalHistory(patientId, { data: next }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['medical-history', patientId] })
      setEditing(false)
      setError('')
    },
    onError: (err) => setError(errorMessage(err, 'Lưu thông tin hỏi bệnh thất bại')),
  })

  // Bệnh nhân bình thường: backend không trả khối này → không hiển thị.
  if (!block) return null

  return (
    <Card size="full">
      <div className="mb-6 flex items-start justify-between gap-4">
        <h3 className="text-lg font-semibold text-slate-900">{block.label}</h3>
        {!editing && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setEditing(true)}
            leftIcon={<Edit2 className="h-4 w-4" />}
          >
            Sửa
          </Button>
        )}
      </div>

      {error && (
        <div className="mb-4 flex items-start gap-2.5 rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-700">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {isLoading ? (
        <Loading text="Đang tải thông tin hỏi bệnh..." />
      ) : (
        <>
          <DynamicForm
            block={block}
            values={values}
            onChange={setValues}
            mode={editing ? 'edit' : 'view'}
          />

          {editing && (
            <div className="mt-6 flex gap-2.5 border-t border-slate-100 pt-4">
              <Button
                variant="outline"
                onClick={() => {
                  setValues(history?.data ?? {})
                  setEditing(false)
                  setError('')
                }}
                disabled={saveMutation.isPending}
              >
                Hủy
              </Button>
              <Button isLoading={saveMutation.isPending} onClick={() => saveMutation.mutate(values)}>
                Lưu
              </Button>
            </div>
          )}
        </>
      )}
    </Card>
  )
}

// ==================== Khối 3: KHÁM BỆNH ====================

/** Nội dung một ô của bảng lần khám, suy ra từ schema chứ không hard-code. */
function examCell(exam: Examination, columnKey: string, block: FormNode | undefined): string {
  const data = exam.data ?? {}

  if (columnKey === 'exam_info.exam_date') {
    return exam.exam_date ? new Date(exam.exam_date).toLocaleDateString('vi-VN') : ''
  }

  const node = block?.children?.find((child) => child.id === columnKey)
  if (node) {
    const summary = summarizeGroup(node, data[columnKey])
    if (summary) return summary
  }

  // Dữ liệu tạo trước khi có form động vẫn nằm ở các cột rời.
  const legacy: Record<string, unknown> = {
    general: exam.general_condition,
    cardiovascular: exam.cardiovascular,
    respiratory: exam.respiratory,
    digestive: exam.digestive,
    urinary: exam.urinary,
    neurological: exam.neurological,
    other_body_parts: exam.other_body_parts,
    diagnosis: exam.diagnosis,
    treatment: exam.treatment,
  }
  return legacy[columnKey] ? String(legacy[columnKey]) : ''
}

export function ExaminationsSection({
  patientId,
  schema,
  onCreateExam,
  onViewExam,
  onEditExam,
  onReviewExtraction,
}: {
  patientId: number
  schema: FormSchema | undefined
  onCreateExam: () => void
  onViewExam: (examId: number) => void
  onEditExam: (examId: number) => void
  onReviewExtraction: (extractionId: number) => void
}) {
  const queryClient = useQueryClient()
  const block = findBlock(schema, 'examination')
  const columns = schema?.exam_table_columns ?? []

  const [page, setPage] = useState(1)
  const [limit, setLimit] = useState(10)
  const [exportError, setExportError] = useState('')
  const [uploadMode, setUploadMode] = useState<ExtractionMode | null>(null)

  const { data: response, isLoading } = useQuery({
    queryKey: ['exams', patientId, page, limit],
    queryFn: () => listExaminations(patientId, page, limit),
  })

  const deleteMutation = useMutation({
    mutationFn: (examId: number) => deleteExamination(patientId, examId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['exams', patientId] }),
  })

  const exportMutation = useMutation({
    mutationFn: () => exportExaminations(patientId),
    onSuccess: () => setExportError(''),
    onError: (err) => setExportError(errorMessage(err, 'Xuất Excel thất bại')),
  })

  const exams: Examination[] = response?.data ?? []
  const total: number = response?.pagination?.total ?? 0
  const totalPages: number = response?.pagination?.total_pages ?? 1

  // Xoá dòng cuối của trang cuối thì trang hiện tại không còn gì để hiển thị.
  useEffect(() => {
    if (page > 1 && page > totalPages) setPage(totalPages)
  }, [page, totalPages])

  return (
    <Card size="full">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-slate-900">KHÁM BỆNH</h3>
          <p className="mt-1 text-sm text-slate-500">
            {total > 0 ? `${total} lần khám` : 'Chưa có lần khám nào'}
          </p>
        </div>
        <div className="flex flex-wrap justify-end gap-2.5">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setUploadMode('ocr')}
            leftIcon={<ScanLine className="h-4 w-4" />}
            title="Đọc ảnh chụp hoặc bản scan bằng OCR"
          >
            OCR
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setUploadMode('upload')}
            leftIcon={<FileText className="h-4 w-4" />}
            title="Đọc file Word hoặc PDF văn bản"
          >
            Upload phiếu khám
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => exportMutation.mutate()}
            isLoading={exportMutation.isPending}
            disabled={total === 0}
            leftIcon={!exportMutation.isPending ? <Download className="h-4 w-4" /> : undefined}
            title={total === 0 ? 'Chưa có lần khám để xuất' : 'Xuất bảng khám bệnh ra Excel'}
          >
            Xuất Excel
          </Button>
          <Button size="sm" onClick={onCreateExam}>
            Nhập bằng tay
          </Button>
        </div>
      </div>

      {exportError && (
        <div className="mb-4 flex items-start gap-2.5 rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-700">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{exportError}</span>
        </div>
      )}

      {isLoading ? (
        <Loading text="Đang tải danh sách lần khám..." />
      ) : exams.length === 0 ? (
        <p className="py-8 text-center text-sm text-slate-500">Chưa có lần khám nào</p>
      ) : (
        <div className="scrollbar-slim overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-slate-200 bg-slate-50">
              <tr>
                {columns.map((column) => (
                  <th
                    key={column.key}
                    className="whitespace-nowrap px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-600"
                  >
                    {column.label}
                  </th>
                ))}
                <th className="px-3 py-2.5 text-center text-xs font-semibold uppercase tracking-wide text-slate-600">
                  Thao tác
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {exams.map((exam) => (
                <tr key={exam.id} className="align-top hover:bg-slate-50">
                  {columns.map((column) => {
                    const text = examCell(exam, column.key, block)

                    if (column.key === 'exam_info.exam_date') {
                      const source = SOURCE_META[exam.source ?? 'manual'] ?? SOURCE_META.manual
                      return (
                        <td key={column.key} className="whitespace-nowrap px-3 py-3">
                          <span className="font-medium text-slate-900">{text || '—'}</span>
                          <Badge variant={source.variant} className="mt-1 block w-fit">
                            {source.label}
                          </Badge>
                        </td>
                      )
                    }

                    return (
                      <td
                        key={column.key}
                        className="px-3 py-3 text-slate-700"
                        title={text || undefined}
                      >
                        <span className="line-clamp-2 block max-w-[220px]">{text || '—'}</span>
                      </td>
                    )
                  })}
                  <td className="px-3 py-3">
                    <div className="flex items-center justify-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onViewExam(exam.id)}
                        className="h-8 w-8 p-0"
                        title="Xem chi tiết"
                      >
                        <Eye className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onEditExam(exam.id)}
                        className="h-8 w-8 p-0"
                        title="Sửa lần khám"
                      >
                        <Edit2 className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => deleteMutation.mutate(exam.id)}
                        disabled={deleteMutation.isPending}
                        className="h-8 w-8 p-0 text-red-600 hover:text-red-700"
                        title="Xóa lần khám"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <Pagination
            page={page}
            limit={limit}
            total={total}
            totalPages={totalPages}
            unit="lần khám"
            onPageChange={setPage}
            onLimitChange={(next) => {
              setLimit(next)
              setPage(1)
            }}
          />
        </div>
      )}

      <UploadExamDialog
        open={uploadMode !== null}
        mode={uploadMode ?? 'ocr'}
        patientId={patientId}
        onClose={() => setUploadMode(null)}
        onExtracted={(draft) => {
          setUploadMode(null)
          onReviewExtraction(draft.extraction_id)
        }}
      />
    </Card>
  )
}

/** Nhãn nguồn gốc bản ghi — dữ liệu do AI đọc cần phân biệt được với bác sĩ tự nhập. */
const SOURCE_META: Record<string, { label: string; variant: 'gray' | 'violet' | 'warning' }> = {
  manual: { label: 'Nhập tay', variant: 'gray' },
  ocr: { label: 'OCR', variant: 'violet' },
  upload: { label: 'Phiếu số', variant: 'warning' },
}

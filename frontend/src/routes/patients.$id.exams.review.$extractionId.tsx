/**
 * Màn hình soát kết quả bóc tách: trái là file gốc, phải là biểu mẫu đã điền sẵn.
 *
 * Bệnh án có hơn 70 ô nên nếu đổ hết ra một cột dọc thì không ai soát nổi. Vì
 * vậy vế phải chia theo đúng các mục của template, mỗi mục gập/mở được và có
 * số ô đã điền — bác sĩ soát lần lượt như một danh sách việc cần làm.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createRoute, useNavigate, useParams } from '@tanstack/react-router'
import {
  AlertCircle,
  AlertTriangle,
  Check,
  ChevronDown,
  ChevronRight,
  FileText,
  ScanLine,
  Save,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import { AppShell } from '@/components/layout/AppShell'
import { Button, Card, ErrorState, Loading } from '@/components/ui'
import {
  createExamination,
  getExtractionDraft,
  getPatient,
  getPatientFormSchema,
  type FormNode,
  type FormValues,
} from '@/features/patients/api'
import { DocumentPreview } from '@/features/patients/components/DocumentPreview'
import {
  DynamicForm,
  countFilled,
  countLeaves,
} from '@/features/patients/components/DynamicForm'
import { requireAuth } from '@/lib/auth-guard'
import { cn, errorMessage } from '@/lib/utils'
import { rootRoute } from '@/routes/__root'

export const examReviewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/patients/$id/exams/review/$extractionId',
  component: ExamReviewPage,
  beforeLoad: requireAuth,
})

function ExamReviewPage() {
  const { id, extractionId } = useParams({ from: examReviewRoute.id })
  const patientId = Number(id)
  const draftId = Number(extractionId)
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [values, setValues] = useState<FormValues>({})
  const [loadedDraftId, setLoadedDraftId] = useState<number | null>(null)
  const [openSections, setOpenSections] = useState<Set<string>>(new Set())
  const [showWarnings, setShowWarnings] = useState(false)
  const [error, setError] = useState('')

  const { data: patient } = useQuery({
    queryKey: ['patient', patientId],
    queryFn: async () => (await getPatient(patientId)).data,
  })

  const { data: schema, isLoading: schemaLoading } = useQuery({
    queryKey: ['form-schema', patientId],
    queryFn: () => getPatientFormSchema(patientId),
  })

  const { data: draft, isLoading: draftLoading } = useQuery({
    queryKey: ['extraction', patientId, draftId],
    queryFn: () => getExtractionDraft(patientId, draftId),
  })

  const block = schema?.blocks.find((item) => item.id === 'examination')
  const sections: FormNode[] = useMemo(() => block?.children ?? [], [block])

  // Chỉ nạp một lần: refetch khi quay lại tab không được đè lên phần đang sửa.
  useEffect(() => {
    if (draft && loadedDraftId !== draft.extraction_id) {
      setValues(draft.data ?? {})
      setLoadedDraftId(draft.extraction_id)
      // Mở sẵn mục đầu để thấy ngay có gì mà soát.
      setOpenSections(new Set(sections.length ? [sections[0].id] : []))
    }
  }, [draft, loadedDraftId, sections])

  const saveMutation = useMutation({
    mutationFn: () =>
      createExamination(patientId, {
        data: values,
        source: draft?.mode,
        document_id: draft?.document_id,
        extraction_id: draft?.extraction_id,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['exams', patientId] })
      navigate({ to: '/patients/$id', params: { id: String(patientId) } })
    },
    onError: (err) => setError(errorMessage(err, 'Lưu lần khám thất bại')),
  })

  if (schemaLoading || draftLoading) {
    return (
      <AppShell>
        <Card size="full">
          <Loading text="Đang tải kết quả bóc tách..." />
        </Card>
      </AppShell>
    )
  }

  if (!draft || !block) {
    return (
      <AppShell>
        <Card size="full">
          <ErrorState message="Không tìm thấy kết quả bóc tách." />
        </Card>
      </AppShell>
    )
  }

  const filled = sections.reduce(
    (total, section) => total + countFilled(section, values[section.id]),
    0,
  )
  const totalFields = sections.reduce((total, section) => total + countLeaves(section), 0)
  const allOpen = openSections.size === sections.length

  const toggleSection = (sectionId: string) =>
    setOpenSections((current) => {
      const next = new Set(current)
      next.has(sectionId) ? next.delete(sectionId) : next.add(sectionId)
      return next
    })

  const handleSave = () => {
    if (!values.exam_info?.exam_date) {
      setError('Vui lòng nhập ngày khám trước khi lưu.')
      setOpenSections((current) => new Set(current).add('exam_info'))
      return
    }
    setError('')
    saveMutation.mutate()
  }

  const ModeIcon = draft.mode === 'ocr' ? ScanLine : FileText

  return (
    <AppShell width="wide">
      {/* Thanh tóm tắt: gộp mọi thông tin trạng thái vào một dải thay vì xếp chồng nhiều hộp */}
      <div className="mb-4 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-card">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-3 px-4 py-3">
          <button
            type="button"
            onClick={() => navigate({ to: '/patients/$id', params: { id: String(patientId) } })}
            className="inline-flex h-9 items-center gap-2 rounded-lg border border-slate-300 px-3 text-sm text-slate-600 transition-colors hover:bg-slate-50 hover:text-slate-900"
          >
            <ChevronRight className="h-4 w-4 rotate-180" />
            Quay lại
          </button>

          <div className="min-w-0 flex-1">
            <h1 className="truncate text-base font-semibold text-slate-900">
              Soát lại kết quả đọc tự động
            </h1>
            <p className="truncate text-sm text-slate-500">
              {patient?.full_name}
              {schema && ` · ${schema.disease_label}`}
            </p>
          </div>

          <span className="inline-flex items-center gap-1.5 rounded-full bg-brand-50 px-3 py-1 text-xs font-medium text-brand-800">
            <ModeIcon className="h-3.5 w-3.5" />
            {draft.mode === 'ocr' ? 'OCR ảnh/scan' : 'Phiếu digital'}
          </span>

          <ProgressPill filled={filled} total={totalFields} />

          {draft.warnings.length > 0 && (
            <button
              type="button"
              onClick={() => setShowWarnings((open) => !open)}
              className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-3 py-1 text-xs font-medium text-amber-800 transition-colors hover:bg-amber-100"
            >
              <AlertTriangle className="h-3.5 w-3.5" />
              {draft.warnings.length} chỗ cần tự điền
            </button>
          )}
        </div>

        {(draft.note || draft.provider === 'stub') && (
          <p className="border-t border-slate-100 bg-slate-50 px-4 py-2 text-xs text-slate-600">
            {draft.provider === 'stub' &&
              'Đang chạy chế độ giả lập — chưa cấu hình OPENAI_API_KEY nên dữ liệu bên dưới là giả. '}
            {draft.note}
          </p>
        )}

        {showWarnings && draft.warnings.length > 0 && (
          <ul className="max-h-48 list-disc space-y-1 overflow-auto border-t border-amber-100 bg-amber-50/60 px-8 py-3 text-sm text-amber-900">
            {draft.warnings.map((warning, index) => (
              <li key={index}>{warning}</li>
            ))}
          </ul>
        )}
      </div>

      {error && (
        <div className="mb-4 flex items-start gap-2.5 rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-700">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
        {/* Bản gốc — dính theo khi cuộn để luôn đối chiếu được */}
        <div className="xl:sticky xl:top-4 xl:h-[calc(100vh-7rem)]">
          <Card size="full" className="flex h-full flex-col">
            <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Bản gốc
            </h2>
            <div className="min-h-[24rem] flex-1">
              <DocumentPreview
                patientId={patientId}
                documentId={draft.document_id}
                fileName={draft.file_name}
                mimeType={draft.mime_type}
              />
            </div>
          </Card>
        </div>

        {/* Kết quả đọc — chia theo mục của template */}
        <div className="space-y-3">
          <div className="flex items-center justify-between px-1">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Kết quả đọc — đối chiếu và sửa
            </h2>
            <button
              type="button"
              onClick={() =>
                setOpenSections(allOpen ? new Set() : new Set(sections.map((s) => s.id)))
              }
              className="text-xs font-medium text-brand-700 hover:text-brand-900"
            >
              {allOpen ? 'Thu gọn tất cả' : 'Mở tất cả'}
            </button>
          </div>

          {sections.map((section) => (
            <SectionCard
              key={section.id}
              section={section}
              open={openSections.has(section.id)}
              onToggle={() => toggleSection(section.id)}
              values={values[section.id] ?? {}}
              onChange={(next) => setValues({ ...values, [section.id]: next })}
            />
          ))}
        </div>
      </div>

      {/* Thanh hành động dính đáy màn hình — không phải cuộn hết form mới bấm được Lưu */}
      <div className="sticky bottom-0 z-10 mt-4 flex items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white/95 px-4 py-3 shadow-popover backdrop-blur">
        <p className="text-sm text-slate-500">
          Đã điền <span className="font-semibold text-slate-900">{filled}</span>/{totalFields} ô
        </p>
        <div className="flex gap-2.5">
          <Button
            variant="outline"
            onClick={() => navigate({ to: '/patients/$id', params: { id: String(patientId) } })}
            disabled={saveMutation.isPending}
          >
            Hủy
          </Button>
          <Button
            isLoading={saveMutation.isPending}
            onClick={handleSave}
            leftIcon={!saveMutation.isPending ? <Save className="h-4 w-4" /> : undefined}
          >
            Lưu lần khám
          </Button>
        </div>
      </div>
    </AppShell>
  )
}

// ==================== Thành phần phụ ====================

function ProgressPill({ filled, total }: { filled: number; total: number }) {
  const percent = total ? Math.round((filled / total) * 100) : 0
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-24 overflow-hidden rounded-full bg-slate-200">
        <div className="h-full rounded-full bg-brand-600" style={{ width: `${percent}%` }} />
      </div>
      <span className="text-xs tabular-nums text-slate-600">
        {filled}/{total} ô
      </span>
    </div>
  )
}

function SectionCard({
  section,
  open,
  onToggle,
  values,
  onChange,
}: {
  section: FormNode
  open: boolean
  onToggle: () => void
  values: FormValues
  onChange: (next: FormValues) => void
}) {
  const total = countLeaves(section)
  const filled = countFilled(section, values)
  const complete = filled === total && total > 0

  return (
    <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-card">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-slate-50"
      >
        {open ? (
          <ChevronDown className="h-4 w-4 shrink-0 text-slate-400" />
        ) : (
          <ChevronRight className="h-4 w-4 shrink-0 text-slate-400" />
        )}

        <span className="min-w-0 flex-1 truncate text-sm font-semibold text-slate-900">
          {section.label}
        </span>

        <span
          className={cn(
            'inline-flex shrink-0 items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium tabular-nums',
            complete
              ? 'bg-emerald-50 text-emerald-700'
              : filled === 0
                ? 'bg-slate-100 text-slate-500'
                : 'bg-amber-50 text-amber-700',
          )}
        >
          {complete && <Check className="h-3 w-3" />}
          {filled}/{total}
        </span>
      </button>

      {open && (
        <div className="border-t border-slate-100 px-4 py-4">
          <DynamicForm block={section} values={values} onChange={onChange} mode="edit" />
        </div>
      )}
    </section>
  )
}

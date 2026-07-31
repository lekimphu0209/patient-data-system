import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useSearch } from '@tanstack/react-router'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { AppShell } from '@/components/layout/AppShell'
import { ConfirmDialog, Toast } from '@/components/ui'
import { useDebouncedValue } from '@/hooks/useDebouncedValue'
import { useToast } from '@/hooks/useToast'
import { errorMessage } from '@/lib/utils'
import type { PatientSearch } from '@/routes/patients'
import type {
  ImportPreviewResponse,
  ImportPreviewRow,
  Patient,
  PatientListFilters,
} from '../api'
import {
  bulkDeletePatients,
  commitImportPatients,
  deletePatient,
  downloadExportedFile,
  downloadImportTemplate,
  exportPatients,
  listPatients,
  previewImportPatients,
} from '../api'
import { CardHeader } from './CardHeader'
import { ImportDialog } from './ImportDialog'
import { Pagination } from './Pagination'
import { PatientTable } from './PatientTable'
import { PatientToolbar } from './PatientToolbar'

type PendingDelete =
  | { kind: 'single'; patient: Patient }
  | { kind: 'bulk'; codes: string[]; count: number }

export function PatientList() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { page, limit, q, diagnosis } = useSearch({ from: '/patients' }) as PatientSearch

  const { toast, showToast, clearToast } = useToast()

  // --- Filters -----------------------------------------------------------
  const [searchInput, setSearchInput] = useState(q)
  const debouncedSearch = useDebouncedValue(searchInput, 350)

  const updateSearch = useCallback(
    (patch: Partial<PatientSearch>) => {
      navigate({
        to: '/patients',
        search: (prev) => ({ ...(prev as PatientSearch), ...patch }),
      })
    },
    [navigate]
  )

  // Keep the box in sync when the URL changes from elsewhere (back/forward).
  useEffect(() => setSearchInput(q), [q])

  // Typing applies the filter on its own — there is no search button.
  useEffect(() => {
    if (debouncedSearch === q) return
    updateSearch({ q: debouncedSearch, page: 1 })
  }, [debouncedSearch, q, updateSearch])

  const filters: PatientListFilters = useMemo(() => ({ q, diagnosis }), [q, diagnosis])
  const hasFilters = Boolean(q || diagnosis)

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ['patients', page, limit, filters],
    queryFn: () => listPatients(page, limit, filters),
    placeholderData: (previous) => previous,
  })

  const patients = data?.data ?? []
  const pagination = data?.pagination
  const total = pagination?.total ?? 0
  const totalPages = pagination?.total_pages ?? 0

  // A page beyond the end (after deleting or shrinking the page size) would
  // render an empty table, so walk back to the last page that has rows.
  useEffect(() => {
    if (totalPages > 0 && page > totalPages) {
      updateSearch({ page: totalPages })
    }
  }, [page, totalPages, updateSearch])

  // --- Selection ---------------------------------------------------------
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  useEffect(() => setSelectedIds(new Set()), [page, limit, q, diagnosis])

  const toggleSelection = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleSelectAll = () => {
    const ids = patients.map((p) => p.id)
    const allSelected = ids.length > 0 && ids.every((id) => selectedIds.has(id))
    setSelectedIds(allSelected ? new Set() : new Set(ids))
  }

  const selectedCount = selectedIds.size

  // --- Delete ------------------------------------------------------------
  const [pendingDelete, setPendingDelete] = useState<PendingDelete | null>(null)
  const [deleting, setDeleting] = useState(false)

  const confirmDelete = async () => {
    if (!pendingDelete) return
    setDeleting(true)
    try {
      if (pendingDelete.kind === 'single') {
        await deletePatient(pendingDelete.patient.id)
        showToast(`Đã xóa bệnh nhân ${pendingDelete.patient.full_name}`)
      } else {
        await bulkDeletePatients(pendingDelete.codes)
        showToast(`Đã xóa ${pendingDelete.count} bệnh nhân`)
      }
      setSelectedIds(new Set())
      queryClient.invalidateQueries({ queryKey: ['patients'] })
      setPendingDelete(null)
    } catch (err) {
      showToast(errorMessage(err, 'Xóa bệnh nhân thất bại.'), 'error')
    } finally {
      setDeleting(false)
    }
  }

  const requestBulkDelete = () => {
    const codes = patients.filter((p) => selectedIds.has(p.id)).map((p) => p.patient_code)
    if (codes.length === 0) return
    setPendingDelete({ kind: 'bulk', codes, count: codes.length })
  }

  // --- Export ------------------------------------------------------------
  const [exporting, setExporting] = useState(false)

  const handleExport = async () => {
    setExporting(true)
    try {
      // No selection means "export everything matching the current filters".
      const ids = selectedCount > 0 ? Array.from(selectedIds) : undefined
      const result = await exportPatients(filters, 'xlsx', ids)
      await downloadExportedFile(result.download_url, result.filename)
      showToast(
        ids
          ? `Đã xuất ${ids.length} bệnh nhân đã chọn`
          : `Đã xuất toàn bộ ${total} bệnh nhân${hasFilters ? ' theo bộ lọc hiện tại' : ''}`
      )
    } catch (err) {
      showToast(errorMessage(err, 'Xuất dữ liệu thất bại.'), 'error')
    } finally {
      setExporting(false)
    }
  }

  // --- Import ------------------------------------------------------------
  const [showImport, setShowImport] = useState(false)
  const [importPreview, setImportPreview] = useState<ImportPreviewResponse | null>(null)
  const [importLoading, setImportLoading] = useState(false)
  const [importError, setImportError] = useState('')
  const [importSuccess, setImportSuccess] = useState('')
  const [importFileName, setImportFileName] = useState('')
  const [templateLoading, setTemplateLoading] = useState(false)

  const resetImport = () => {
    setImportPreview(null)
    setImportError('')
    setImportSuccess('')
    setImportFileName('')
  }

  const closeImport = () => {
    setShowImport(false)
    resetImport()
  }

  const handleFileSelected = async (file: File) => {
    resetImport()
    setImportFileName(file.name)
    setImportLoading(true)
    try {
      setImportPreview(await previewImportPatients(file))
    } catch (err) {
      setImportError(errorMessage(err, 'Không đọc được file, vui lòng kiểm tra lại định dạng.'))
    } finally {
      setImportLoading(false)
    }
  }

  const handleImportCommit = async () => {
    if (!importPreview) return
    const validRows = importPreview.rows.filter((r: ImportPreviewRow) => r.valid)
    if (validRows.length === 0) return

    setImportLoading(true)
    setImportError('')
    try {
      const result = await commitImportPatients(validRows)
      queryClient.invalidateQueries({ queryKey: ['patients'] })
      showToast(`Đã nhập thành công ${result.created} bệnh nhân`)
      setImportPreview(null)
      setImportSuccess(`Đã nhập thành công ${result.created} bệnh nhân vào hệ thống.`)
      window.setTimeout(closeImport, 1400)
    } catch (err) {
      setImportError(errorMessage(err, 'Nhập dữ liệu thất bại.'))
    } finally {
      setImportLoading(false)
    }
  }

  const handleDownloadTemplate = async () => {
    setTemplateLoading(true)
    try {
      await downloadImportTemplate()
      showToast('Đã tải file mẫu')
    } catch (err) {
      showToast(errorMessage(err, 'Tải file mẫu thất bại.'), 'error')
    } finally {
      setTemplateLoading(false)
    }
  }

  // --- Render ------------------------------------------------------------
  const goToNewPatient = () => navigate({ to: '/patients/new' })

  return (
    <AppShell>
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-card">
        <CardHeader
          total={pagination ? total : undefined}
          onImport={() => setShowImport(true)}
          onCreate={goToNewPatient}
        />

        <PatientToolbar
          search={searchInput}
          onSearchChange={setSearchInput}
          diagnosis={diagnosis}
          onDiagnosisChange={(value) => updateSearch({ diagnosis: value, page: 1 })}
          selectedCount={selectedCount}
          exporting={exporting}
          onExport={handleExport}
          onDelete={requestBulkDelete}
        />

        <PatientTable
          patients={patients}
          isLoading={isLoading || (isFetching && patients.length === 0)}
          hasFilters={hasFilters}
          selectedIds={selectedIds}
          onToggle={toggleSelection}
          onToggleAll={toggleSelectAll}
          onDelete={(patient) => setPendingDelete({ kind: 'single', patient })}
          onCreate={goToNewPatient}
        />

        {totalPages > 0 && (
          <Pagination
            page={page}
            limit={limit}
            total={total}
            totalPages={totalPages}
            onPageChange={(next) => updateSearch({ page: next })}
            onLimitChange={(next) => updateSearch({ limit: next, page: 1 })}
          />
        )}
      </div>

      {showImport && (
        <ImportDialog
          loading={importLoading}
          error={importError}
          successMessage={importSuccess}
          fileName={importFileName}
          preview={importPreview}
          onClose={closeImport}
          onFileSelected={handleFileSelected}
          onCommit={handleImportCommit}
          onReset={resetImport}
          onDownloadTemplate={handleDownloadTemplate}
          templateLoading={templateLoading}
        />
      )}

      <ConfirmDialog
        open={pendingDelete !== null}
        title={pendingDelete?.kind === 'bulk' ? 'Xóa các bệnh nhân đã chọn?' : 'Xóa bệnh nhân này?'}
        message={
          pendingDelete?.kind === 'bulk'
            ? `${pendingDelete.count} hồ sơ bệnh nhân sẽ bị xóa khỏi danh sách. Bạn có chắc chắn không?`
            : `Hồ sơ của ${pendingDelete?.kind === 'single' ? pendingDelete.patient.full_name : ''} sẽ bị xóa khỏi danh sách. Bạn có chắc chắn không?`
        }
        confirmLabel="Xóa"
        loading={deleting}
        onConfirm={confirmDelete}
        onCancel={() => setPendingDelete(null)}
      />

      {toast && <Toast message={toast.message} type={toast.type} onClose={clearToast} />}
    </AppShell>
  )
}

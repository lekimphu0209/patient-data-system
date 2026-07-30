import { useNavigate, useSearch } from '@tanstack/react-router'
import { useEffect, useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'

import { useAuth } from '@/app/auth-context'
import { Toast } from '@/components/ui'
import { useToast } from '@/hooks/useToast'
import type {
  ImportPreviewResponse,
  ImportPreviewRow,
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
import { AddPatientDialog } from './AddPatientDialog'
import { CardHeader } from './CardHeader'
import { ImportDialog } from './ImportDialog'
import { PatientTable } from './PatientTable'
import { Pagination } from './Pagination'
import { PatientToolbar } from './PatientToolbar'
import { StatusLegend } from './StatusLegend'
import { TopBar } from './TopBar'

interface PatientSearch {
  page?: number
  q?: string
  diagnosis?: string
  birthDateFrom?: string
  birthDateTo?: string
}

export function PatientList() {
  const { user, logout } = useAuth()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const search = useSearch({ from: '/patients' }) as PatientSearch

  const page = search.page || 1
  const q = search.q || ''
  const diagnosis = search.diagnosis || ''
  const birthDateFrom = search.birthDateFrom || ''
  const birthDateTo = search.birthDateTo || ''

  const [searchInput, setSearchInput] = useState(q)

  const [localDiagnosis, setLocalDiagnosis] = useState(diagnosis)
  const [localFrom, setLocalFrom] = useState(birthDateFrom)
  const [localTo, setLocalTo] = useState(birthDateTo)

  useEffect(() => setLocalDiagnosis(diagnosis), [diagnosis])
  useEffect(() => setLocalFrom(birthDateFrom), [birthDateFrom])
  useEffect(() => setLocalTo(birthDateTo), [birthDateTo])

  const filters: PatientListFilters = useMemo(
    () => ({
      q,
      diagnosis,
      birthDateFrom,
      birthDateTo,
    }),
    [q, diagnosis, birthDateFrom, birthDateTo]
  )

  const { data, isLoading } = useQuery({
    queryKey: ['patients', page, filters],
    queryFn: () => listPatients(page, 10, filters),
  })

  const patients = data?.data ?? []
  const pagination = data?.pagination

  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  useEffect(() => setSelectedIds(new Set()), [page])

  const [showAddDialog, setShowAddDialog] = useState(false)

  const [showImport, setShowImport] = useState(false)
  const [importPreview, setImportPreview] = useState<ImportPreviewResponse | null>(null)
  const [importLoading, setImportLoading] = useState(false)
  const [importMessage, setImportMessage] = useState('')

  const { toast, showToast } = useToast()

  const applyFilters = () => {
    navigate({
      to: '/patients',
      search: (prev) => ({
        ...(prev as object),
        q: searchInput,
        diagnosis: localDiagnosis,
        birthDateFrom: localFrom,
        birthDateTo: localTo,
        page: 1,
      }),
    })
  }

  const handlePageChange = (newPage: number) => {
    navigate({
      to: '/patients',
      search: (prev) => ({ ...(prev as object), page: newPage }),
    })
  }

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
    if (selectedIds.size === ids.length && ids.length > 0) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(ids))
    }
  }

  const selectedCount = selectedIds.size

  const handleDelete = async (id: number) => {
    if (!confirm('Xóa bệnh nhân này?')) return
    try {
      await deletePatient(id)
      queryClient.invalidateQueries({ queryKey: ['patients'] })
      showToast('Đã xóa bệnh nhân')
    } catch (err: any) {
      showToast(err.message || 'Lỗi khi xóa', 'error')
    }
  }

  const handleBulkDelete = async () => {
    if (!confirm(`Xóa ${selectedCount} bệnh nhân đã chọn?`)) return
    try {
      const codes = patients
        .filter((p) => selectedIds.has(p.id))
        .map((p) => p.patient_code)
      await bulkDeletePatients(codes)
      setSelectedIds(new Set())
      queryClient.invalidateQueries({ queryKey: ['patients'] })
      showToast('Đã xóa các bệnh nhân đã chọn')
    } catch (err: any) {
      showToast(err.message || 'Lỗi khi xóa hàng loạt', 'error')
    }
  }

  const handleExport = async () => {
    if (selectedIds.size === 0) return
    try {
      const result = await exportPatients(filters, 'xlsx', Array.from(selectedIds))
      await downloadExportedFile(result.download_url, result.filename)
      showToast('Xuất danh sách bệnh nhân thành công')
    } catch (err: any) {
      showToast(err.message || 'Lỗi khi xuất', 'error')
    }
  }

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setImportLoading(true)
    setImportMessage('')
    setImportPreview(null)
    try {
      const preview = await previewImportPatients(file)
      setImportPreview(preview)
    } catch (err: any) {
      setImportMessage(err.message || 'Lỗi khi xem trước file')
    } finally {
      setImportLoading(false)
    }
  }

  const handleImportCommit = async () => {
    if (!importPreview) return
    const validRows = importPreview.rows.filter((r: ImportPreviewRow) => r.valid)
    if (validRows.length === 0) return
    setImportLoading(true)
    try {
      const result = await commitImportPatients(validRows)
      setImportMessage(`Đã nhập thành công ${result.created} bệnh nhân.`)
      queryClient.invalidateQueries({ queryKey: ['patients'] })
      setImportPreview(null)
      setTimeout(() => setShowImport(false), 1200)
      showToast(`Đã nhập thành công ${result.created} bệnh nhân`)
    } catch (err: any) {
      setImportMessage(err.message || 'Lỗi khi nhập dữ liệu')
      showToast(err.message || 'Lỗi khi nhập dữ liệu', 'error')
    } finally {
      setImportLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <TopBar
        user={user}
        onLogout={() => {
          logout()
          navigate({ to: '/login' })
        }}
      />

      <main className="max-w-7xl mx-auto p-6">
        

        <div className="bg-white border border-gray-200 rounded-2xl shadow-sm p-6">
          <CardHeader
            onImport={() => setShowImport(true)}
            onToggleAdd={() => setShowAddDialog(true)}
          />

          <PatientToolbar
            search={searchInput}
            onSearchChange={setSearchInput}
            diagnosis={localDiagnosis}
            onDiagnosisChange={setLocalDiagnosis}
            birthDateFrom={localFrom}
            onBirthDateFromChange={setLocalFrom}
            birthDateTo={localTo}
            onBirthDateToChange={setLocalTo}
            onSearch={applyFilters}
            selectedCount={selectedCount}
            onExport={handleExport}
            onDelete={handleBulkDelete}
          />

          <div className="mt-6">
            <div className="overflow-x-auto">
              <PatientTable
                patients={patients}
                isLoading={isLoading}
                selectedIds={selectedIds}
                onToggle={toggleSelection}
                onToggleAll={toggleSelectAll}
                onDelete={handleDelete}
              />
            </div>

            <StatusLegend />

            {pagination && pagination.total_pages > 0 && (
              <Pagination
                page={page}
                totalPages={pagination.total_pages}
                onChange={handlePageChange}
              />
            )}
          </div>
        </div>
      </main>

      {showAddDialog && (
        <AddPatientDialog
          open={showAddDialog}
          onClose={() => setShowAddDialog(false)}
          onSuccess={() => showToast('Đã thêm bệnh nhân')}
        />
      )}

      {showImport && (
        <ImportDialog
          loading={importLoading}
          message={importMessage}
          preview={importPreview}
          onClose={() => {
            setShowImport(false)
            setImportPreview(null)
            setImportMessage('')
          }}
          onFileChange={handleFileChange}
          onCommit={handleImportCommit}
          onDownloadTemplate={async () => {
            try {
              await downloadImportTemplate()
              showToast('Đã tải file mẫu')
            } catch {
              showToast('Lỗi khi tải file mẫu', 'error')
            }
          }}
        />
      )}

      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => showToast('', 'success')}
        />
      )}
    </div>
  )
}

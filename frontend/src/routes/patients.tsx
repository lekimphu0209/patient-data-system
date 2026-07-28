import { createRoute, Link } from '@tanstack/react-router'
import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'

import { useAuth } from '@/app/auth-context'
import { rootRoute } from '@/routes/__root'
import {
  bulkDeletePatients,
  deletePatient,
  exportPatients,
  listPatients,
  type Patient,
} from '@/features/patients/api'

export const patientsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/patients',
  component: PatientsPage,
})

function PatientsPage() {
  const { user, logout } = useAuth()
  const queryClient = useQueryClient()

  const [page, setPage] = useState(1)
  const [q, setQ] = useState('')
  const [showExtraColumns, setShowExtraColumns] = useState(false)
  const [selectedIds, setSelectedIds] = useState<number[]>([])

  const limit = 20

  const { data, isLoading } = useQuery({
    queryKey: ['patients', page, q],
    queryFn: () => listPatients(page, limit, q),
  })

  const toggleSelection = (id: number) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    )
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Xóa bệnh nhân này?')) return
    await deletePatient(id)
    queryClient.invalidateQueries({ queryKey: ['patients'] })
  }

  const handleBulkDelete = async () => {
    if (!confirm(`Xóa ${selectedIds.length} bệnh nhân đã chọn?`)) return
    await bulkDeletePatients(selectedIds)
    setSelectedIds([])
    queryClient.invalidateQueries({ queryKey: ['patients'] })
  }

  const handleExport = async () => {
    const result = await exportPatients(selectedIds.length > 0 ? selectedIds : undefined)
    window.open(`http://localhost:8000${result.download_url}`, '_blank')
  }

  const patients = data?.data ?? []
  const pagination = data?.pagination

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow p-4 flex justify-between items-center">
        <h1 className="text-xl font-bold">Danh sách bệnh nhân</h1>
        <div className="flex items-center gap-4">
          <span className="text-sm text-gray-600">{user?.full_name}</span>
          <button
            onClick={logout}
            className="text-sm text-red-600 hover:underline"
          >
            Đăng xuất
          </button>
        </div>
      </header>

      <main className="p-6 max-w-7xl mx-auto">
        <div className="flex flex-wrap gap-3 mb-4">
          <Link
            to="/patients/new"
            className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
          >
            Thêm bệnh nhân
          </Link>
          <button
            onClick={handleExport}
            className="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700"
          >
            Xuất dữ liệu
          </button>
          {selectedIds.length > 0 && (
            <button
              onClick={handleBulkDelete}
              className="bg-red-600 text-white px-4 py-2 rounded hover:bg-red-700"
            >
              Xóa đã chọn ({selectedIds.length})
            </button>
          )}
          <label className="flex items-center gap-2 ml-auto">
            <input
              type="checkbox"
              checked={showExtraColumns}
              onChange={(e) => setShowExtraColumns(e.target.checked)}
            />
            <span className="text-sm">Hiển thị thêm cột xóa/xuất</span>
          </label>
        </div>

        <div className="mb-4">
          <input
            type="text"
            placeholder="Tìm kiếm theo tên hoặc mã bệnh nhân..."
            value={q}
            onChange={(e) => {
              setQ(e.target.value)
              setPage(1)
            }}
            className="w-full max-w-md border rounded px-3 py-2"
          />
        </div>

        <div className="bg-white rounded shadow overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-gray-100">
                {showExtraColumns && (
                  <th className="p-3 border-b">
                    <input
                      type="checkbox"
                      checked={
                        patients.length > 0 && selectedIds.length === patients.length
                      }
                      onChange={(e) =>
                        setSelectedIds(
                          e.target.checked ? patients.map((p) => p.id) : []
                        )
                      }
                    />
                  </th>
                )}
                <th className="p-3 border-b">Mã BN</th>
                <th className="p-3 border-b">Họ tên</th>
                <th className="p-3 border-b">Tuổi</th>
                <th className="p-3 border-b">Loại bệnh</th>
                {showExtraColumns && (
                  <>
                    <th className="p-3 border-b">Xóa</th>
                    <th className="p-3 border-b">Xuất</th>
                  </>
                )}
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={showExtraColumns ? 7 : 4} className="p-4 text-center">
                    Đang tải...
                  </td>
                </tr>
              ) : patients.length === 0 ? (
                <tr>
                  <td colSpan={showExtraColumns ? 7 : 4} className="p-4 text-center">
                    Không có dữ liệu
                  </td>
                </tr>
              ) : (
                patients.map((patient) => (
                  <PatientRow
                    key={patient.id}
                    patient={patient}
                    showExtraColumns={showExtraColumns}
                    selected={selectedIds.includes(patient.id)}
                    onToggle={() => toggleSelection(patient.id)}
                    onDelete={() => handleDelete(patient.id)}
                  />
                ))
              )}
            </tbody>
          </table>
        </div>

        {pagination && (
          <div className="flex justify-center items-center gap-2 mt-4">
            <button
              disabled={page <= 1}
              onClick={() => setPage(page - 1)}
              className="px-3 py-1 border rounded disabled:opacity-50"
            >
              Trước
            </button>
            <span className="text-sm">
              Trang {page} / {pagination.total_pages}
            </span>
            <button
              disabled={page >= pagination.total_pages}
              onClick={() => setPage(page + 1)}
              className="px-3 py-1 border rounded disabled:opacity-50"
            >
              Sau
            </button>
          </div>
        )}
      </main>
    </div>
  )
}

interface PatientRowProps {
  patient: Patient
  showExtraColumns: boolean
  selected: boolean
  onToggle: () => void
  onDelete: () => void
}

function PatientRow({
  patient,
  showExtraColumns,
  selected,
  onToggle,
  onDelete,
}: PatientRowProps) {
  return (
    <tr className="hover:bg-gray-50">
      {showExtraColumns && (
        <td className="p-3 border-b">
          <input type="checkbox" checked={selected} onChange={onToggle} />
        </td>
      )}
      <td className="p-3 border-b">{patient.patient_code}</td>
      <td className="p-3 border-b">{patient.full_name}</td>
      <td className="p-3 border-b">{patient.age ?? '-'}</td>
      <td className="p-3 border-b">{patient.disease_type ?? '-'}</td>
      {showExtraColumns && (
        <>
          <td className="p-3 border-b">
            <button
              onClick={onDelete}
              className="text-red-600 hover:underline text-sm"
            >
              Xóa
            </button>
          </td>
          <td className="p-3 border-b">
            <button
              onClick={() => exportPatients([patient.id])}
              className="text-green-600 hover:underline text-sm"
            >
              Xuất
            </button>
          </td>
        </>
      )}
    </tr>
  )
}

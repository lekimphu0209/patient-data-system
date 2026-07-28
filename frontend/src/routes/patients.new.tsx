import { createRoute, useNavigate } from '@tanstack/react-router'
import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'

import { rootRoute } from '@/routes/__root'
import { createPatient } from '@/features/patients/api'

export const newPatientRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/patients/new',
  component: NewPatientPage,
})

function NewPatientPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const mutation = useMutation({
    mutationFn: createPatient,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patients'] })
      navigate({ to: '/patients' })
    },
  })

  const [form, setForm] = useState({
    patient_code: '',
    full_name: '',
    birth_date: '',
    age: '',
    disease_type: '',
    diagnosis: '',
  })

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => {
    setForm({ ...form, [e.target.name]: e.target.value })
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    mutation.mutate({
      ...form,
      age: form.age ? parseInt(form.age) : undefined,
      birth_date: form.birth_date || undefined,
      disease_type: form.disease_type || undefined,
      diagnosis: form.diagnosis || undefined,
    })
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-2xl mx-auto bg-white rounded shadow p-8">
        <h1 className="text-2xl font-bold mb-6">Thêm bệnh nhân</h1>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Mã bệnh nhân</label>
            <input
              name="patient_code"
              value={form.patient_code}
              onChange={handleChange}
              className="w-full border rounded px-3 py-2"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Họ tên</label>
            <input
              name="full_name"
              value={form.full_name}
              onChange={handleChange}
              className="w-full border rounded px-3 py-2"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Ngày sinh</label>
            <input
              name="birth_date"
              type="date"
              value={form.birth_date}
              onChange={handleChange}
              className="w-full border rounded px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Tuổi</label>
            <input
              name="age"
              type="number"
              value={form.age}
              onChange={handleChange}
              className="w-full border rounded px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Loại bệnh</label>
            <select
              name="disease_type"
              value={form.disease_type}
              onChange={handleChange}
              className="w-full border rounded px-3 py-2"
            >
              <option value="">-- Chọn --</option>
              <option value="depression">Trầm cảm</option>
              <option value="schizophrenia">Tâm thần phân liệt</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Chẩn đoán</label>
            <input
              name="diagnosis"
              value={form.diagnosis}
              onChange={handleChange}
              className="w-full border rounded px-3 py-2"
            />
          </div>
          <div className="flex gap-3 pt-4">
            <button
              type="submit"
              disabled={mutation.isPending}
              className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:opacity-50"
            >
              {mutation.isPending ? 'Đang lưu...' : 'Lưu'}
            </button>
            <button
              type="button"
              onClick={() => navigate({ to: '/patients' })}
              className="border px-4 py-2 rounded hover:bg-gray-100"
            >
              Hủy
            </button>
          </div>
          {mutation.isError && (
            <div className="text-red-600 text-sm">
              Có lỗi xảy ra khi lưu bệnh nhân.
            </div>
          )}
        </form>
      </div>
    </div>
  )
}

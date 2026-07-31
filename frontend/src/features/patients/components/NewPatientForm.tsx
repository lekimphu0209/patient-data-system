import { AddFormState, DIAGNOSIS_OPTIONS, DISEASE_TYPE_OPTIONS } from '../constants'

interface NewPatientFormProps {
  form: AddFormState
  onChange: (field: keyof AddFormState, value: string) => void
  onSubmit: (e: React.FormEvent) => void
  onCancel: () => void
  loading: boolean
}

export function NewPatientForm({ form, onChange, onSubmit, onCancel, loading }: NewPatientFormProps) {
  return (
    <form
      onSubmit={onSubmit}
      className="mb-6 p-4 bg-gray-50 border border-gray-200 rounded-xl"
    >
      <h3 className="text-sm font-semibold text-gray-900 mb-3">Thêm bệnh nhân mới</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        <input
          required
          type="text"
          placeholder="Mã BN *"
          value={form.patient_code}
          onChange={(e) => onChange('patient_code', e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
        />
        <input
          required
          type="text"
          placeholder="Họ và tên *"
          value={form.full_name}
          onChange={(e) => onChange('full_name', e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
        />
        <input
          type="date"
          placeholder="Ngày sinh"
          value={form.birth_date}
          onChange={(e) => onChange('birth_date', e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
        />
        <input
          type="text"
          placeholder="Quê quán"
          value={form.hometown}
          onChange={(e) => onChange('hometown', e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
        />
        <input
          type="number"
          placeholder="Tuổi"
          value={form.age}
          onChange={(e) => onChange('age', e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
        />
        <select
          value={form.disease_type}
          onChange={(e) => onChange('disease_type', e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 bg-white"
        >
          <option value="">-- Loại bệnh --</option>
          {DISEASE_TYPE_OPTIONS.slice(1).map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <select
          value={form.diagnosis}
          onChange={(e) => onChange('diagnosis', e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 bg-white"
        >
          <option value="">-- Chẩn đoán --</option>
          {DIAGNOSIS_OPTIONS.slice(1).map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <select
          value={form.status}
          onChange={(e) => onChange('status', e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 bg-white"
        >
          <option value="active">Hoạt động</option>
          <option value="inactive">Không hoạt động</option>
        </select>
      </div>

      <div className="flex items-center justify-end gap-2 mt-4">
        <button
          type="button"
          onClick={onCancel}
          className="border border-gray-300 text-gray-600 hover:bg-gray-50 font-medium text-sm px-4 py-2 rounded-lg transition"
        >
          Hủy
        </button>
        <button
          type="submit"
          disabled={loading || !form.patient_code || !form.full_name}
          className="bg-green-600 text-white hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium text-sm px-4 py-2 rounded-lg transition"
        >
          {loading ? 'Đang lưu...' : 'Lưu bệnh nhân'}
        </button>
      </div>
    </form>
  )
}

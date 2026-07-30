import { useEffect, useState } from 'react'
import { User } from 'lucide-react'

import { Button, Card, FormField, FormSection, Input, Select, Textarea } from '@/components/ui'
import { GENDER_OPTIONS } from '@/constants'
import type { Patient, PatientCreateRequest } from '../api'
import { DIAGNOSIS_OPTIONS } from '../constants'

export interface PatientFormData {
  patient_code: string
  full_name: string
  birth_date: string
  gender: string
  hometown: string
  contactPhone: string
  contactPerson: string
  diagnosis: string
  notes: string
}

interface PatientFormProps {
  patient?: Patient
  mode: 'new' | 'edit'
  loading: boolean
  onSubmit: (data: PatientCreateRequest) => void
  onCancel: () => void
  error?: string | null
  showTitle?: boolean
}

const diagnosisOptions = [
  { value: '', label: 'Chọn chẩn đoán' },
  ...DIAGNOSIS_OPTIONS.slice(1),
]

const fieldLabels: Record<keyof PatientFormData, string> = {
  patient_code: 'Mã bệnh nhân',
  full_name: 'Họ và tên',
  birth_date: 'Ngày sinh',
  gender: 'Giới tính',
  hometown: 'Quê quán',
  contactPhone: 'Số điện thoại',
  contactPerson: 'Người liên hệ',
  diagnosis: 'Chẩn đoán hiện tại',
  notes: 'Ghi chú',
}

function getInitialData(patient?: Patient): PatientFormData {
  return {
    patient_code: patient?.patient_code ?? '',
    full_name: patient?.full_name ?? '',
    birth_date: patient?.birth_date ?? '',
    gender: (patient?.patient_metadata?.gender as string) ?? '',
    hometown: patient?.hometown ?? '',
    contactPhone: (patient?.contact_info?.phone as string) ?? '',
    contactPerson: (patient?.contact_info?.contact_person as string) ?? '',
    diagnosis: patient?.diagnosis ?? '',
    notes: (patient?.patient_metadata?.notes as string) ?? '',
  }
}

function buildPayload(values: PatientFormData): PatientCreateRequest {
  const contact_info =
    values.contactPhone || values.contactPerson
      ? { phone: values.contactPhone, contact_person: values.contactPerson }
      : undefined
  const patient_metadata =
    values.gender || values.notes
      ? { gender: values.gender, notes: values.notes }
      : undefined
  return {
    patient_code: values.patient_code,
    full_name: values.full_name,
    birth_date: values.birth_date || undefined,
    hometown: values.hometown || undefined,
    diagnosis: values.diagnosis || undefined,
    contact_info,
    patient_metadata,
  }
}

export function PatientForm({
  patient,
  mode,
  loading,
  onSubmit,
  onCancel,
  error,
  showTitle = true,
}: PatientFormProps) {
  const [values, setValues] = useState<PatientFormData>(getInitialData(patient))
  const [errors, setErrors] = useState<Record<string, string>>({})

  useEffect(() => {
    setValues(getInitialData(patient))
    setErrors({})
  }, [patient?.id])

  const isRequired = (field: keyof PatientFormData) =>
    field === 'patient_code' || field === 'full_name'

  const validateField = (field: keyof PatientFormData) => {
    if (isRequired(field) && !values[field].trim()) {
      setErrors((prev) => ({ ...prev, [field]: 'Trường này là bắt buộc' }))
    } else {
      setErrors((prev) => {
        const next = { ...prev }
        delete next[field]
        return next
      })
    }
  }

  const handleChange = (field: keyof PatientFormData, value: string) => {
    setValues((prev) => ({ ...prev, [field]: value }))
    if (errors[field]) validateField(field)
  }

  const handleBlur = (field: keyof PatientFormData) => {
    validateField(field)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    validateField('patient_code')
    validateField('full_name')
    if (!values.patient_code.trim() || !values.full_name.trim()) return
    const data = buildPayload(values)
    onSubmit(data)
  }

  return (
    <Card size="lg">
      <form onSubmit={(e) => handleSubmit(e)}>
        {showTitle && (
          <div className="flex items-center gap-2 mb-6">
            <User className="w-7 h-7 text-teal-700" />
            <h2 className="text-2xl font-bold text-gray-900">Thông tin bệnh nhân</h2>
          </div>
        )}

        <div className="space-y-6">
          <FormSection title="Thông tin cơ bản">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6">
              <FormField
                label={fieldLabels.patient_code}
                htmlFor="patient_code"
                required
              >
                <Input
                  id="patient_code"
                  type="text"
                  value={values.patient_code}
                  onChange={(e) => handleChange('patient_code', e.target.value)}
                  onBlur={() => handleBlur('patient_code')}
                  placeholder="Nhập mã bệnh nhân"
                  readOnly={mode === 'edit'}
                  className={mode === 'edit' ? 'bg-gray-100 text-gray-600' : ''}
                  error={errors.patient_code}
                />
              </FormField>

              <FormField
                label={fieldLabels.full_name}
                htmlFor="full_name"
                required
              >
                <Input
                  id="full_name"
                  type="text"
                  value={values.full_name}
                  onChange={(e) => handleChange('full_name', e.target.value)}
                  onBlur={() => handleBlur('full_name')}
                  placeholder="Nhập họ và tên"
                  error={errors.full_name}
                />
              </FormField>

              <FormField label={fieldLabels.birth_date} htmlFor="birth_date">
                <Input
                  id="birth_date"
                  type="date"
                  value={values.birth_date}
                  onChange={(e) => handleChange('birth_date', e.target.value)}
                  onBlur={() => handleBlur('birth_date')}
                  error={errors.birth_date}
                />
              </FormField>

              <FormField label={fieldLabels.gender} htmlFor="gender">
                <Select
                  id="gender"
                  value={values.gender}
                  onChange={(e) => handleChange('gender', e.target.value)}
                  onBlur={() => handleBlur('gender')}
                  options={GENDER_OPTIONS}
                  error={errors.gender}
                />
              </FormField>

              <FormField label={fieldLabels.hometown} htmlFor="hometown">
                <Input
                  id="hometown"
                  type="text"
                  value={values.hometown}
                  onChange={(e) => handleChange('hometown', e.target.value)}
                  onBlur={() => handleBlur('hometown')}
                  placeholder="Nhập quê quán"
                  error={errors.hometown}
                />
              </FormField>
            </div>
          </FormSection>

          <FormSection title="Thông tin liên hệ">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6">
              <FormField label={fieldLabels.contactPhone} htmlFor="contactPhone">
                <Input
                  id="contactPhone"
                  type="text"
                  value={values.contactPhone}
                  onChange={(e) => handleChange('contactPhone', e.target.value)}
                  onBlur={() => handleBlur('contactPhone')}
                  placeholder="Nhập số điện thoại"
                  error={errors.contactPhone}
                />
              </FormField>

              <FormField label={fieldLabels.contactPerson} htmlFor="contactPerson">
                <Input
                  id="contactPerson"
                  type="text"
                  value={values.contactPerson}
                  onChange={(e) => handleChange('contactPerson', e.target.value)}
                  onBlur={() => handleBlur('contactPerson')}
                  placeholder="Nhập tên người liên hệ"
                  error={errors.contactPerson}
                />
              </FormField>
            </div>
          </FormSection>

          <FormSection title="Thông tin y tế">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6">
              <FormField label={fieldLabels.diagnosis} htmlFor="diagnosis">
                <Select
                  id="diagnosis"
                  value={values.diagnosis}
                  onChange={(e) => handleChange('diagnosis', e.target.value)}
                  onBlur={() => handleBlur('diagnosis')}
                  options={diagnosisOptions}
                  error={errors.diagnosis}
                />
              </FormField>

              <FormField
                label={fieldLabels.notes}
                htmlFor="notes"
                className="md:col-span-2"
              >
                <Textarea
                  id="notes"
                  value={values.notes}
                  onChange={(e) => handleChange('notes', e.target.value)}
                  onBlur={() => handleBlur('notes')}
                  placeholder="Nhập ghi chú về tình trạng bệnh nhân"
                  className="h-32"
                  error={errors.notes}
                />
              </FormField>
            </div>
          </FormSection>
        </div>

        {error && (
          <p className="mt-4 text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
            {error}
          </p>
        )}

        <div className="mt-6 pt-6 border-t border-gray-100 flex flex-wrap items-center justify-end gap-3">
          <Button type="button" variant="outline" onClick={onCancel}>
            Hủy
          </Button>
          <Button
            type="submit"
            isLoading={loading}
            disabled={loading || !values.patient_code.trim() || !values.full_name.trim()}
          >
            {loading ? 'Đang lưu...' : 'Lưu'}
          </Button>
        </div>
      </form>
    </Card>
  )
}

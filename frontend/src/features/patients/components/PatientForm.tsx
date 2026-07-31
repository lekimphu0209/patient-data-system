import { AlertCircle, HeartPulse, Phone, Save, User } from 'lucide-react'
import { useEffect, useState } from 'react'

import { Button, Card, FormField, FormSection, Input, Select, Textarea } from '@/components/ui'
import { GENDER_OPTIONS, VALIDATION_MESSAGES } from '@/constants'
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
}

const diagnosisOptions = [{ value: '', label: 'Chọn chẩn đoán' }, ...DIAGNOSIS_OPTIONS.slice(1)]

const REQUIRED_FIELDS: (keyof PatientFormData)[] = ['patient_code', 'full_name']

function getInitialData(patient?: Patient): PatientFormData {
  return {
    patient_code: patient?.patient_code ?? '',
    full_name: patient?.full_name ?? '',
    birth_date: patient?.birth_date?.slice(0, 10) ?? '',
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
    values.gender || values.notes ? { gender: values.gender, notes: values.notes } : undefined

  return {
    patient_code: values.patient_code.trim(),
    full_name: values.full_name.trim(),
    birth_date: values.birth_date || undefined,
    hometown: values.hometown.trim() || undefined,
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
}: PatientFormProps) {
  const [values, setValues] = useState<PatientFormData>(getInitialData(patient))
  const [errors, setErrors] = useState<Partial<Record<keyof PatientFormData, string>>>({})

  useEffect(() => {
    setValues(getInitialData(patient))
    setErrors({})
  }, [patient?.id])

  const validateField = (field: keyof PatientFormData) => {
    const invalid = REQUIRED_FIELDS.includes(field) && !values[field].trim()
    setErrors((prev) => {
      const next = { ...prev }
      if (invalid) next[field] = VALIDATION_MESSAGES.required
      else delete next[field]
      return next
    })
    return !invalid
  }

  const handleChange = (field: keyof PatientFormData, value: string) => {
    setValues((prev) => ({ ...prev, [field]: value }))
    if (errors[field] && value.trim()) {
      setErrors((prev) => {
        const next = { ...prev }
        delete next[field]
        return next
      })
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const allValid = REQUIRED_FIELDS.map(validateField).every(Boolean)
    if (!allValid) return
    onSubmit(buildPayload(values))
  }

  const canSubmit = REQUIRED_FIELDS.every((field) => values[field].trim())

  return (
    <Card size="full">
      <form onSubmit={handleSubmit} noValidate>
        <FormSection title="Thông tin cơ bản" icon={<User className="h-4 w-4" />}>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <FormField label="Mã bệnh nhân" htmlFor="patient_code" required>
              <Input
                id="patient_code"
                value={values.patient_code}
                onChange={(e) => handleChange('patient_code', e.target.value)}
                onBlur={() => validateField('patient_code')}
                placeholder="VD: BN001"
                readOnly={mode === 'edit'}
                error={errors.patient_code}
              />
            </FormField>

            <FormField label="Họ và tên" htmlFor="full_name" required>
              <Input
                id="full_name"
                value={values.full_name}
                onChange={(e) => handleChange('full_name', e.target.value)}
                onBlur={() => validateField('full_name')}
                placeholder="VD: Nguyễn Văn An"
                error={errors.full_name}
              />
            </FormField>

            <FormField label="Ngày sinh" htmlFor="birth_date">
              <Input
                id="birth_date"
                type="date"
                max={new Date().toISOString().slice(0, 10)}
                value={values.birth_date}
                onChange={(e) => handleChange('birth_date', e.target.value)}
              />
            </FormField>

            <FormField label="Giới tính" htmlFor="gender">
              <Select
                id="gender"
                value={values.gender}
                onChange={(e) => handleChange('gender', e.target.value)}
                options={GENDER_OPTIONS}
              />
            </FormField>

            <FormField label="Quê quán" htmlFor="hometown" className="md:col-span-2">
              <Input
                id="hometown"
                value={values.hometown}
                onChange={(e) => handleChange('hometown', e.target.value)}
                placeholder="VD: Hà Nội"
              />
            </FormField>
          </div>
        </FormSection>

        <FormSection title="Thông tin liên hệ" icon={<Phone className="h-4 w-4" />}>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <FormField label="Số điện thoại" htmlFor="contactPhone">
              <Input
                id="contactPhone"
                type="tel"
                inputMode="tel"
                value={values.contactPhone}
                onChange={(e) => handleChange('contactPhone', e.target.value)}
                placeholder="VD: 0912345678"
              />
            </FormField>

            <FormField label="Người liên hệ" htmlFor="contactPerson">
              <Input
                id="contactPerson"
                value={values.contactPerson}
                onChange={(e) => handleChange('contactPerson', e.target.value)}
                placeholder="Tên người thân"
              />
            </FormField>
          </div>
        </FormSection>

        <FormSection title="Thông tin y tế" icon={<HeartPulse className="h-4 w-4" />}>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <FormField label="Chẩn đoán hiện tại" htmlFor="diagnosis">
              <Select
                id="diagnosis"
                value={values.diagnosis}
                onChange={(e) => handleChange('diagnosis', e.target.value)}
                options={diagnosisOptions}
              />
            </FormField>

            <FormField label="Ghi chú" htmlFor="notes" className="md:col-span-2">
              <Textarea
                id="notes"
                rows={4}
                value={values.notes}
                onChange={(e) => handleChange('notes', e.target.value)}
                placeholder="Ghi chú về tình trạng, phác đồ điều trị hoặc lịch tái khám"
              />
            </FormField>
          </div>
        </FormSection>

        {error && (
          <div className="mt-5 flex items-start gap-2.5 rounded-lg border border-red-200 bg-red-50 px-3.5 py-3 text-sm text-red-700">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div className="mt-5 flex flex-wrap items-center justify-end gap-2.5 border-t border-slate-100 pt-5">
          <Button type="button" variant="outline" onClick={onCancel} disabled={loading}>
            Hủy
          </Button>
          <Button
            type="submit"
            isLoading={loading}
            disabled={!canSubmit}
            leftIcon={<Save className="h-4 w-4" />}
          >
            {mode === 'edit' ? 'Lưu thay đổi' : 'Lưu bệnh nhân'}
          </Button>
        </div>
      </form>
    </Card>
  )
}

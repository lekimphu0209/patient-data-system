import type { Patient } from './api'

export const DIAGNOSIS_OPTIONS = [
  { value: '', label: 'Tất cả' },
  { value: 'Bình thường', label: 'Bình thường' },
  { value: 'Trầm cảm', label: 'Trầm cảm' },
  { value: 'Tâm thần phân liệt', label: 'Tâm thần phân liệt' },
]

export const DISEASE_TYPE_OPTIONS = [
  { value: '', label: 'Tất cả' },
  { value: 'depression', label: 'Trầm cảm' },
  { value: 'schizophrenia', label: 'Tâm thần phân liệt' },
  { value: 'normal', label: 'Bình thường' },
]

export const CONDITION_META: Record<string, { bg: string; dot: string; text: string; textColor: string }> = {
  depression: { bg: 'bg-[#FEF9C3]', dot: 'bg-yellow-400', text: 'Trầm cảm', textColor: 'text-yellow-700' },
  schizophrenia: { bg: 'bg-[#EDE9FE]', dot: 'bg-purple-400', text: 'Tâm thần phân liệt', textColor: 'text-purple-700' },
  normal: { bg: '', dot: '', text: 'Bình thường', textColor: 'text-gray-500' },
}

export function detectCondition(patient: Patient): string {
  const text = `${patient.diagnosis || ''} ${patient.disease_type || ''}`.toLowerCase()
  if (
    text.includes('trầm cảm') ||
    text.includes('depression') ||
    text.includes('tram cảm') ||
    text.includes('tram cam') ||
    text.includes('trầm')
  ) {
    return 'depression'
  }
  if (
    text.includes('tâm thần phân liệt') ||
    text.includes('schizophrenia') ||
    text.includes('phan liet') ||
    text.includes('phân liệt')
  ) {
    return 'schizophrenia'
  }
  return 'normal'
}

export function formatDate(value: string | null) {
  if (!value) return '-'
  return new Date(value).toLocaleDateString('vi-VN')
}

export interface AddFormState {
  patient_code: string
  full_name: string
  birth_date: string
  hometown: string
  age: string
  disease_type: string
  diagnosis: string
  status: string
}

import type { BadgeProps } from '@/components/ui'
import type { Patient } from './api'

export const DIAGNOSIS_OPTIONS = [
  { value: '', label: 'Tất cả chẩn đoán' },
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

export type Condition = 'depression' | 'schizophrenia' | 'normal'

/**
 * Clinical colour coding, applied as a chip on the diagnosis cell rather than a
 * separate column or a full-row tint — same signal, far less visual noise.
 */
export const CONDITION_META: Record<Condition, { label: string; variant: BadgeProps['variant'] }> = {
  depression: { label: 'Trầm cảm', variant: 'warning' },
  schizophrenia: { label: 'Tâm thần phân liệt', variant: 'violet' },
  normal: { label: 'Bình thường', variant: 'gray' },
}

export function detectCondition(patient: Patient): Condition {
  const text = `${patient.diagnosis || ''} ${patient.disease_type || ''}`.toLowerCase()
  if (text.includes('trầm') || text.includes('tram cam') || text.includes('depression')) {
    return 'depression'
  }
  if (
    text.includes('phân liệt') ||
    text.includes('phan liet') ||
    text.includes('schizophrenia')
  ) {
    return 'schizophrenia'
  }
  return 'normal'
}

export function formatDate(value: string | null) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleDateString('vi-VN')
}

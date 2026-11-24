import axios from 'axios'
import { api } from '@/lib/api'

export type ClinicalType = 'F20' | 'F32'
export type FieldKind = 'text' | 'textarea' | 'number' | 'date' | 'select' | 'multi'
export type ClinicalFieldDef = { key: string; label: string; kind: FieldKind; options?: string[] }
export type ClinicalSection = { key: string; title: string; fields: ClinicalFieldDef[] }
export type ClinicalForm = { title: string; sections: ClinicalSection[] }
export type ClinicalSpec = { identity: ClinicalFieldDef[]; forms: Record<ClinicalType, ClinicalForm> }

export type FieldValue = string | string[]
export type Visit = { id: string; date: string; createdAt: string; fields: Record<string, FieldValue> }
export type OcrSummary = {
  sourceFile: string
  pages: number
  extractedCount: number
  uncertain: string[]
  notes: string
  dateInferred: boolean
  model: string
}
export type Patient = {
  id: string
  type: ClinicalType
  code: string
  fullName: string
  age: string
  sex: string
  visits: Visit[]
  revision: number
  source?: string
  needsReview?: boolean
  createdAt?: string
  updatedAt?: string
  hasOriginal?: boolean
  originalType?: 'pdf' | 'image' | null
  ocr?: OcrSummary | null
  [identity: string]: unknown
}

export const CLINICAL_TYPES: ClinicalType[] = ['F20', 'F32']
export const isClinicalType = (value: string | undefined): value is ClinicalType => value === 'F20' || value === 'F32'

export async function getClinicalSpec() {
  return (await api.get<ClinicalSpec>('/clinical/forms')).data
}
export async function getPatients() {
  return (await api.get<{ patients: Patient[] }>('/clinical/patients')).data.patients
}
export async function savePatient(patient: Patient, createOnly: boolean) {
  return (await api.post<{ patient: Patient }>('/clinical/save', { patient, createOnly })).data.patient
}
export async function deletePatient(id: string, revision: number) {
  await api.post('/clinical/delete', { id, revision })
}
export async function extractPatient(type: ClinicalType, file: File, onUpload: (fraction: number) => void) {
  const body = new FormData()
  body.append('type', type)
  body.append('file', file)
  const { data } = await api.post<{ patient: Patient }>('/clinical/extract', body, {
    timeout: 300_000,
    onUploadProgress: event => onUpload(event.total ? event.loaded / event.total : 1),
  })
  return data.patient
}
export async function getOriginal(id: string) {
  return (await api.get<Blob>('/clinical/original', { params: { id }, responseType: 'blob' })).data
}

export function clinicalError(error: unknown) {
  if (axios.isAxiosError(error)) {
    if (error.code === 'ECONNABORTED') return 'Máy chủ phản hồi quá lâu. Vui lòng thử lại.'
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (!error.response) return 'Không kết nối được máy chủ. Kiểm tra mạng rồi thử lại.'
  }
  return error instanceof Error && error.message ? error.message : 'Không lưu được bệnh án.'
}

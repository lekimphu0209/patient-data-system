import { api } from '@/lib/api'
import { downloadBlob } from '@/lib/utils'

// ==================== Examination Types ====================
export interface Examination {
  id: number
  patient_id: number
  exam_date: string
  general_condition?: string
  cardiovascular?: string
  respiratory?: string
  digestive?: string
  urinary?: string
  neurological?: string
  other_body_parts?: string
  mental_exam?: Record<string, unknown>
  general_clinical_tests?: Record<string, unknown>
  other_clinical_tests?: Record<string, unknown>
  diagnosis?: string
  treatment?: string
  /** Khối KHÁM BỆNH lưu phân cấp theo form schema. */
  data?: Record<string, any>
  created_at: string
  updated_at: string
}

export interface MedicalHistory {
  id: number
  patient_id: number
  presenting_symptoms?: Record<string, unknown>
  onset_age?: number
  disease_duration_years?: number
  disease_duration_months?: number
  previous_diagnoses?: string[]
  disease_progression?: string
  relapse_count?: number
  previous_inpatient_treatments?: number
  medications_before_admission?: Record<string, unknown>
  reinforcement_status?: string
  circumstances_of_onset?: string
  personal_history?: Record<string, unknown>
  family_history?: Record<string, unknown>
  /** Khối HỎI BỆNH lưu phân cấp theo form schema. */
  data?: Record<string, any>
  created_at: string
  updated_at: string
}

export interface Patient {
  id: number
  patient_code: string
  full_name: string
  birth_date: string | null
  hometown: string | null
  age: number | null
  disease_type: string | null
  diagnosis: string | null
  status: string
  contact_info: Record<string, any> | null
  patient_metadata: Record<string, any> | null
  created_at: string
  updated_at: string
}

export interface PatientCreateRequest {
  patient_code: string
  full_name: string
  birth_date?: string
  hometown?: string
  age?: number
  disease_type?: string
  diagnosis?: string
  status?: string
  contact_info?: Record<string, any>
  patient_metadata?: Record<string, any>
}

export interface PaginatedResponse<T> {
  data: T[]
  pagination: {
    page: number
    limit: number
    total: number
    total_pages: number
  }
}

export interface PatientListFilters {
  q?: string
  diagnosis?: string
}

export async function listPatients(
  page = 1,
  limit = 20,
  filters: PatientListFilters = {}
): Promise<PaginatedResponse<Patient>> {
  const params: Record<string, unknown> = { page, limit }
  if (filters.q) params.q = filters.q
  if (filters.diagnosis) params.diagnosis = filters.diagnosis
  const response = await api.get('/patients', { params })
  return response.data
}

export async function createPatient(
  data: PatientCreateRequest
): Promise<{ data: Patient }> {
  const response = await api.post('/patients', data)
  return response.data
}

export async function getPatient(id: number): Promise<{ data: Patient }> {
  const response = await api.get(`/patients/${id}`)
  return response.data
}

export async function updatePatient(
  id: number,
  data: PatientCreateRequest
): Promise<{ data: Patient }> {
  const response = await api.patch(`/patients/${id}`, data)
  return response.data
}

export async function deletePatient(id: number): Promise<void> {
  await api.delete(`/patients/${id}`)
}

export async function bulkDeletePatients(patientCodes: string[]): Promise<void> {
  await api.delete('/patients', { data: { patient_codes: patientCodes } })
}

export async function exportPatients(
  filters: PatientListFilters = {},
  format: 'xlsx' | 'csv' = 'xlsx',
  ids?: number[]
): Promise<{ download_url: string; filename: string }> {
  const payload: Record<string, unknown> = { format }
  if (ids && ids.length > 0) payload.ids = ids
  if (filters.q) payload.q = filters.q
  if (filters.diagnosis) payload.diagnosis = filters.diagnosis

  const response = await api.post('/patients/export', payload)
  const { download_url, filename } = response.data as { download_url: string; filename: string }
  const baseURL = api.defaults.baseURL || `${window.location.origin}/api/v1`
  const normalizedBase = baseURL.startsWith('http') ? baseURL : `${window.location.origin}${baseURL}`
  const baseOrigin = new URL(normalizedBase).origin
  return { download_url: new URL(download_url, baseOrigin).toString(), filename }
}

export async function downloadExportedFile(
  downloadUrl: string,
  suggestedFilename?: string
): Promise<void> {
  const response = await api.get(downloadUrl, { responseType: 'blob' })

  let filename = suggestedFilename
  if (!filename) {
    const disposition = response.headers['content-disposition'] as string | undefined
    const match = disposition?.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/)
    if (match) filename = match[1].replace(/['"]/g, '').trim()
  }
  if (!filename) {
    const path = new URL(downloadUrl).searchParams.get('path')
    filename = path ? path.replace(/^.*[\\/]/, '') : 'danh_sach_benh_nhan.xlsx'
  }

  downloadBlob(response.data as Blob, filename)
}

export interface ImportPreviewRow {
  row: number
  valid: boolean
  data: Record<string, unknown>
  errors: string[]
}

export interface ImportPreviewResponse {
  valid_count: number
  invalid_count: number
  rows: ImportPreviewRow[]
}

export interface ImportCommitResponse {
  created: number
  errors: { row: number; error: string }[]
}

export async function previewImportPatients(file: File): Promise<ImportPreviewResponse> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await api.post('/patients/import', formData)
  return response.data
}

export async function commitImportPatients(
  rows: ImportPreviewRow[]
): Promise<ImportCommitResponse> {
  const response = await api.post('/patients/import/commit', { rows })
  return response.data
}

export async function downloadImportTemplate() {
  const res = await api.get('/patients/import/template', { responseType: 'blob' })
  downloadBlob(res.data as Blob, 'mau_nhap_benh_nhan.xlsx')
}

// ==================== Examination API ====================

export async function listExaminations(
  patientId: number,
  page: number = 1,
  limit: number = 10
) {
  const response = await api.get(`/patients/${patientId}/exams`, {
    params: { page, limit },
  })
  return response.data
}

export async function getExamination(patientId: number, examId: number) {
  const response = await api.get(`/patients/${patientId}/exams/${examId}`)
  return response.data
}

export async function getLatestExamination(patientId: number) {
  const response = await api.get(`/patients/${patientId}/exams/latest`)
  return response.data
}

export async function createExamination(patientId: number, data: Partial<Examination>) {
  const response = await api.post(`/patients/${patientId}/exams`, data)
  return response.data
}

export async function updateExamination(
  patientId: number,
  examId: number,
  data: Partial<Examination>
) {
  const response = await api.patch(`/patients/${patientId}/exams/${examId}`, data)
  return response.data
}

export async function deleteExamination(patientId: number, examId: number) {
  return await api.delete(`/patients/${patientId}/exams/${examId}`)
}

// ==================== Medical History API ====================

export async function getMedicalHistory(patientId: number) {
  const response = await api.get(`/patients/${patientId}/medical-history`)
  return response.data
}

export async function createMedicalHistory(patientId: number, data: Partial<MedicalHistory>) {
  const response = await api.post(`/patients/${patientId}/medical-history`, data)
  return response.data
}

export async function updateMedicalHistory(patientId: number, data: Partial<MedicalHistory>) {
  const response = await api.patch(`/patients/${patientId}/medical-history`, data)
  return response.data
}

// ==================== Form Schema API ====================
// Cấu trúc bệnh án do backend định nghĩa trong form_schema.json (theo template
// F20 / F32) và trả về đã lọc sẵn theo loại bệnh của bệnh nhân.

export type FormNodeType =
  | 'block'
  | 'group'
  | 'text'
  | 'textarea'
  | 'number'
  | 'date'
  | 'radio'
  | 'checkbox_group'
  | 'matrix'

export interface FormOption {
  value: string
  label: string
}

export interface FormMatrixRow {
  id: string
  label: string
}

export interface FormShowIf {
  field: string
  includes?: string
  equals?: string
}

export interface FormNode {
  id: string
  label: string
  type: FormNodeType
  part?: string
  unit?: string
  required?: boolean
  readonly?: boolean
  source?: string
  table_column?: string
  show_if?: FormShowIf
  options?: FormOption[]
  rows?: FormMatrixRow[]
  columns?: FormOption[]
  children?: FormNode[]
}

export interface ExamTableColumn {
  key: string
  label: string
  kind?: string
}

export interface FormSchema {
  version: string
  disease_code: 'f20' | 'f32' | 'normal'
  disease_label: string
  exam_table_columns: ExamTableColumn[]
  blocks: FormNode[]
}

/** Giá trị của một khối, lồng theo đúng cấu trúc group của schema. */
export type FormValues = Record<string, any>

export async function getPatientFormSchema(patientId: number) {
  const response = await api.get<{ data: FormSchema }>(`/patients/${patientId}/form-schema`)
  return response.data.data
}

export async function getFormSchemaByDisease(diseaseCode: string) {
  const response = await api.get<{ data: FormSchema }>(`/patients/forms/${diseaseCode}`)
  return response.data.data
}

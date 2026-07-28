import { api } from '@/lib/api'

export interface Patient {
  id: number
  patient_code: string
  full_name: string
  birth_date: string | null
  age: number | null
  disease_type: string | null
  diagnosis: string | null
  status: string
  created_at: string
  updated_at: string
}

export interface PatientCreateRequest {
  patient_code: string
  full_name: string
  birth_date?: string
  age?: number
  disease_type?: string
  diagnosis?: string
  status?: string
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

export async function listPatients(
  page = 1,
  limit = 20,
  q = ''
): Promise<PaginatedResponse<Patient>> {
  const response = await api.get('/patients', { params: { page, limit, q } })
  return response.data
}

export async function createPatient(
  data: PatientCreateRequest
): Promise<{ data: Patient }> {
  const response = await api.post('/patients', data)
  return response.data
}

export async function deletePatient(id: number): Promise<void> {
  await api.delete(`/patients/${id}`)
}

export async function bulkDeletePatients(ids: number[]): Promise<void> {
  await api.post('/patients/bulk-delete', { ids })
}

export async function exportPatients(ids?: number[]): Promise<{ download_url: string }> {
  const response = await api.post('/exports/patients', { ids, format: 'xlsx' })
  return response.data
}

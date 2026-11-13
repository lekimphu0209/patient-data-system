import { api } from '@/lib/api'
import type { Survey, SurveyForm } from './model'

export async function getForms(): Promise<SurveyForm[]> {
  return (await api.get('/surveys/forms')).data
}
export async function getRecords(): Promise<Survey[]> {
  return (await api.get('/surveys/records')).data
}
export async function getRecord(id: string): Promise<Survey> {
  return (await api.get('/surveys/record', { params: { id } })).data
}
export async function createRecords(records: Survey[]) {
  await api.post('/surveys/records', { records })
}
export async function updateRecord(record: Survey) {
  await api.put('/surveys/record', record)
}
export async function deleteRecords(ids: string[]) {
  await api.post('/surveys/delete', { ids })
}

export function surveyError(error: unknown) {
  const detail = (error as { response?: { data?: { detail?: string | { msg: string }[] } } })?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail[0]?.msg.replace(/^Value error, /, '') || 'Dữ liệu không hợp lệ.'
  return error instanceof Error ? error.message : 'Yêu cầu không thành công.'
}
